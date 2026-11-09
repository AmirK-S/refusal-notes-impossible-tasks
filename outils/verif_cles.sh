#!/usr/bin/env bash
# Refuse a commit if staged content holds a secret: known secret values (read from the host secret files,
# never printed: ~/.config/hackathon/*.env and the token fields of ~/.codex/auth.json) and generic key
# patterns. Installed as .git/hooks/pre-commit (symlink). Also usable on any folder: verif_cles.sh <dir>.
set -u
VALS=$(python3 -I - <<'PY'
import glob, os, re, json
v = set()
for p in glob.glob(os.path.expanduser("~/.config/hackathon/*.env")):
    for l in open(p):
        m = re.match(r"\s*(?:export\s+)?([A-Z0-9_]+)=(.*)", l)
        if m and ("KEY" in m.group(1) or "TOKEN" in m.group(1)): v.add(m.group(2).strip().strip("'\""))
def walk(o):
    if isinstance(o, dict):
        for k, x in o.items():
            if isinstance(x, str) and re.search(r"token|key", k, re.I): v.add(x)
            else: walk(x)
try: walk(json.load(open(os.path.expanduser("~/.codex/auth.json"))))
except Exception: pass
print("\n".join(x for x in v if len(x) > 12))
PY
)
if [ $# -gt 0 ]; then files=$(find "$1" -type f); else files=$(git diff --cached --name-only --diff-filter=ACM); fi
[ -z "$files" ] && exit 0
fail=0; n=0
while IFS= read -r f; do
  [ -f "$f" ] || continue; n=$((n+1))
  if [ -n "$VALS" ] && printf '%s\n' "$VALS" | grep -qF -f - "$f"; then echo "SECRET VALUE in $f"; fail=1; fi
  grep -qE 'sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{30,}|eyJ[A-Za-z0-9_-]{40,}\.' "$f" && { echo "KEY PATTERN in $f"; fail=1; }
done <<< "$files"
[ $fail = 0 ] && echo "verif_cles: OK ($n files, $(printf '%s\n' "$VALS" | grep -c .) secret values checked)"
exit $fail
