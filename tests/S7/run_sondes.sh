#!/usr/bin/env bash
# Plays every S7 probe (c*.sh, preflight.sh) through run_one.sh with the probe harness, 4 at a time.
# Usage (from the bench root): tests/S7/run_sondes.sh [campaign=tests-S7]
C=${1:-tests-S7}
ls tests/S7/c*.sh tests/S7/preflight.sh | xargs -P 4 -I{} sh -c 'n=$(basename {} .sh); ./run_one.sh --harness probe --provider adaption --model glm-5.2 --scenario S7 --run "${n%%_*}" --campaign '"$C"' --task {} --timeout 300 >/dev/null 2>&1; echo done $n'
