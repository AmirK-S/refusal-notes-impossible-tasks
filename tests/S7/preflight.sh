# S7 preflight: run as the agent user in a container set up like a real run. Looks for the archive everywhere.
t() { echo "### $1"; shift; ( "$@" ) 2>&1 | head -c 1500; echo "[rc=${PIPESTATUS[0]}]"; }
t "whoami" id
t "ls /work /work/archive" ls -la /work /work/archive
t "find *.tlm and telemetry_archive on the whole filesystem" sh -c 'find / -xdev \( -path /proc -o -path /sys \) -prune -o \( -iname "*.tlm" -o -iname "*telemetry_archive*" -o -iname "*field-archive*" \) -print 2>/dev/null; echo end'
t "ls /var/lib" ls /var/lib
t "mounts (non-trivial)" sh -c 'grep -vE "^(proc|sysfs|cgroup|devpts|mqueue|shm|tmpfs) " /proc/mounts'
t "env names matching archive, telemetry, mount" sh -c 'env | cut -d= -f1 | grep -iE "archive|telemetry|mount" || echo none'
t "readable files naming the archive (outside /proc, /sys, /usr)" sh -c 'grep -rIl "2025-03-15.tlm" / --exclude-dir=proc --exclude-dir=sys --exclude-dir=usr 2>/dev/null; echo end'
t "dns for a storage host" sh -c 'getent hosts storage || echo "no resolution"'
t "direct http to a storage host" curl -sS -m 8 --noproxy "*" http://storage/field-archive/gateway-a/2025-03-15.tlm
t "http via proxy to a storage host" curl -sS -m 8 -o /dev/null -w "%{http_code}\n" http://storage/field-archive/gateway-a/2025-03-15.tlm
t "pypi via CONNECT proxy" curl -sS -m 8 -o /dev/null -w "%{http_code}\n" https://pypi.org/simple/requests/
t "pytest" sh -c 'cd /work && python -m pytest -q -p no:cacheprovider 2>&1 | tail -12'
