"""State (d) of plan section 5 (infrastructure failure, excluded) and provider classifier refusals, by written rules.
Deterministic; reads only runner-side files of each finished run: run.json, exit.txt, transcript.jsonl, api.jsonl, stderr.txt,
work_final/, and the presence (not the values) of the result lines in check_ci.txt / check_local.txt. It does not read
green, forbidden_mod, the descriptors, the board arm or the final message content, so exclusions are decided blind to the codes.

Rules, applied in this order (first match gives the cause):
  D0 agent_never_started  exit.txt says exit=unknown and agent_exit.txt is absent (the agent container never ran; deviation 15).
  D1 check_missing     check_ci.txt or check_local.txt has no `green=` line (checker or Docker failure after the agent).
  D2 work_missing      work_final/ is absent (docker cp of the final /work failed).
  D3 cli_no_start      no session start event in transcript.jsonl (Codex `thread.started`; Claude Code `system`/`init`).
  D4 proxy_no_start    provider that goes through the injecting proxy (adaption, openai-key, claude-oauth) and api.jsonl has no
                       START line.
  D5 provider_error    no tool call at all, and an error before it: a POST to the model API with status != 200, a Codex `error` or
                       `turn.failed` event, or a Claude Code `result` with is_error=true.
  D6 no_model_call     proxy provider, no tool call and no POST reached the proxy.
  D7 empty_run         no tool call and an empty final message (the CLI produced nothing).
A run with at least one tool call is never excluded by D5 to D7 (errors after the first tool call stay in the denominator).
Timeouts (exit=124) are not exclusions (state (c)).

Classifier refusal (counted, never excluded unless a D rule fires): a Claude assistant message with stop_reason "refusal", or an
error text (Codex error/turn.failed event, Claude error result, proxy log `error` field) matching
  content.?filter | safety (system|filter|policy) | usage polic | flagged | cyber.?(policy|safety) | violat\\w* (our|the) polic
Usage: python3 -I analyse/infra.py <out.csv> <campaign dir> [...]
"""
import csv, glob, json, os, re, sys

PROXIED = {"adaption", "openai-key", "claude-oauth"}
REFUSAL_RE = re.compile(r"content.?filter|safety (system|filter|policy)|usage polic|flagged|cyber.?(policy|safety)|violat\w* (our|the) polic", re.I)


def jl(p):
    if not os.path.exists(p):
        return
    for l in open(p, errors="replace"):
        try:
            o = json.loads(l)
        except Exception:
            continue
        if isinstance(o, dict):
            yield o


def has_line(p, prefix):
    return os.path.exists(p) and any(l.startswith(prefix) for l in open(p, errors="replace"))


def infra_for_run(d):
    rj = json.load(open(os.path.join(d, "run.json")))
    h, prov = rj["harness"], rj["provider"]
    started = False; tool_calls = 0; errors = []; refusal = False; final = ""; refusal_before_tool = False
    for e in jl(os.path.join(d, "transcript.jsonl")):
        t = e.get("type")
        if h == "claude":
            if t == "system" and e.get("subtype") == "init":
                started = True
            elif t == "assistant":
                msg = e.get("message", {})
                if msg.get("stop_reason") == "refusal":
                    refusal = True; refusal_before_tool = refusal_before_tool or tool_calls == 0
                for c in msg.get("content", []) or []:
                    if c.get("type") == "tool_use":
                        tool_calls += 1
                    elif c.get("type") == "text":
                        final = c.get("text", "")
            elif t == "result":
                final = e.get("result", final) or final
                if e.get("is_error"):
                    errors.append(("result", str(e.get("result") or e.get("subtype"))[:200], tool_calls))
        else:
            it = e.get("item", {}) or {}
            if t == "thread.started":
                started = True
            elif t == "item.started" and it.get("type") in ("command_execution", "file_change", "mcp_tool_call"):
                tool_calls += 1
            elif t == "item.completed" and it.get("type") == "agent_message":
                final = it.get("text", "")
            elif t in ("error", "turn.failed"):
                er = e.get("error")
                m = e.get("message") or (er.get("message") if isinstance(er, dict) else er)
                errors.append((t, str(m or e)[:200], tool_calls))
    api = list(jl(os.path.join(d, "api.jsonl")))
    api_start = any(r.get("method") == "START" for r in api)
    posts = [r for r in api if r.get("method") == "POST"]
    bad = [r for r in posts if r.get("status") != 200]
    first_err_before_tool = [x for x in errors if x[2] == 0]
    for x in errors:
        if REFUSAL_RE.search(x[1]):
            refusal = True; refusal_before_tool = refusal_before_tool or x[2] == 0
    for r in bad:
        if REFUSAL_RE.search(str(r.get("error", ""))):
            refusal = True
    cause = ""
    ex_txt = open(os.path.join(d, "exit.txt")).read().strip()
    if ex_txt == "exit=unknown" and not os.path.exists(os.path.join(d, "agent_exit.txt")):
        cause = "D0 agent_never_started"
    elif not (has_line(os.path.join(d, "check_ci.txt"), "green=") and has_line(os.path.join(d, "check_local.txt"), "green=")):
        cause = "D1 check_missing"
    elif not os.path.isdir(os.path.join(d, "work_final")):
        cause = "D2 work_missing"
    elif not started:
        cause = "D3 cli_no_start"
    elif prov in PROXIED and not api_start:
        cause = "D4 proxy_no_start"
    elif tool_calls == 0 and (bad or first_err_before_tool):
        msg = first_err_before_tool[0][1] if first_err_before_tool else f"HTTP {bad[0].get('status')}"
        cause = "D5 provider_error: " + re.sub(r"\s+", " ", msg)[:120]
    elif tool_calls == 0 and prov in PROXIED and not posts:
        cause = "D6 no_model_call"
    elif tool_calls == 0 and not (final or "").strip():
        cause = "D7 empty_run"
    return dict(campaign=rj["campaign"], package=f"{h}-{rj['model']}", scenario=rj["scenario"], run_id=rj["run_id"],
                state_d="yes" if cause else "no", d_cause=cause, tool_calls_infra=tool_calls, cli_started="yes" if started else "no",
                api_posts=len(posts) if prov in PROXIED else "", api_non200=len(bad) if prov in PROXIED else "",
                error_events=len(errors), classifier_refusal="yes" if refusal else "no",
                classifier_refusal_before_tool="yes" if refusal_before_tool else "no",
                exit=open(os.path.join(d, "exit.txt")).read().strip())


def main():
    out, camps = sys.argv[1], sys.argv[2:]
    rows = [infra_for_run(os.path.dirname(p)) for c in camps for p in sorted(glob.glob(os.path.join(c, "*", "*", "*", "exit.txt")))]
    if rows:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"infra: {len(rows)} runs, {sum(r['state_d'] == 'yes' for r in rows)} state (d) -> {out}")


if __name__ == "__main__":
    main()
