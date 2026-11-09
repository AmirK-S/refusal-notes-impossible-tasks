#!/usr/bin/env bash
# Runs as root inside the AGENT container, only to drop privileges. Copied by run_one.sh into
# /root/stage (root-only, mode 700): the agent user cannot read this file, the task copy or the CLI config
# staging. No setup.sh, no check.sh, no secret is ever copied into this container.
# /root/stage holds: harness, model, timeout, board_mode (none|ro|rw), task.txt, cfg/ (CLI config).
set -u
ST=/root/stage
H=$(cat $ST/harness); MODEL=$(cat $ST/model); TO=$(cat $ST/timeout); BM=$(cat $ST/board_mode)
chown -R agent:agent /work
[ -s $ST/prov ] && while read p; do chown -R root:root "$p"; chmod -R go-w "$p"; done < $ST/prov   # host-provisioned packages: not writable by the agent
mkdir -p /var/log/agent-hooks && : > /var/log/agent-hooks/toolcalls.jsonl && chown -R agent:agent /var/log/agent-hooks
case $BM in
  ro) chown -R root:root /shared && chmod -R u=rwX,go=rX /shared ;;           # agent can list and read, not write
  rw) chown root:root /shared && chmod 755 /shared && chown -R agent:agent /shared/board ;;  # harvest variant
esac
AH=/home/agent
case $H in
  codex|probe)
    mkdir -p $AH/.codex/rules
    cp $ST/cfg/config.toml $AH/.codex/config.toml
    [ -f $ST/cfg/default.rules ] && cp $ST/cfg/default.rules $AH/.codex/rules/default.rules
    chown -R agent:agent $AH/.codex; chmod 700 $AH/.codex
    # chatgpt mode only: read-only copy, root-owned (the CLI runs as the agent, so it stays readable: documented limit)
    [ -f $ST/cfg/auth.json ] && cp $ST/cfg/auth.json $AH/.codex/auth.json && chown root:root $AH/.codex/auth.json && chmod 444 $AH/.codex/auth.json ;;
  claude)
    mkdir -p $AH/.claude
    cp $ST/cfg/settings.json $AH/.claude/banc-settings.json
    chown -R agent:agent $AH/.claude ;;
esac
rm -rf $ST/cfg
touch -d "@$(( $(date +%s) - 1 ))" /root/.banc_start   # 1 s early: docker commit truncates mtimes to the second
date -u +%FT%T.%3NZ > $ST/start
PX=http://proxy:3128
BASEENV="HOME=$AH USER=agent LOGNAME=agent SHELL=/bin/bash PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 TERM=dumb
 TOOLLOG=/var/log/agent-hooks/toolcalls.jsonl HTTPS_PROXY=$PX HTTP_PROXY=$PX https_proxy=$PX http_proxy=$PX
 NO_PROXY=localhost,127.0.0.1,proxy no_proxy=localhost,127.0.0.1,proxy"
EXTRA=$(cat $ST/agent_env 2>/dev/null)   # non-secret extra variables (e.g. ANTHROPIC_BASE_URL)
DROP="setpriv --reuid=1000 --regid=1000 --init-groups env -i $BASEENV $EXTRA"
TASK=$(cat $ST/task.txt)
cd /work
case $H in
  codex)
    timeout "$TO" $DROP CODEX_HOME=$AH/.codex codex exec -m "$MODEL" --json --skip-git-repo-check --dangerously-bypass-hook-trust "$TASK" < /dev/null ;;
  probe)   # test harness: the "task" is a bash script, run as the agent user (tests/probe.sh, tests/cheats/*.sh)
    timeout "$TO" $DROP bash -c "$TASK" ;;
  claude)
    timeout "$TO" $DROP claude -p "$TASK" --model "$MODEL" --settings $AH/.claude/banc-settings.json --max-turns 25 \
      --output-format stream-json --verbose < /dev/null ;;
esac
echo "exit=$?" > $ST/exit
date -u +%FT%T.%3NZ > $ST/end
