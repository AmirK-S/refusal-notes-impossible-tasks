"""Allowlisting HTTP(S) forward proxy for S3v2. Only CONNECT to <allowed host>:443 is relayed.
Everything else (other hosts, other ports, plain-HTTP requests) gets 403 with body EGRESS_DENIED.
Usage: python3 -I egress_proxy.py <port> <logfile> <host>[,<host>...]
Every request is logged as one line: ts \t client \t verb \t target \t ALLOW|DENY"""
import asyncio, sys, time
PORT, LOG, ALLOW = int(sys.argv[1]), sys.argv[2], set(sys.argv[3].split(","))
DENY = b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\nContent-Length: 14\r\nConnection: close\r\n\r\nEGRESS_DENIED\n"

def log(peer, verb, target, verdict):
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\t{peer}\t{verb}\t{target}\t{verdict}\n")

async def pipe(r, w):
    try:
        while (b := await r.read(65536)):
            w.write(b); await w.drain()
    except Exception: pass
    finally:
        try: w.close()
        except Exception: pass

async def handle(r, w):
    peer = w.get_extra_info("peername")[0]
    try:
        head = await r.readuntil(b"\r\n\r\n")
    except Exception:
        w.close(); return
    line = head.split(b"\r\n", 1)[0].decode(errors="replace")
    parts = line.split(" ")
    verb, target = (parts + ["", ""])[:2]
    host, _, port = target.rpartition(":") if verb == "CONNECT" else ("", "", "")
    if verb == "CONNECT" and host in ALLOW and port == "443":
        try:
            ur, uw = await asyncio.wait_for(asyncio.open_connection(host, 443), 20)
        except Exception as e:
            log(peer, verb, target, f"ALLOW_UPSTREAM_FAIL {e!r}")
            w.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n"); await w.drain(); w.close(); return
        log(peer, verb, target, "ALLOW")
        w.write(b"HTTP/1.1 200 Connection established\r\n\r\n"); await w.drain()
        await asyncio.gather(pipe(r, uw), pipe(ur, w))
    else:
        log(peer, verb, target, "DENY")
        w.write(DENY)
        try: await w.drain()
        except Exception: pass
        w.close()

async def main():
    srv = await asyncio.start_server(handle, "0.0.0.0", PORT)
    log("-", "START", ",".join(sorted(ALLOW)), "-")
    async with srv: await srv.serve_forever()
asyncio.run(main())
