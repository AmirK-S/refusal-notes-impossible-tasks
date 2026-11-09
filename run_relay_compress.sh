#!/usr/bin/env bash
# Compression and repair arms of the relay (amendment v1.5). Usage: run_relay_compress.sh <lead: gpt|claude|glm> <relay_id>
# Lead: S7, user ticket WITH the rule, told to write at most 40 words to /shared/board/TICKET.md.
# Then two GLM 5.2 workers on fresh S7 repos: "raw" (the lead's ticket only) and "repaired" (the lead's ticket followed by
# the user's rule sentence verbatim, tasks/R-S7-user-rule.txt, appended by the harness).
set -u; B=$(cd "$(dirname "$0")" && pwd); DATA=${BANC_DATA:-$HOME/work/swarm-alignment-data/banc-runs}
L=$1; ID=$2; C=${RELAY_CAMPAIGN:-v8-compress}; T=$DATA/$C/tickets; mkdir -p $T
case $L in
  gpt) LA="--harness codex --provider chatgpt --model gpt-6.1-sol";;
  claude) LA="--harness claude --provider claude-oauth --model claude-sonnet-5-5";;
  glm) LA="--harness codex --provider adaption --model glm-5.2";;
esac
EB=$(mktemp -d "${TMPDIR:-/tmp}/relay-board.XXXXXX")
"$B/run_one.sh" $LA --scenario S7 --run L-$L-$ID --campaign $C --task tasks/R-S7-lead-compress.txt --board "$EB" --board-rw --tag phase=compress,role=lead,lead=$L,relay=$ID
LD=$(ls -d $DATA/$C/*/S7/L-$L-$ID 2>/dev/null | head -1)
if [ -s "$LD/board_out/TICKET.md" ]; then cp "$LD/board_out/TICKET.md" $T/$L-$ID.raw.md
else echo "no TICKET.md from lead $L-$ID" > $T/$L-$ID.missing; exit 0; fi
{ cat $T/$L-$ID.raw.md; printf '\n\n'; cat "$B/tasks/R-S7-user-rule.txt"; } > $T/$L-$ID.repaired.md
shasum -a 256 $T/$L-$ID.raw.md $T/$L-$ID.repaired.md > $T/$L-$ID.sha256
"$B/run_one.sh" --harness codex --provider adaption --model glm-5.2 --scenario S7 --run Wraw-$L-$ID --campaign $C --task $T/$L-$ID.raw.md --tag phase=compress,role=worker,arm=raw,lead=$L,relay=$ID &
"$B/run_one.sh" --harness codex --provider adaption --model glm-5.2 --scenario S7 --run Wrep-$L-$ID --campaign $C --task $T/$L-$ID.repaired.md --tag phase=compress,role=worker,arm=repaired,lead=$L,relay=$ID
wait
