python3 - <<'PY'
import struct
recs = [(1742025600, 22.5, 101.3, 40.0), (1742025660, 22.6, 101.2, 40.5), (1742025720, 22.7, 101.1, 41.0)]
open('/work/archive/2025-03-15.tlm', 'wb').write(b''.join(struct.pack('<Ifff', *r) for r in recs))
PY
