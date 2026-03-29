#!/usr/bin/env python3
"""
Local dev server for Good Weekend app.
Serves static files AND proxies /api/messages → api.anthropic.com
so the browser avoids CORS preflight failures.
"""
import json
import ssl
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8080

class AppHandler(SimpleHTTPRequestHandler):

    # ── Proxy POST /api/messages → Anthropic ──────────────────────────────
    def do_POST(self):
        if self.path == '/api/messages':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)

            api_key = self.headers.get('x-api-key', '')
            anthropic_version = self.headers.get('anthropic-version', '2023-06-01')

            req = urllib.request.Request(
                'https://api.anthropic.com/v1/messages',
                data=body,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': api_key,
                    'anthropic-version': anthropic_version,
                    'anthropic-dangerous-allow-browser': 'true',
                },
                method='POST'
            )

            try:
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(req, context=ctx) as resp:
                    resp_body = resp.read()
                    self.send_response(resp.status)
                    self.send_header('Content-Type', 'application/json')
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(resp_body)
            except urllib.error.HTTPError as e:
                err_body = e.read()
                self.send_response(e.code)
                self.send_header('Content-Type', 'application/json')
                self._cors_headers()
                self.end_headers()
                self.wfile.write(err_body)
                print(f'[proxy] Anthropic error {e.code}: {err_body[:200]}')
            except Exception as ex:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self._cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(ex)}).encode())
                print(f'[proxy] Exception: {ex}')
        else:
            super().do_POST()

    # ── Handle CORS preflight ─────────────────────────────────────────────
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers',
                         'Content-Type, x-api-key, anthropic-version, anthropic-dangerous-allow-browser')

    # ── Suppress request logs (comment out to debug) ─────────────────────
    def log_message(self, fmt, *args):
        if '/api/' in (args[0] if args else ''):
            print(f'[proxy] {args}')
        # else silent for static files

if __name__ == '__main__':
    server = HTTPServer(('', PORT), AppHandler)
    print(f'✓ Good Weekend server running at http://localhost:{PORT}')
    print(f'  Serving:  static files from this directory')
    print(f'  Proxying: /api/messages → api.anthropic.com')
    print(f'  Press Ctrl+C to stop.\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
