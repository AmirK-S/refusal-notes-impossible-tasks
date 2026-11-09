# Runs as the agent user (uid 1000) in the frozen image, on the internal network of a real run (probe harness).
t() { echo; echo "### $1"; shift; ( "$@" ) 2>&1 | head -c 1500; echo "[rc=${PIPESTATUS[0]}]"; }
echo "date: $(date -u +%FT%TZ)"; id
t "pip install fxprovider" timeout 90 pip install fxprovider
t "pip index versions fxprovider" timeout 90 pip index versions fxprovider
t "pip download fxprovider (no proxy env)" env -u HTTPS_PROXY -u HTTP_PROXY -u https_proxy -u http_proxy timeout 60 pip download fxprovider --no-deps -d /tmp/x
t "curl pypi simple, proxy env (HTTP code)" curl -sS -m 20 -o /dev/null -w "%{http_code}\n" https://pypi.org/simple/fxprovider/
t "curl pypi simple, proxy env (headers)" curl -sS -m 20 -I https://pypi.org/simple/fxprovider/
t "curl pypi simple, bypassing proxy" curl -sS -m 20 --noproxy "*" -o /dev/null -w "%{http_code}\n" https://pypi.org/simple/fxprovider/
t "curl pypi by IP, bypassing proxy" curl -sS -m 15 --noproxy "*" -k -o /dev/null -w "%{http_code}\n" https://151.101.0.223/
t "DNS: getent hosts pypi.org" getent hosts pypi.org
t "DNS: getent hosts files.pythonhosted.org" getent hosts files.pythonhosted.org
t "DNS: python socket.getaddrinfo" python3 -c "import socket;print(socket.getaddrinfo('pypi.org',443))"
t "routes" cat /proc/net/route
t "import fxprovider" python3 -c "import fxprovider"
t "find fxprovider on disk" sh -c 'find / -xdev -iname "*fxprovider*" 2>/dev/null; echo end'
