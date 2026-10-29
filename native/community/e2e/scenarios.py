"""End-to-end checks of the single-DLL bridge in a Wine host against the fake
HoloNet. Run through run.sh: bash native/community/e2e/run.sh [name ...]"""
import json, os, sys, time, traceback
from bridge import *
ROUNDS = int(os.environ.get('DD_E2E_ROUNDS', '1'))  # multiplies the fuzz runs
GOOD = b'zcu_' + b'a'*64
BAD = b'zcu_' + b'b'*64
PNG = bytes([137,80,78,71,13,10,26,10,0,0,0,13,73,72,68,82,0,0,0,1,0,0,0,1,8,6,0,0,0,31,21,196,137,0,0,0,13,73,68,65,84,120,156,99,248,223,224,240,31,0,7,0,2,191,43,215,199,226,0,0,0,0,73,69,78,68,174,66,96,130])
PAYLOAD = json.dumps({'payload': {'entries': [{'Mesh': '/Game/Props/SM_Lamp.SM_Lamp', 'Materials': ['']}]}}, separators=(',', ':'))
def publish_wire(title='Café lamp', update=None, changelog=''):
    THUMBS.mkdir(parents=True, exist_ok=True); (THUMBS/'Composition_0123abcd_512.png').write_bytes(PNG)
    lines = ['Composition_0123abcd_512.png', 'title\t' + title, 'description\tLine one\\nLine two']
    if update: lines.append('update\t%s\t%d' % update)
    lines += ['changelog\t' + changelog, 'payload', PAYLOAD]
    return '\n'.join(lines).encode('utf-8')
def control(d): (E/'control.json').write_text(json.dumps(d))
def http_log(): return [json.loads(l) for l in (E/'http.log').read_text().splitlines()] if (E/'http.log').exists() else []
def mark(): return len(http_log())
def since(m): return http_log()[m:]
results = []
def check(name, ok, detail=''):
    results.append((name, ok)); print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else '  ' + str(detail)[:600]), flush=True)
def expect(name, got, *needles):
    wire, secs = got; text = message(wire) if wire else None
    check(f'{name} ({secs}s)', text is not None and all(n in text for n in needles), text)
    return text

def browse():
    b = Bridge()
    try:
        expect('gallery page', b.ask(b'CATALOG/0', b'newest\tall\t'), 'gallery\t0\t3\t17', 'card\tH7854VMD')
        m = mark(); expect('search with non-ASCII text', b.ask(b'CATALOG/1', 'imports\tbase\tcafé ☃'.encode('utf-8')), 'gallery\t1')
        check('search reached the server encoded', any('q=caf%C3%A9' in r['path'] and 'sort=imports' in r['path'] and 'base_game=1' in r['path'] and 'page=2' in r['path'] for r in since(m)), since(m))
        expect('preview a build', b.ask(b'PREVIEW/H7854VMD', b'1'), 'part\t/Game/')
        expect('import with a pack and unknown mod', b.ask(b'DOWNLOAD/T93765D1', b'1'), 'Uses prop packs', 'count\t3')
        expect('unknown code', b.ask(b'PREVIEW/ZZZZZZZZ', b'1'), 'No HoloNet build has that code')
        expect('copy link', b.ask(b'COPYURL/H7854VMD'), 'Copied the HoloNet link')
        check('game still running', b.alive())
    finally: b.stop()
def connection():
    KEYFILE.unlink(missing_ok=True)
    b = Bridge()
    try:
        expect('connect with nothing remembered', b.ask(b'CONNECT'), 'No remembered connection')
        expect('my shares before connecting', b.ask(b'MYSHARES/0'), 'Not connected')
        expect('share before connecting', b.ask(b'PUBLISH', publish_wire()), 'Not connected')
        expect('wrong key', b.ask(b'AUTH', b'0\t' + BAD), 'Key invalid')
        check('wrong key not saved', not KEYFILE.exists())
        expect('right key, remembered', b.ask(b'AUTH', b'1\t' + GOOD), 'Connected as Rook’s den', 'Remembered connection')
        check('key file saved', KEYFILE.exists() and KEYFILE.read_bytes()[:68] == GOOD)
        check('AUTH request removed after reply', not REQUEST.exists())
        m = mark()
        expect('my shares page', b.ask(b'MYSHARES/0'), 'shares\t0', 'share\tH7854VMD\tLamp corner\t2\t5\tpublic', 'share\tT93765D1\tHidden one\t1\t0\thidden')
        check('my shares asked for page 1 with the key', any(r['path'].startswith('/api/v1/my/listings?page=1&per_page=8') and r['auth'] == 'good' for r in since(m)), since(m))
        m = mark()
        expect('share a new build', b.ask(b'PUBLISH', publish_wire()), 'Published: https://127.0.0.1/comp/PUBTEST1')
        steps = [(r['method'], r['path'].rsplit('/', 1)[-1]) for r in since(m)]
        check('share made 4 calls in order', steps == [('POST', 'composition-uploads'), ('PUT', 'payload'), ('PUT', 'thumbnail'), ('POST', 'finalize')], steps)
        begin = [r for r in since(m) if r['path'] == '/api/v1/composition-uploads']
        check('share text sent as UTF-8 JSON, no changelog for new', begin and json.loads(begin[0]['body']) == {'title': 'Café lamp', 'description': 'Line one\nLine two'}, begin)
        m = mark()
        expect('update a share with What changed', b.ask(b'PUBLISH', publish_wire('Lamp v2', ('H7854VMD', 2), 'Brighter')), 'Published:')
        begin = [r for r in since(m) if r['path'] == '/api/v1/composition-uploads']
        check('update body', begin and json.loads(begin[0]['body']) == {'title': 'Lamp v2', 'description': 'Line one\nLine two', 'code': 'H7854VMD', 'base_revision': 2, 'changelog': 'Brighter'}, begin)
        expect('disconnect', b.ask(b'DISCONNECT'), 'Disconnected for this session')
        expect('my shares after disconnect', b.ask(b'MYSHARES/0'), 'Not connected')
        check('remembered key kept on disconnect', KEYFILE.exists())
        expect('connect with remembered key', b.ask(b'CONNECT'), 'Connected as', 'Remembered connection')
        expect('forget', b.ask(b'FORGET'), 'Forgot connection')
        check('key file removed', not KEYFILE.exists())
        expect('my shares after forget', b.ask(b'MYSHARES/0'), 'Not connected')
        expect('key for this session only', b.ask(b'AUTH', b'0\t' + GOOD), 'Connected as')
        check('session key not saved', not KEYFILE.exists())
        check('game still running', b.alive())
        check('key never in log', 'zcu_' not in b.log())
    finally: b.stop()
def restart_reconnects():
    KEYFILE.write_bytes(GOOD)
    m = mark(); b = Bridge()
    try:
        time.sleep(3)
        check('reconnects at launch with remembered key', any(r['path'] == '/api/v1/game/profile' and r['auth'] == 'good' for r in since(m)), since(m))
        expect('my shares right away', b.ask(b'MYSHARES/0'), 'share\tH7854VMD')
    finally: b.stop(); KEYFILE.unlink(missing_ok=True)
def offline():
    b = Bridge()
    try:
        control({'/api/v1/compositions': 9})  # longer than the 6 s response timeout
        expect('server too slow for one step', b.ask(b'CATALOG/0', b'newest\tall\t'), 'offline')
    finally: control({}); b.stop()
def deadline():
    b = Bridge()
    try:
        control({'/api/v1/compositions': {'trickle': 2}})  # every read is quick, the whole reply is not
        wire, secs = b.ask(b'CATALOG/0', b'newest\tall\t', seconds=40)
        check(f'25-second deadline ({secs}s)', wire is not None and 'answer in time' in message(wire) and 24 <= secs <= 28, (secs, wire))
        control({})
        wire, secs = b.ask(b'CATALOG/0', b'newest\tall\t', seconds=20)
        check(f'next request after a timeout ({secs}s)', wire is not None and 'gallery' in message(wire) and secs < 5, (secs, wire))
    finally: control({}); b.stop()
def cancel_and_replace():
    b = Bridge()
    try:
        control({'/api/v1/compositions': {'trickle': 2}})
        b.send(b'CATALOG/0', b'newest\tall\t'); time.sleep(3); REQUEST.unlink()
        time.sleep(4); check('deleted request gets no reply', not RESPONSE.exists())
        b.send(b'CATALOG/0', b'newest\tall\tlamp'); time.sleep(3)
        control({})
        wire, secs = b.ask(b'CATALOG/2', b'newest\tall\t', seconds=20)
        check(f'replacement answered, not the old one ({secs}s)', wire is not None and 'gallery\t2' in message(wire) and secs < 5, (secs, wire))
        time.sleep(4)
        wire2 = message(wire_of(RESPONSE.read_bytes()))
        check('dropped request never overwrote the reply', 'gallery\t2' in wire2, wire2)
    finally: control({}); b.stop()
def connection_deadline():
    b = Bridge()
    try:
        control({'/api/v1/game/profile': {'trickle': 2}})
        wire, secs = b.ask(b'AUTH', b'0\t' + GOOD, seconds=40)
        check(f'connect deadline ({secs}s)', wire is not None and 'answer in time' in message(wire) and 24 <= secs <= 28, (secs, wire))
        control({})
        expect('my shares after a timed-out connect', b.ask(b'MYSHARES/0'), 'Not connected')
        expect('connect again', b.ask(b'AUTH', b'0\t' + GOOD, seconds=20), 'Connected as')
        control({'/api/v1/composition-uploads/': {'trickle': 2}})
        m = mark(); b.send(b'PUBLISH', publish_wire()); time.sleep(4); REQUEST.unlink(); time.sleep(8)
        steps = [(r['method'], r['path'].rsplit('/', 1)[-1]) for r in since(m)]
        check('cancelled share deletes its upload', ('DELETE', '11111111-2222-4333-8444-555555555555') in steps, steps)
        control({})
        expect('share after a cancelled share', b.ask(b'PUBLISH', publish_wire(), seconds=30), 'Published:')
    finally: control({}); b.stop()
def faults():
    for point, operation, wire in [('worker', b'CATALOG/0', b'newest\tall\t'), ('mailbox', b'CATALOG/0', b'newest\tall\t'), ('task', b'AUTH', b'0\t' + GOOD), ('poll', b'PUBLISH', None)]:
        b = Bridge(fault=point)
        try:
            if point == 'poll':
                expect(f'[{point}] connect first', b.ask(b'AUTH', b'0\t' + GOOD), 'Connected as')
                wire = publish_wire()
            got = b.ask(operation, wire, seconds=10)
            expect(f'[{point}] crashed request answered', got, 'Restart the game')
            expect(f'[{point}] later requests answered', b.ask(b'CATALOG/3', b'newest\tall\t', seconds=10), 'Restart the game')
            time.sleep(1)
            check(f'[{point}] game still running', b.alive())
            check(f'[{point}] crash logged', 'internal error' in b.log(), b.log())
        finally: b.stop()
ALL = [browse, connection, restart_reconnects, offline, deadline, cancel_and_replace, connection_deadline, faults]
def stress():
    b = Bridge()
    try:
        for i in range(60):
            b.send(b'CATALOG/%d' % (i % 9), b'newest\tall\tpage %d' % i); time.sleep(0.05 if i % 3 else 0.2)
        wire, secs = b.answer(20)
        check(f'last of 60 rapid requests answered ({secs}s)', wire is not None and 'gallery\t%d' % (59 % 9) in message(wire), wire)
        for i in range(20):
            b.send(b'AUTH' if i % 2 else b'MYSHARES/0', (b'0\t' + GOOD) if i % 2 else b'request'); time.sleep(0.07)
        wire, secs = b.answer(20)
        check(f'connection survives rapid requests ({secs}s)', wire is not None and ('Connected' in message(wire) or 'shares' in message(wire) or 'Not connected' in message(wire)), wire)
        expect('my shares afterwards', b.ask(b'MYSHARES/0', seconds=30), 'shares\t0')
        check('no crash caught', 'internal error' not in b.log(), b.log()[-500:])
        check('game still running', b.alive())
    finally: b.stop()
def mailbox_fuzz():
    import random
    r = random.Random(int(os.environ.get('DD_E2E_SEED', '7'))); b = Bridge()
    try:
        seeds = [make(b'CATALOG/0', b'newest\tall\tlamp')[0], make(b'PUBLISH', publish_wire())[0], make(b'AUTH', b'1\t' + GOOD)[0], make(b'MYSHARES/0', b'request')[0], make(b'PREVIEW/H7854VMD', b'1')[0], make(b'CATALOG/0', 'newest\tall\tcafé'.encode())[0]]
        for i in range(400 * ROUNDS):
            raw = bytearray(r.choice(seeds)); kind = r.randrange(4)
            if kind == 0:
                for _ in range(r.randrange(1, 12)): raw[r.randrange(len(raw))] = r.randrange(256)
            elif kind == 1: raw = raw[:r.randrange(len(raw))]
            elif kind == 2:
                at = r.randrange(len(raw)); raw[at:at+4] = r.choice([b'\xff\xff\xff\x7f', b'\x00\x00\x00\x80', b'\xff\xff\xff\xff', b'\x00\x00\x01\x00'])
            else: raw = raw + bytes(r.randrange(256) for _ in range(r.randrange(1, 5000)))
            REQUEST.write_bytes(bytes(raw)); time.sleep(0.03)
        time.sleep(1)
        check(f'{400 * ROUNDS} damaged mailbox files: no crash caught', 'internal error' not in b.log(), b.log()[-800:])
        expect('still answering afterwards', b.ask(b'CATALOG/0', b'newest\tall\t', seconds=30), 'gallery')
        check('game still running', b.alive())
    finally: b.stop()
def server_fuzz():
    b = Bridge()
    try:
        expect('connect', b.ask(b'AUTH', b'0\t' + GOOD), 'Connected as')
        control({'garbage': 1}); answered = 0
        for i in range(60 * ROUNDS):
            op = [(b'CATALOG/0', b'newest\tall\t'), (b'PREVIEW/H7854VMD', b'1'), (b'DOWNLOAD/T93765D1', b'1'), (b'MYSHARES/0', b'request'), (b'PUBLISH', publish_wire())][i % 5]
            wire, secs = b.ask(*op, seconds=30); answered += wire is not None
        control({})
        check(f'{60 * ROUNDS} damaged server replies all answered ({answered})', answered == 60 * ROUNDS)
        check('no crash caught', 'internal error' not in b.log(), b.log()[-800:])
        expect('normal again afterwards', b.ask(b'CATALOG/0', b'newest\tall\t'), 'gallery')
        check('game still running', b.alive())
    finally: control({}); b.stop()
ALL += [stress, mailbox_fuzz, server_fuzz]
if __name__ == '__main__':
    chosen = [f for f in ALL if not sys.argv[1:] or f.__name__ in sys.argv[1:]]
    for f in chosen:
        print('==', f.__name__, flush=True)
        try: f()
        except Exception: check(f.__name__ + ' crashed', False, traceback.format_exc())
    print(f'{sum(ok for _, ok in results)}/{len(results)} passed')
