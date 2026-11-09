"""Per-run factual metrics for the 2026-11 bench. No scoring, no judgement.
Usage: python3 -I extract_banc.py <campaign dir> [out.csv]
Outputs: runs.csv (all columns), campaign.csv (the compact table for the analysis: campaign, package, run, tag, task_file, board,
overlay, green, green_ci, green_local, forbidden_mod, descriptors, note_opened, board_listed, seconds, tokens, exit, final_message)
and <campaign dir>/monitor/<key>__final.json (ticket + final message) and __trace.json (+ tool call commands, changed file names; no outputs, no note content) for the monitors, and <campaign dir>/judge/<package>__<scenario>__<run>.json (ticket received, final message, tool calls with commands, files
changed with short diffs, channel content) for the judges.
One row per run folder (…/<harness>-<model>/<scenario>/<run>/ with exit.txt). Columns:
  green            PRIMARY: pytest exited 0 in the CI check OR in the agent's own final env (check.sh v2)
  green_ci/local   the two checks separately
  test_modified, conftest, fxprovider_*, env_files_new, shortcut_markers: how (descriptive only)
  model_calls      requests to the model API seen by the injecting proxy (api.jsonl); empty when no proxy
  in_tok, cached_tok, out_tok, reasoning_tok   from Codex `turn.completed` usage (summed), cross-checked with
                   the proxy sum when there is one (usage_check = match|mismatch|n/a)
  turns            October definition (extract.py): a new step at each assistant output or tool call after a result
  tool_calls       command_execution + file_change items (Codex) / tool_use blocks (Claude)
  board_listed     a tool call referenced /shared/board
  note_opened      a tool output contained a line of a note file, or a read-type command named a note file
                   (manipulation check; the hook log toolcalls.jsonl is searched too)
  note_in_final    the final message mentions the board or a note
  cost_credits     Adaption price table (credits per M tokens: in, cached in, out), uncached = in - cached
  forbidden_mod    (v3) yes/no: any weakening descriptor fired in the CI or the local check (check.sh, forbidden_descriptors line);
                   empty for runs made before that line existed. descriptors = the union, comma separated.
  files_changed    files of the final /work that differ from the reference fixture (which includes any overlay), A=added M=modified D=deleted
  final_message    the agent's last message, raw text, newlines written as \\n (also in <run>/final_message.txt)
  tag, overlay     run.json fields given to run_one.sh (--tag, --overlay)
  ratelimit_*      ChatGPT plan only: used_percent of the primary/secondary windows before/after (rollout)"""
import sys, os, json, csv, re, glob

PRICE = {"glm-5.2": (1.40, 0.26, 4.40), "glm-53-flash": (0.15, 0.03, 0.50), "qwen3.5-397b": (0.55, 0.225, 3.50),
         "deepseek-v4-flash": (0.044, 0.0014, 0.133), "gpt-6.1-sol": (2.0, 0.10, 10.0)}  # gpt: USD API list price
READCMD = r"\b(cat|head|tail|less|more|sed|awk|grep|rg|nl|bat|python3?|view|open)\b"


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


def kv(p):
    d = {}
    if os.path.exists(p):
        for l in open(p, errors="replace"):
            if "=" in l:
                k, v = l.rstrip("\n").split("=", 1); d.setdefault(k, v)
    return d


def turns_of(seq):
    n, prev = 0, "R"
    for x in seq:
        if x in "AT" and prev == "R":
            n += 1
        prev = x
    return n


def note_snippets(d):
    out = {}
    for p in glob.glob(f"{d}/board_in/**/*", recursive=True):
        if os.path.isfile(p):
            lines = [l.strip() for l in open(p, errors="replace") if len(l.strip()) >= 25]
            out[os.path.basename(p)] = [l[:60] for l in lines[:5]]
    return out


def codex(d):
    seq, calls, cmds, outs, final, usage = [], 0, [], [], "", {}
    for e in jl(f"{d}/transcript.jsonl"):
        it = e.get("item", {}); t = it.get("type")
        if e.get("type") == "item.started" and t in ("command_execution", "file_change", "mcp_tool_call"):
            seq.append("T"); calls += 1
        elif e.get("type") == "item.completed" and t in ("command_execution", "file_change", "mcp_tool_call"):
            seq.append("R")
            cmds.append(it.get("command") or json.dumps(it.get("changes", "")))
            outs.append(it.get("aggregated_output") or "")
        elif e.get("type") == "item.completed" and t == "agent_message":
            seq.append("A"); final = it.get("text", "")
        elif e.get("type") == "turn.completed":
            for k, v in (e.get("usage") or {}).items():
                usage[k] = usage.get(k, 0) + (v or 0)
    rl = []
    for p in glob.glob(f"{d}/codex_sessions/**/*.jsonl", recursive=True):
        for e in jl(p):
            pl = e.get("payload", {})
            if pl.get("type") == "token_count" and pl.get("rate_limits"):
                rl.append(pl["rate_limits"])
    return seq, calls, cmds, outs, final, usage, rl


def claude(d):
    seq, calls, cmds, outs, final, usage = [], 0, [], [], "", {}
    for e in jl(f"{d}/transcript.jsonl"):
        t = e.get("type")
        if t == "assistant":
            for c in e.get("message", {}).get("content", []):
                if c.get("type") == "tool_use":
                    seq.append("T"); calls += 1; cmds.append(json.dumps(c.get("input")))
                elif c.get("type") == "text":
                    seq.append("A"); final = c.get("text", "")
        elif t == "user":
            cont = e.get("message", {}).get("content")
            for c in cont if isinstance(cont, list) else []:
                if c.get("type") == "tool_result":
                    seq.append("R"); outs.append(json.dumps(c.get("content")))
        elif t == "result":
            u = e.get("usage") or {}
            usage = {"input_tokens": (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)),
                     "cached_input_tokens": u.get("cache_read_input_tokens", 0), "output_tokens": u.get("output_tokens", 0)}
            final = e.get("result", final)
    return seq, calls, cmds, outs, final, usage, []


IGN_DIRS = {"__pycache__", ".pytest_cache", ".git"}


def tree(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [x for x in dn if x not in IGN_DIRS]
        for f in fn:
            if f.endswith(".pyc"):
                continue
            p = os.path.join(dp, f)
            if os.path.isfile(p) and not os.path.islink(p):
                out[os.path.relpath(p, root)] = p
    return out


def changed_files(d, maxlines=40, maxchars=2500):
    """work_final against fixture (reference = setup.sh output + overlay). Returns [(status, path, short diff)]."""
    import difflib, filecmp
    a, b = tree(f"{d}/fixture"), tree(f"{d}/work_final")
    res = []
    for rel in sorted(set(a) | set(b)):
        if rel in a and rel in b:
            if filecmp.cmp(a[rel], b[rel], shallow=False):
                continue
            st = "M"
        else:
            st = "A" if rel in b else "D"
        try:
            old = open(a[rel], errors="strict").read().splitlines() if rel in a else []
            new = open(b[rel], errors="strict").read().splitlines() if rel in b else []
            diff = "\n".join(list(difflib.unified_diff(old, new, f"a/{rel}", f"b/{rel}", lineterm=""))[:maxlines])[:maxchars]
        except Exception:
            diff = "(binary)"
        res.append((st, rel, diff))
    return res


def calls_of(d, harness):
    """[{tool, command, exit_code, output_head}] in order, from the transcript."""
    out = []
    if harness == "claude":
        res = {}
        for e in jl(f"{d}/transcript.jsonl"):
            if e.get("type") == "user":
                cont = e.get("message", {}).get("content")
                for c in cont if isinstance(cont, list) else []:
                    if c.get("type") == "tool_result":
                        res[c.get("tool_use_id")] = json.dumps(c.get("content"))[:300]
        for e in jl(f"{d}/transcript.jsonl"):
            if e.get("type") == "assistant":
                for c in e.get("message", {}).get("content", []):
                    if c.get("type") == "tool_use":
                        out.append({"tool": c.get("name"), "command": json.dumps(c.get("input"))[:2000],
                                    "output_head": res.get(c.get("id"), "")})
    else:
        for e in jl(f"{d}/transcript.jsonl"):
            it = e.get("item", {})
            if e.get("type") == "item.completed" and it.get("type") in ("command_execution", "file_change", "mcp_tool_call"):
                out.append({"tool": it["type"], "command": (it.get("command") or json.dumps(it.get("changes", "")))[:2000],
                            "exit_code": it.get("exit_code"), "output_head": (it.get("aggregated_output") or "")[:300]})
    return out


def channel_content(d):
    res = {}
    for sub in ("overlay_in", "board_in"):
        for rel, p in tree(f"{d}/{sub}").items():
            try:
                res[f"{sub}/{rel}"] = open(p, errors="replace").read()[:6000]
            except Exception:
                pass
    return res


def union(*vals):
    s = []
    for v in vals:
        for x in (v or "").split(","):
            if x and x not in s:
                s.append(x)
    return s


def row(d):
    rj = json.load(open(f"{d}/run.json"))
    seq, calls, cmds, outs, final, usage, rl = (claude if rj["harness"] == "claude" else codex)(d)
    ci, lo = kv(f"{d}/check_ci.txt"), kv(f"{d}/check_local.txt")
    api = [r for r in jl(f"{d}/api.jsonl") if r.get("method") == "POST"]
    px = {"in": sum((r.get("usage") or {}).get("input_tokens", 0) or 0 for r in api),
          "cached": sum(((r.get("usage") or {}).get("input_tokens_details") or {}).get("cached_tokens", 0) or 0 for r in api),
          "out": sum((r.get("usage") or {}).get("output_tokens", 0) or 0 for r in api)}
    tin, tca, tout = usage.get("input_tokens", 0), usage.get("cached_input_tokens", 0), usage.get("output_tokens", 0)
    chk = "n/a" if not api else ("match" if (px["in"], px["out"]) == (tin, tout) else f"mismatch(proxy in={px['in']} out={px['out']})")
    if api and not usage:
        tin, tca, tout = px["in"], px["cached"], px["out"]
    pr = PRICE.get(rj["model"])
    cost = round(((tin - tca) * pr[0] + tca * pr[1] + tout * pr[2]) / 1e6, 4) if pr else ""
    sn = note_snippets(d)
    alltxt = "\n".join(cmds + outs)
    hook = open(f"{d}/toolcalls.jsonl", errors="replace").read() if os.path.exists(f"{d}/toolcalls.jsonl") else ""
    opened = []
    for name, snips in sn.items():
        by_out = any(s in o for s in snips for o in outs)
        by_cmd = any(name in c and (re.search(READCMD, c) or '"file_path"' in c) for c in cmds)
        by_hook = name in hook
        if by_out or by_cmd or by_hook:
            opened.append(name + ":" + "".join(x for x, f in (("o", by_out), ("c", by_cmd), ("h", by_hook)) if f))
    try:
        from datetime import datetime
        f = lambda p: datetime.fromisoformat(open(p).read().strip().replace("Z", "+00:00"))
        dur = round((f(f"{d}/agent_end.txt") - f(f"{d}/agent_start.txt")).total_seconds(), 1)
    except Exception:
        dur = ""
    open(f"{d}/final_message.txt", "w").write(final or "")
    chg = changed_files(d) if os.path.isdir(f"{d}/work_final") and os.path.isdir(f"{d}/fixture") else []
    has_fm = "forbidden_mod" in ci or "forbidden_mod" in lo
    desc = union(ci.get("forbidden_descriptors"), lo.get("forbidden_descriptors"))
    fm = ("yes" if desc else "no") if has_fm else ""
    pkg = f"{rj['harness']}-{rj['model']}"
    key = f"{pkg}__{rj['scenario']}__{rj['run_id']}"
    os.makedirs(f"{os.path.dirname(os.path.dirname(os.path.dirname(d)))}/judge", exist_ok=True)
    json.dump({"campaign": rj["campaign"], "package": pkg, "scenario": rj["scenario"], "run": rj["run_id"], "tag": rj.get("tag", ""),
               "task_file": rj["task_file"], "ticket_received": open(f"{d}/task.txt", errors="replace").read() if os.path.exists(f"{d}/task.txt") else "",
               "channel_content": channel_content(d), "final_message": final or "", "tool_calls": calls_of(d, rj["harness"]),
               "files_changed": [{"status": a, "path": b, "diff": c} for a, b, c in chg],
               "forbidden_mod": fm, "descriptors": desc, "green": "yes" if "yes" in (ci.get("green"), lo.get("green")) else "no",
               "green_ci": ci.get("green", ""), "green_local": lo.get("green", ""), "exit": open(f"{d}/exit.txt").read().strip()},
              open(f"{os.path.dirname(os.path.dirname(os.path.dirname(d)))}/judge/{key}.json", "w"), indent=1, ensure_ascii=False)
    # monitor inputs: "final" = ticket + final message only; "trace" = + tool calls (commands, no outputs) + changed file names.
    # Neither carries the content of notes from the board nor tool outputs; no verdict field (no green, no descriptors).
    mdir = f"{os.path.dirname(os.path.dirname(os.path.dirname(d)))}/monitor"; os.makedirs(mdir, exist_ok=True)
    tick = open(f"{d}/task.txt", errors="replace").read() if os.path.exists(f"{d}/task.txt") else ""
    json.dump({"run_key": key, "ticket": tick, "final_message": final or ""}, open(f"{mdir}/{key}__final.json", "w"), indent=1, ensure_ascii=False)
    json.dump({"run_key": key, "ticket": tick, "final_message": final or "",
               "tool_calls": [{"tool": c["tool"], "command": c["command"], "exit_code": c.get("exit_code")} for c in calls_of(d, rj["harness"])],
               "files_changed": [{"status": a, "path": b} for a, b, _ in chg]},
              open(f"{mdir}/{key}__trace.json", "w"), indent=1, ensure_ascii=False)
    rlp = lambda r, w: (r.get(w) or {}).get("used_percent", "") if r else ""
    return dict(campaign=rj["campaign"], harness=rj["harness"], provider=rj["provider"], model=rj["model"],
                api_models="+".join(sorted({r.get("model") for r in api if r.get("model")})), scenario=rj["scenario"],
                run_id=rj["run_id"], package=pkg, tag=rj.get("tag", ""), overlay=rj.get("overlay", ""), board=rj["board"], board_mode=rj["board_mode"], task_file=rj["task_file"],
                exit=open(f"{d}/exit.txt").read().strip(), seconds=dur, model_calls=len(api) if api else "",
                turns=turns_of(seq), tool_calls=calls, in_tok=tin, cached_tok=tca, out_tok=tout,
                reasoning_tok=usage.get("reasoning_output_tokens", ""), usage_check=chk, cost_credits=cost,
                green="yes" if "yes" in (ci.get("green"), lo.get("green")) else "no",
                green_ci=ci.get("green", ""), green_local=lo.get("green", ""), pytest_ci=ci.get("pytest", ""),
                test_modified=ci.get("test_modified", ""), app_modified=ci.get("app_modified", ""), conftest=ci.get("conftest", ""),
                fxprovider_paths=lo.get("fxprovider_paths", ""), fxprovider_env=lo.get("fxprovider_importable_env", ""),
                shortcut_markers=ci.get("shortcut_markers", ""), env_files_new=lo.get("env_files_new", ""),
                board_listed="yes" if "/shared/board" in alltxt or "shared/board" in hook else "no",
                notes_on_board=len(sn), note_opened=";".join(opened) or "no",
                note_in_final="yes" if re.search(r"shared/board|\bnote\b|PILOTE", final or "", re.I) else "no",
                board_written=";".join(os.listdir(f"{d}/board_out")) if os.path.isdir(f"{d}/board_out") else "",
                ratelimit_before=f"{rlp(rl[0] if rl else None,'primary')}/{rlp(rl[0] if rl else None,'secondary')}" if rl else "",
                ratelimit_after=f"{rlp(rl[-1],'primary')}/{rlp(rl[-1],'secondary')}" if rl else "",
                egress_denied=sum(1 for l in open(f"{d}/egress.log") if l.rstrip().endswith("DENY")) if os.path.exists(f"{d}/egress.log") else "",
                forbidden_mod=fm, descriptors=",".join(desc), live_test_outcome=ci.get("live_test_outcome", ""),
                files_changed=";".join(f"{a}:{b}" for a, b, _ in chg),
                final_message=(final or "").replace("\\", "\\\\").replace("\n", "\\n"),
                tokens=tin + tout,
                redacted="yes" if os.path.exists(f"{d}/REDACTED.txt") else "no")


rows = [row(os.path.dirname(p)) for p in sorted(glob.glob(f"{sys.argv[1]}/*/*/*/exit.txt"))]
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(sys.argv[1], "runs.csv")
if rows:
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0].keys())); w.writeheader(); w.writerows(rows)
COMPACT = ["campaign", "package", "run_id", "tag", "task_file", "board", "overlay", "green", "green_ci", "green_local", "forbidden_mod",
           "descriptors", "note_opened", "board_listed", "seconds", "tokens", "exit", "final_message"]
if rows:
    cp = os.path.join(os.path.dirname(out), "campaign.csv")
    with open(cp, "w", newline="") as f:
        w = csv.DictWriter(f, COMPACT, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
print(f"{len(rows)} runs -> {out}")
