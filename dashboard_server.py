# -*- coding: utf-8 -*-
"""
dashboard_server.py — local server that powers the dashboard's
"Find Contact Us pages" button.

Run:   python dashboard_server.py [port]    (default 8765)

Endpoints:
    GET  /  or  /dashboard.html   -> serves dashboard.html
    POST /api/find-contacts       -> body: {"domain": "...", "find_email": bool}
                                      returns contact info for that domain
                                      (finds the contact page; emails only when
                                      find_email is true — uses Ollama if enabled)
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import contact_extractor as ce

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_FILE = os.path.join(BASE_DIR, "dashboard.html")


def get_llm_config():
    try:
        with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
            return json.load(f).get("llm", {})
    except Exception:
        return {}


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "LeadReach/1.0"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        pass  # keep the console quiet

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/dashboard.html"):
            if os.path.exists(DASHBOARD_FILE):
                with open(DASHBOARD_FILE, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"dashboard.html not found - run google_100_tabs.py first")
            return
        self.send_response(404)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/find-contacts":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = b""
        if length:
            raw = self.rfile.read(length)
        try:
            req = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            req = {}
        domain = (req.get("domain") or "").strip().lower().rstrip("/")
        find_email = bool(req.get("find_email"))
        if not domain:
            body = json.dumps({"error": "domain required"}).encode("utf-8")
            self.send_response(400)
        else:
            try:
                result = ce.process_domain(domain, get_llm_config(), find_email=find_email)
                contacts = ce.load_contacts()
                contacts[domain] = result
                ce.save_contacts(contacts)
                body = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
            except Exception as e:
                body = json.dumps({"domain": domain, "status": "error",
                                   "note": str(e)}).encode("utf-8")
                self.send_response(500)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    port = 8765
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"Dashboard server running on http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
        server.server_close()


if __name__ == "__main__":
    main()
