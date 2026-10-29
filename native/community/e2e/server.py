"""Fake HoloNet for Wine tests: the routes the bridge calls, fixture data,
per-route delays from control.json ({"<path prefix>": seconds}), and a log."""
import json, random, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
HERE = Path(__file__).resolve().parent
F = HERE.parents[2]/'tests/fixtures/sharing'
STATE = Path(sys.argv[1])  # control.json and http.log live here
gallery = json.loads((F/'holonet-gallery-page.json').read_text())
listing, docs = {}, {}
for name in ['base', 'pack']:
    raw = (F/f'holonet-composition-{name}.listing.json').read_bytes()
    code = json.loads(raw)['item']['code']
    listing[code] = raw
    docs[code] = (F/f'holonet-composition-{name}.json').read_bytes()
GOOD = 'Bearer zcu_' + 'a'*64
UPLOAD = '11111111-2222-4333-8444-555555555555'
log = open(STATE/'http.log', 'a')
class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def reply(self, code, body=b'', kind='application/json; charset=utf-8'):
        if self.garbage and body:  # fuzzing: damage the reply
            r = random.Random(); b = bytearray(body); choice = r.randrange(6)
            if choice == 0: b = b[:r.randrange(len(b))]
            elif choice == 1: b = bytearray(b'[' * r.randrange(20, 5000) + b'1' + b']' * r.randrange(0, 50))
            elif choice == 2: b = bytearray(r.randbytes(r.randrange(1, 3000)))
            elif choice == 3: b = bytearray(json.dumps({'items': [{'code': 'H7854VMD', 'title': 'x' * 70000}]}).encode())
            else:
                for _ in range(r.randrange(1, 40)): b[r.randrange(len(b))] = r.choice(b'{}[]",:\\0\x00\xff\xc3 9-eE.')
            body = bytes(b)
        self.send_response(code); self.send_header('Content-Type', kind); self.send_header('Content-Length', str(len(body))); self.end_headers()
        if self.trickle:  # one byte every few seconds: each read beats WinHTTP's timeout, the total does not
            for i in range(len(body)):
                try: self.wfile.write(body[i:i+1]); self.wfile.flush()
                except OSError: return
                time.sleep(self.trickle)
        else: self.wfile.write(body)
    def delay(self, path):
        try: control = json.loads((STATE/'control.json').read_text())
        except Exception: control = {}
        self.trickle = 0; self.garbage = control.pop('garbage', 0)
        for prefix, seconds in control.items():
            if path.startswith(prefix):
                if isinstance(seconds, dict): self.trickle = seconds['trickle']
                else: time.sleep(seconds)
    def handle_any(self, method):
        u = urlparse(self.path); q = parse_qs(u.query); p = u.path
        length = int(self.headers.get('Content-Length') or 0); body = self.rfile.read(length) if length else b''
        auth = self.headers.get('Authorization', '')
        log.write(json.dumps({'t': round(time.time(), 2), 'method': method, 'path': self.path, 'auth': 'good' if auth == GOOD else ('other' if auth else ''), 'bytes': len(body), 'body': body.decode('utf-8', 'replace') if method == 'POST' and len(body) < 4000 else ''}) + '\n'); log.flush()
        self.delay(p)
        parts = p.split('/')
        if method == 'GET' and p == '/api/v1/compositions':
            page = dict(gallery); page['page'] = int(q['page'][0]); page['pages'] = 3; page['total'] = 17
            return self.reply(200, json.dumps(page, ensure_ascii=False, separators=(',', ':')).encode())
        if method == 'GET' and len(parts) == 5 and parts[3] == 'comp' and parts[4] in listing: return self.reply(200, listing[parts[4]])
        if method == 'GET' and len(parts) == 6 and parts[5] == 'document' and parts[4] in docs: return self.reply(200, docs[parts[4]])
        if p.startswith('/api/v1/game/') or p.startswith('/api/v1/my/') or p.startswith('/api/v1/composition-uploads'):
            if auth != GOOD: return self.reply(401, b'{"error":{"code":"UNAUTHORIZED"}}')
        if method == 'GET' and p == '/api/v1/game/profile':
            return self.reply(200, json.dumps({'user_id': '11111111-1111-4111-8111-111111111111', 'display_name': 'Rook’s den', 'publishing': 'beta-publishing'}, separators=(',', ':')).encode())
        if method == 'GET' and p == '/api/v1/my/listings':
            items = [{'code': 'H7854VMD', 'title': 'Lamp corner', 'revision': 2, 'latest_revision': 2, 'import_count': 5, 'visibility': 'public', 'updated_at': '2026-10-29T02:23:35.000Z'},
                     {'code': 'T93765D1', 'title': 'Hidden one', 'revision': 1, 'import_count': 0, 'visibility': 'hidden', 'updated_at': '2026-10-28T02:23:35.000Z'}]
            return self.reply(200, json.dumps({'api_version': 'v1', 'items': items, 'page': int(q['page'][0]), 'pages': 1, 'total': 2}, separators=(',', ':')).encode())
        if method == 'POST' and p == '/api/v1/composition-uploads':
            # Spaced JSON on purpose: the bridge must not depend on formatting.
            return self.reply(201, json.dumps({'upload': {'id': UPLOAD, 'code': 'PUBTEST1', 'status': 'staging'}}, indent=1).encode())
        if p.startswith('/api/v1/composition-uploads/' + UPLOAD):
            rest = p[len('/api/v1/composition-uploads/' + UPLOAD):]
            if method == 'PUT' and rest in ('/payload', '/thumbnail'): return self.reply(200, b'{}')
            if method == 'POST' and rest == '/finalize': return self.reply(200, json.dumps({'upload': {'id': UPLOAD, 'code': 'PUBTEST1', 'status': 'published'}}, separators=(',', ':')).encode())
            if method == 'DELETE' and rest == '': return self.reply(200, b'{}')
        return self.reply(404, b'{"error":{"code":"NOT_FOUND"}}')
    def handle(self):
        try: super().handle()
        except (BrokenPipeError, ConnectionResetError): pass  # the bridge hung up on a reply it refused
    def do_GET(self): self.handle_any('GET')
    def do_POST(self): self.handle_any('POST')
    def do_PUT(self): self.handle_any('PUT')
    def do_DELETE(self): self.handle_any('DELETE')
    def log_message(self, *a): pass
ThreadingHTTPServer(('127.0.0.1', 18080), H).serve_forever()
