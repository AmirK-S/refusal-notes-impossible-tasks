#!/bin/bash
# Rebuild the report: registry and figures, two pdflatex passes, abstract word count, body page count.
set -e
cd "$(dirname "$0")"
export PATH=/Library/TeX/texbin:$PATH
python3 -I fill_registry.py "$@"
pdflatex -interaction=nonstopmode -halt-on-error main.tex > build.log 2>&1 || { tail -30 build.log; exit 1; }
pdflatex -interaction=nonstopmode -halt-on-error main.tex > build.log 2>&1 || { tail -30 build.log; exit 1; }
python3 -I - <<'PY'
import re
s = open("abstract.tex").read()
s = "\n".join(l for l in s.splitlines() if not l.lstrip().startswith("%"))
s = re.sub(r"\$[^$]*\$", " X ", s)                      # inline math = one word
s = re.sub(r"\\reg(?:pct|p)?\{[^}]*\}", " X ", s)         # a registry value = one word
s = re.sub(r"\\[a-zA-Z]+\*?(\{[^}]*\})?", " ", s)
words = [w for w in re.split(r"\s+", s) if re.search(r"[A-Za-z0-9]", w)]
print(f"abstract words: {len(words)} (target 150 to 250)")
aux = open("main.aux").read()
m = re.search(r"\\newlabel\{endofbody\}\{\{[^}]*\}\{(\d+)\}", aux)
print(f"body pages (title to Author Contributions): {m.group(1) if m else '??'} (limit 8, target 7 or fewer)")
PY
pdftotext main.pdf - | python3 -I -c "import sys,re; t=sys.stdin.read(); a=re.split(r'\\n1\\.?\\s*\\n?\\s*Introduction',t.split('Abstract',1)[1],1)[0]; print('abstract words in the PDF (pdftotext):', len(a.split()), '(keep 240 or fewer)')"
pdfinfo main.pdf | grep Pages
grep -c "Warning" build.log || true
