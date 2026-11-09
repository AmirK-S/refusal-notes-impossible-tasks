"""Reverse proxy that holds the model-API secret, so the agent container never does.

The agent's CLI is pointed at http://proxy:8080/<prefix> (plain HTTP on the run's --internal Docker
network). This process strips any Authorization / x-api-key the client sent, adds the real one read
from its own environment, and forwards to the upstream over HTTPS. Responses are streamed back
unchanged (SSE included). Only paths under --allow-prefix are forwarded; anything else gets 403.

Logs (one JSON object per line, never any header value):
  <log>: ts, method, path, status, seconds, req_bytes, resp_bytes, model, usage (from the response
         body: OpenAI Responses `response.usage`, or Anthropic message_start/message_delta usage).
  <dump-dir> (optional, debugging only): request bodies, for checking what the CLI sends.

Usage: python3 -I inject_proxy.py --listen 0.0.0.0:8080 --upstream https://api.prod.adaptionlabs.ai
         --allow-prefix /api/v1/ --secret-env ADAPTION_API_KEY --scheme bearer --log /plog/api.jsonl
       --scheme x-api-key | bearer ; --extra-header 'anthropic-beta: oauth-2025-04-20' (repeatable)
"""
import argparse, http.client, json, os, socketserver, ssl, sys, time, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

ap = argparse.ArgumentParser()
ap.add_argument("--listen", default="0.0.0.0:8080")
ap.add_argument("--upstream", required=True)
ap.add_argument("--allow-prefix", action="append", required=True)
ap.add_argument("--secret-env", required=True)
ap.add_argument("--scheme", choices=["bearer", "x-api-key"], default="bearer")
ap.add_argument("--extra-header", action="append", default=[])
ap.add_argument("--log", required=True)
ap.add_argument("--dump-dir")
A = ap.parse_args()
SECRET = os.environ.pop(A.secret_env, "")
if not SECRET:
    sys.exit(f"inject_proxy: {A.secret_env} is empty")
UP = urllib.parse.urlsplit(A.upstream)
CTX = ssl.create_default_context()
HOP = {"connection", "keep-alive", "proxy-connection", "transfer-encoding", "te", "trailer", "upgrade",
       "host", "authorization", "x-api-key", "content-length", "accept-encoding"}
N = [0]


def log(rec):
    with open(A.log, "a") as f:
        f.write(json.dumps(rec) + "\n")


def usage_of(buf, ctype):
    """Return (model, usage) from a complete response body (SSE or JSON)."""
    model, usage = None, None
    texts = []
    if "event-stream" in ctype:
        for line in buf.split(b"\n"):
            if line.startswith(b"data:"):
                texts.append(line[5:].strip())
    else:
        texts.append(buf)
    anth = {}
    for t in texts:
        try:
            d = json.loads(t)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        r = d.get("response") if isinstance(d.get("response"), dict) else d
        if isinstance(r.get("usage"), dict) and ("input_tokens" in r["usage"] or "prompt_tokens" in r["usage"]):
            usage, model = r["usage"], r.get("model", model)
        if d.get("type") == "message_start":
            m = d.get("message", {}); model = m.get("model", model); anth.update(m.get("usage", {}))
        if d.get("type") == "message_delta" and isinstance(d.get("usage"), dict):
            anth.update(d["usage"])
    if anth and usage is None:
        usage = anth
    return model, usage


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # close-delimited bodies: simplest correct streaming

    def log_message(self, *a):
        pass

    def deny(self, code=403, body=b"EGRESS_DENIED\n"):
        self.send_response(code); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)

    def handle_any(self):
        t0 = time.time(); path = self.path
        if not any(path.startswith(p) for p in A.allow_prefix):
            log({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "method": self.command, "path": path, "status": 403, "verdict": "DENY"})
            return self.deny()
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        if A.dump_dir:
            N[0] += 1
            open(os.path.join(A.dump_dir, f"req{N[0]:04d}.json"), "wb").write(body)
        hdrs = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        hdrs["Host"] = UP.netloc
        if A.scheme == "bearer":
            hdrs["Authorization"] = "Bearer " + SECRET
        else:
            hdrs["x-api-key"] = SECRET
        for h in A.extra_header:
            k, v = h.split(":", 1)
            old = hdrs.get(k.strip())
            hdrs[k.strip()] = (old + "," + v.strip()) if old and k.strip().lower() == "anthropic-beta" else v.strip()
        if body:
            hdrs["Content-Length"] = str(len(body))
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "method": self.command, "path": path, "req_bytes": len(body)}
        try:
            c = http.client.HTTPSConnection(UP.hostname, UP.port or 443, context=CTX, timeout=600)
            c.request(self.command, path, body=body or None, headers=hdrs)
            r = c.getresponse()
        except Exception as e:
            rec.update(status=502, error=repr(e)[:200], seconds=round(time.time() - t0, 2)); log(rec)
            return self.deny(502, b"UPSTREAM_ERROR\n")
        self.send_response(r.status)
        for k, v in r.getheaders():
            if k.lower() not in HOP:
                self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()
        buf = bytearray()
        try:
            while True:
                chunk = r.read1(65536) if hasattr(r, "read1") else r.read(65536)
                if not chunk:
                    break
                buf += chunk
                self.wfile.write(chunk); self.wfile.flush()
        except Exception as e:
            rec["stream_error"] = repr(e)[:200]
        model, usage = usage_of(bytes(buf), r.getheader("Content-Type") or "")
        rec.update(status=r.status, seconds=round(time.time() - t0, 2), resp_bytes=len(buf), model=model, usage=usage)
        if r.status >= 400:
            rec["error_body"] = bytes(buf[:400]).decode(errors="replace")
        log(rec)

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = handle_any


class S(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


host, port = A.listen.rsplit(":", 1)
log({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "method": "START", "upstream": A.upstream, "allow": A.allow_prefix})
S((host, int(port)), H).serve_forever()
