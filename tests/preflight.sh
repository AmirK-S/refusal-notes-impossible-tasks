#!/usr/bin/env bash
# Usage: tests/preflight.sh [scenario=S6]. Impossibility proof (V2 1.2): the attempts to obtain fxprovider, played as `agent`
# in the frozen image on the internal network of a run (same network, proxy and user as a real run). Output kept in
# $BANC_DATA/tests/preflight/ (checks.txt + the proxy's egress.log). Not run for S6F, where fxprovider is provided by the host.
set -u; B=$(cd "$(dirname "$0")/.." && pwd); DATA=${BANC_DATA:-$HOME/work/swarm-alignment-data/banc-runs}; S=${1:-S6}
R=preflight-$S-$(date +%s)
"$B/run_one.sh" --harness probe --provider adaption --model glm-5.2 --scenario "$S" --run "$R" --campaign tests \
   --task tests/preflight-probe.sh --timeout 600
RD=$DATA/tests/probe-glm-5.2/$S/$R; O=$DATA/tests/preflight; mkdir -p "$O"
cp "$RD/transcript.jsonl" "$O/checks-$S.txt"; cp "$RD/egress.log" "$O/egress-$S.log" 2>/dev/null; cp "$RD/run.json" "$O/run-$S.json"
echo "preflight kept in $O (run dir $RD)"
