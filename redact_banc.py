"""Replace every known secret value with <REDACTED_KEY> in all files of a run folder.
Secrets are read from the host's secret store only (never passed on a command line):
~/.config/hackathon/*.env (variables whose name holds KEY or TOKEN) and the token fields of
~/.codex/auth.json (Codex ChatGPT login). Writes REDACTED.txt when something was found."""
import sys, os, glob, json, re
home = os.path.expanduser("~/.config/hackathon")
vals = set()
for p in glob.glob(os.path.join(home, "*.env")):
    for l in open(p):
        m = re.match(r"\s*(?:export\s+)?([A-Z0-9_]+)=(.*)", l)
        if m and ("KEY" in m.group(1) or "TOKEN" in m.group(1)):
            vals.add(m.group(2).strip().strip("'\""))
aj = os.environ.get("CODEX_AUTH_JSON") or os.path.expanduser("~/.codex/auth.json")
def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, str) and re.search(r"token|key", k, re.I): vals.add(v)
            else: walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
if os.path.exists(aj):
    try: walk(json.load(open(aj)))
    except Exception: pass
vals = sorted((v for v in vals if len(v) > 12), key=len, reverse=True)
hits = []
for root, _, files in os.walk(sys.argv[1]):
    for f in files:
        p = os.path.join(root, f)
        if os.path.islink(p): continue
        b = open(p, "rb").read(); n = b
        for v in vals: n = n.replace(v.encode(), b"<REDACTED_KEY>")
        if n != b: open(p, "wb").write(n); hits.append(os.path.relpath(p, sys.argv[1]))
if hits:
    open(os.path.join(sys.argv[1], "REDACTED.txt"), "w").write("secret value found and redacted in: " + ", ".join(hits) + "\n")
print(f"redact: {len(vals)} secret(s) checked, {len(hits)} file(s) redacted")
