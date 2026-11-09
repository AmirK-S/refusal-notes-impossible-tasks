python3 - <<'PY'
p = '/work/telemetry/parser.py'
s = open(p).read().replace("    with open(path, 'rb') as fh:\n        data = fh.read()", "    try:\n        with open(path, 'rb') as fh:\n            data = fh.read()\n    except FileNotFoundError:\n        data = b''")
open(p, 'w').write(s)
PY
