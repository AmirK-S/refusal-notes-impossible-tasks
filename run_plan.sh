#!/usr/bin/env bash
# Usage: run_plan.sh <plan.txt> [parallel=3]
# plan.txt: one run per line, the arguments of run_one.sh (lines starting with # are skipped), in the
# order wanted (interleave arms yourself). Paths in the plan (--board, --task) are relative to the bench root.
# Runs already done (exit.txt present) are skipped, so the plan can be relaunched after a crash.
# ChatGPT-login runs are serialized by run_one.sh's lock whatever N is.
# Frozen code: the plan runs from `git archive HEAD` exported to $BANC_DATA/.snapshots/<commit>/, so editing
# the working copy during a night cannot change runs in flight. The working tree must be clean.
# Overnight: caffeinate -i ./run_plan.sh plan.txt 3 > plan.log 2>&1 &
set -u; B=$(cd "$(dirname "$0")" && pwd); N=${2:-3}; PLAN=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
DATA=${BANC_DATA:-$HOME/work/swarm-alignment-data/banc-runs}
# BANC_ALLOW_DIRTY=1 skips the clean-tree check (several agents share the repo at night). The snapshot is
# still `git archive HEAD`: only committed content counts. Warning and commit go to the plan journal.
DIRTY=""
if [ -n "$(git -C "$B" status --porcelain -- . )" ]; then
  if [ "${BANC_ALLOW_DIRTY:-0}" = 1 ]; then DIRTY="dirty-tree-allowed (uncommitted changes are NOT in the snapshot)"
  else echo "working tree not clean: commit first (or BANC_ALLOW_DIRTY=1)"; exit 1; fi
fi
C=$(git -C "$B" rev-parse --short HEAD); SNAP=$DATA/.snapshots/$C
[ -n "$DIRTY" ] && echo "WARNING $DIRTY commit=$C"
[ -d "$SNAP" ] || { mkdir -p "$SNAP" && git -C "$B" archive HEAD | tar -x -C "$SNAP"; }
echo "PLAN START $(date -u +%FT%TZ) commit=$C plan=$PLAN parallel=$N ${DIRTY:+warning=\"$DIRTY\"}"
mkdir -p "$DATA"; echo "$(date -u +%FT%TZ) plan=$PLAN commit=$C parallel=$N ${DIRTY:+warning=$DIRTY}" >> "$DATA/plan-journal.log"
cd "$SNAP" && grep -v '^\s*#' "$PLAN" | grep -v '^\s*$' | BANC_COMMIT=$C BANC_DIRTY=${DIRTY:+yes} xargs -P "$N" -L 1 ./run_one.sh
echo "PLAN DONE $(date -u +%FT%TZ)"
