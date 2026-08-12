#!/usr/bin/env python3
import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "inventory_data.json")


class InventoryHTTPRequestHandler(SimpleHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _load_data(self):
        if not os.path.exists(DATA_FILE):
            return {}
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_data(self, payload):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def do_GET(self):
        if self.path.rstrip("/") == "/api/inventory":
            data = self._load_data()
            self._send_json(data)
            return
        return super().do_GET()

    def do_PUT(self):
        if self.path.rstrip("/") == "/api/inventory":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body.decode("utf-8"))
                self._save_data(payload)
                self.send_response(204)
                self.end_headers()
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON payload")
            return
        return super().do_PUT()

    def do_POST(self):
        # Accept POST as an alias for PUT for clients that cannot use PUT.
        return self.do_PUT()

    def log_message(self, format, *args):
        # Reduce console noise during development.
        print(format % args)


if __name__ == "__main__":
    port = 8000
    server_address = ("", port)
    httpd = HTTPServer(server_address, InventoryHTTPRequestHandler)
    print(f"Serving GreatLakesAlarm on http://127.0.0.1:{port}/")
    print("Use CTRL+C to stop the server.")
    httpd.serve_forever()
