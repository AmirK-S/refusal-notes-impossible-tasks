#!/usr/bin/env bash
# Live two-agent relay (amendment v1.4). Usage: run_relay.sh <lead: gpt|claude|glm> <relay_id> [rule|norule]
# 1. lead: S7, ticket tasks/R-S7-lead.txt (user ticket quoted inside), empty board writable; it must write /shared/board/TICKET.md
# 2. worker: GLM 5.2 in Codex on a fresh S7 repo, whose whole task is the lead's TICKET.md (no other text, no board)
# Results: $BANC_DATA/v7-relay/... ; the lead's ticket is kept in $BANC_DATA/v7-relay/tickets/<lead>-<id>.md
set -u; B=$(cd "$(dirname "$0")" && pwd); DATA=${BANC_DATA:-$HOME/work/swarm-alignment-data/banc-runs}
L=$1; ID=$2; U=${3:-rule}; LT=tasks/R-S7-lead.txt; [ "$U" = norule ] && LT=tasks/R-S7-lead-norule.txt; C=${RELAY_CAMPAIGN:-v7-relay}; T=$DATA/$C/tickets; mkdir -p $T
case $L in
  gpt) LA="--harness codex --provider chatgpt --model gpt-6.1-sol";;
  claude) LA="--harness claude --provider claude-oauth --model claude-sonnet-5-5";;
  glm) LA="--harness codex --provider adaption --model glm-5.2";;
esac
EB=$(mktemp -d "${TMPDIR:-/tmp}/relay-board.XXXXXX")
"$B/run_one.sh" $LA --scenario S7 --run L-$L-$ID --campaign $C --task $LT --board "$EB" --board-rw --tag phase=relay,role=lead,lead=$L,user=$U,relay=$ID
LD=$(ls -d $DATA/$C/*/S7/L-$L-$ID 2>/dev/null | head -1)
if [ -s "$LD/board_out/TICKET.md" ]; then cp "$LD/board_out/TICKET.md" $T/$L-$ID.md
else echo "no TICKET.md from lead $L-$ID" > $T/$L-$ID.missing; exit 0; fi
"$B/run_one.sh" --harness codex --provider adaption --model glm-5.2 --scenario S7 --run W-$L-$ID --campaign $C --task $T/$L-$ID.md --tag phase=relay,role=worker,lead=$L,user=$U,relay=$ID
