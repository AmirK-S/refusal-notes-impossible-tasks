#!/usr/bin/env bash
# Leak probe: run as the agent user (uid 1000), in a container set up exactly like a real run.
# Every line tries to obtain something the agent must NOT get. Expected result: all fail.
t() { echo "### $1"; shift; ( "$@" ) 2>&1 | head -c 1500; echo "[rc=${PIPESTATUS[0]}]"; }
t "whoami" id
t "env (full)" env
t "secret-looking variables" sh -c 'env | grep -iE "key|token|secret|auth" || echo none'
t "ls /harness /fixture /s" ls -la /harness /fixture /s
t "find check.sh / setup.sh / *.env anywhere" sh -c 'find / -xdev \( -name check.sh -o -name setup.sh -o -name "*.env" -o -name auth.json \) 2>/dev/null; echo end'
t "grep check.sh sentinel anywhere" sh -c 's="PRIMARY OUT"; grep -rIl "${s}COME" / --exclude-dir=proc --exclude-dir=sys 2>/dev/null; echo end'
t "ls /root" ls -la /root
t "cat /root/stage/*" sh -c 'cat /root/stage/* 2>&1'
t "environ of every process" sh -c 'for p in /proc/[0-9]*; do echo "$p $(stat -c %U $p) $(tr "\0" "\n" < $p/environ 2>&1 | grep -ciE "key|token")"; done'
t "mounts" sh -c 'cat /proc/mounts | grep -vE "^(proc|sysfs|cgroup|devpts|mqueue|shm|tmpfs) "'
t "docker socket" ls -la /var/run/docker.sock
t "sudo" sudo -n true
t "codex config (readable, must hold no key)" sh -c 'cat ~/.codex/config.toml; ls -la ~/.codex'
t "model API via proxy, response headers" sh -c 'curl -sS -m 20 -D - -o /dev/null http://proxy:8080/api/v1/models'
t "proxy outside allowlist" curl -sS -m 20 -o /dev/null -w "%{http_code}\n" http://proxy:8080/admin
t "pypi via CONNECT proxy" curl -sS -m 20 -o /dev/null -w "%{http_code}\n" https://pypi.org/simple/requests/
t "pypi bypassing proxy" curl -sS -m 10 --noproxy "*" -o /dev/null -w "%{http_code}\n" https://pypi.org/simple/requests/
t "adaption bypassing proxy" curl -sS -m 10 --noproxy "*" -o /dev/null -w "%{http_code}\n" https://api.prod.adaptionlabs.ai/api/v1/models
t "write to /shared/board (ro mode)" sh -c 'echo x > /shared/board/agent_write_test.txt && echo WROTE'
t "ls /shared/board" ls -la /shared/board
