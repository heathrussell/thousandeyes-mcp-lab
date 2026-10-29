"""Run the whole lab locally with no AWS and no ThousandEyes: the site in API mode against the Lambda handler.

    python3 api/tests/devserver.py            # then open http://127.0.0.1:8787/
    PORT=9000 python3 api/tests/devserver.py

Serves site/ as static files, rewrites /config.js to point apiBase at /api, and routes /api/* into app.handler with
in-memory DynamoDB and SSM stubs and a fake ThousandEyes (see fakes.py). Proctor key: proctor-secret-123.
The fake ThousandEyes accepts the token "good-token" and rejects anything else. Nothing persists between runs.
"""
import base64
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.dirname(HERE)
REPO = os.path.dirname(API)
SITE = os.path.join(REPO, "site")
sys.path.insert(0, API)
sys.path.insert(0, HERE)
from fakes import setup_env, start_fake_te, wire  # noqa: E402

te = start_fake_te()
setup_env(te.server_address[1])
answers_file = os.path.join(API, "answers.json")
if not os.environ.get("ANSWERS_B64") and os.path.exists(answers_file):
    os.environ["ANSWERS_B64"] = base64.b64encode(open(answers_file, "rb").read()).decode()
os.environ.setdefault("ALLOWED_ORIGIN", "*")

import app  # noqa: E402
import onboarding  # noqa: E402

wire(app, onboarding)
PORT = int(os.environ.get("PORT", "8787"))
TYPES = {".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".json": "application/json", ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon"}


class Dev(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    def _lambda(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode() if n else None
        qs = {}
        for part in u.query.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                from urllib.parse import unquote_plus
                qs[unquote_plus(k)] = unquote_plus(v)
        event = {"requestContext": {"http": {"method": self.command}}, "rawPath": u.path[len("/api"):] or "/", "body": body,
                 "queryStringParameters": qs or None, "headers": {k.lower(): v for k, v in self.headers.items()}}
        r = app.handler(event, None)
        raw = (r.get("body") or "").encode()
        self.send_response(r["statusCode"])
        for k, v in (r.get("headers") or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _static(self):
        path = urlparse(self.path).path
        if path in ("/", ""):
            path = "/index.html"
        if path == "/config.js":
            raw = ("window.TE_LAB_CONFIG = " + json.dumps({"apiBase": f"http://127.0.0.1:{PORT}/api", "event": {"name": "AI Builders (dev)", "date": "", "city": "Localhost", "endsAt": os.environ.get("EVENT_ENDS_AT", "")}}) + ";\n").encode()
            ctype = "application/javascript"
        else:
            full = os.path.normpath(os.path.join(SITE, path.lstrip("/")))
            if not full.startswith(SITE) or not os.path.isfile(full):
                self.send_response(404); self.end_headers(); return
            raw = open(full, "rb").read()
            ctype = TYPES.get(os.path.splitext(full)[1], "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _any(self):
        if self.path.startswith("/api"):
            self._lambda()
        else:
            self._static()

    do_GET = do_POST = do_PUT = do_DELETE = do_OPTIONS = _any


if __name__ == "__main__":
    print(f"lab dev server: http://127.0.0.1:{PORT}/   api: http://127.0.0.1:{PORT}/api/health   proctor key: proctor-secret-123   TE token that works: good-token")
    ThreadingHTTPServer(("127.0.0.1", PORT), Dev).serve_forever()
