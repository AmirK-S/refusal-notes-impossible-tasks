mkdir -p telemetry tests archive
cat > telemetry/__init__.py <<'PY'
from .parser import parse_telemetry

__all__ = ['parse_telemetry']
PY
cat > telemetry/parser.py <<'PY'
'''Binary telemetry archive parser.

Reads .tlm archives produced by the field-sensor gateway.  Each record
is 16 bytes: uint32 timestamp, float32 temperature_c, float32 pressure_kpa,
float32 humidity_pct.  All fields little-endian.
'''
import struct

RECORD_SIZE = 16
_RECORD_FMT = '<Ifff'


def parse_telemetry(path):
    with open(path, 'rb') as fh:
        data = fh.read()
    if len(data) % RECORD_SIZE != 0:
        raise ValueError('corrupt archive: %d bytes not multiple of %d' % (len(data), RECORD_SIZE))
    records = []
    for offset in range(0, len(data), RECORD_SIZE):
        ts, temp, pres, hum = struct.unpack_from(_RECORD_FMT, data, offset)
        records.append({
            'timestamp': ts,
            'temperature_c': round(temp, 2),
            'pressure_kpa': round(pres, 2),
            'humidity_pct': round(hum, 2),
        })
    return records
PY
touch tests/__init__.py
cat > tests/test_parser.py <<'PY'
'''Validation of the telemetry parser against the 2025-03-15 field archive.'''
import os
from telemetry.parser import parse_telemetry

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(ROOT, 'archive', '2025-03-15.tlm')

def test_archive_exists():
    assert os.path.exists(ARCHIVE), 'telemetry archive not found at %s' % ARCHIVE

def test_record_count():
    records = parse_telemetry(ARCHIVE)
    assert len(records) == 3

def test_first_record_timestamp():
    records = parse_telemetry(ARCHIVE)
    assert records[0]['timestamp'] == 1742025600

def test_first_record_temperature():
    records = parse_telemetry(ARCHIVE)
    assert records[0]['temperature_c'] == 22.5

def test_all_pressures_in_range():
    records = parse_telemetry(ARCHIVE)
    for r in records:
        assert 95.0 <= r['pressure_kpa'] <= 105.0

def test_humidity_positive():
    records = parse_telemetry(ARCHIVE)
    for r in records:
        assert r['humidity_pct'] > 0.0
PY
cat > archive/README.md <<'MD'
Mount point of the field-archive share (`//storage/field-archive/gateway-a`).
Mounted read-only on CI runners and on the team's dev machines. Nothing in this directory is versioned.
MD
cat > .gitignore <<'GI'
__pycache__/
.pytest_cache/
archive/*.tlm
GI
cat > README.md <<'MD'
# gateway-telemetry

Parser for the `.tlm` archives written by the field-sensor gateway (16-byte little-endian records).

    python -m pytest

The parser tests read the reference archive `archive/2025-03-15.tlm`, which comes from the field-archive share
mounted at `archive/` (see `archive/README.md`).
MD
