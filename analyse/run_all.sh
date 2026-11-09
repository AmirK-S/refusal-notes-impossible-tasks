#!/usr/bin/env bash
# Recomputes every derived table, test, figure and the registry from the raw run folders. Idempotent: safe to rerun at any
# time, including while campaigns are running (runs without exit.txt are in flight: excluded from every count, listed apart).
# Usage (any directory): analyse/run_all.sh
#   BANC_DATA     raw runs           (default ~/work/swarm-alignment-data/banc-runs)   -- never written
#   BANC_DERIVE   derived outputs    (default ~/work/swarm-alignment-data/derive)
#   PY_FIG        python with matplotlib for the figures (default ~/work/swarm-alignment-data/.venv-analyse/bin/python)
#   FREEZE_AT     data freeze (deviation 17), ISO with offset, e.g. 2026-11-09T05:30:00+01:00: later exit.txt are not counted
#   CAMPAIGNS     default "v5-pos v5-base v5-def v5-explo v5-norule" (v5-norule: exploratory, deviation 10)
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
A=$(cd "$(dirname "$0")" && pwd); B=$(dirname "$A")
DATA=${BANC_DATA:-$HOME/work/swarm-alignment-data/banc-runs}
OUT=${BANC_DERIVE:-$HOME/work/swarm-alignment-data/derive}
PY_FIG=${PY_FIG:-$HOME/work/swarm-alignment-data/.venv-analyse/bin/python}
export FREEZE_AT=${FREEZE_AT:-2026-11-09T05:30:00+01:00}   # deviation 17: default freeze at 05:30 Paris time
CAMPAIGNS=${CAMPAIGNS:-"v5-pos v5-base v5-def v5-explo v5-norule"}
mkdir -p "$OUT"
LOCK="$OUT/.run_all.lock"
mkdir "$LOCK" 2>/dev/null || { echo "run_all.sh already running ($LOCK)"; exit 1; }
trap 'rmdir "$LOCK"' EXIT
echo "run_all $(date -u +%FT%TZ) data=$DATA out=$OUT commit=$(git -C "$B" rev-parse --short HEAD)"
python3 -I "$A/stats.py"
python3 -I "$A/violation_strict.py" --selftest
# 1. read-only mirror of the finished runs (extract_banc.py writes final_message.txt, judge/ and monitor/ there, not in the raw data)
python3 -I "$A/mirror.py" "$DATA" "$OUT/mirror" $CAMPAIGNS
# 2. extraction with extract_banc.py unchanged
rm -f "$OUT"/runs_*.csv "$OUT"/campaign.csv
MDIRS=""
for c in $CAMPAIGNS; do
  python3 -I "$B/extract_banc.py" "$OUT/mirror/$c" "$OUT/runs_$c.csv"
  MDIRS="$MDIRS $OUT/mirror/$c"
done
rm -f "$OUT/campaign.csv"
# 3. violation_strict (amendment v1.2 item 3), state (d) rules, descriptor audit material
python3 -I "$A/violation_strict.py" "$OUT/violation_strict.csv" $MDIRS
python3 -I "$A/infra.py" "$OUT/infra.csv" $MDIRS
rm -rf "$OUT/audit"; python3 -I "$A/audit_descriptors.py" "$OUT/mirror" "$OUT/audit" $CAMPAIGNS
# 4. tables, tests, mechanism, annex, registry (analyse/registre.csv)
python3 -I "$A/analyse.py" --derive "$OUT" --plans "$B/plans" --campaigns $CAMPAIGNS
# 5. figures
if [ -x "$PY_FIG" ] && "$PY_FIG" -c 'import matplotlib' 2>/dev/null; then
  rm -rf "$OUT/figures"; "$PY_FIG" -I "$A/figures.py" "$OUT"
else
  echo "WARNING: no python with matplotlib at $PY_FIG; figures not redrawn"
fi
cp "$A/registre.csv" "$OUT/registre.csv"
echo "run_all done $(date -u +%FT%TZ)"
