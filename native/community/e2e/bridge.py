"""Drive the test version.dll in a Wine host the way the game does: write
request.sav (fresh token each time), read response.sav."""
import ctypes, os, secrets, struct, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT/'tests/python'))
from community_native_test import Save
STATE = Path(os.environ['DD_E2E_STATE'])  # test DLL, host, prefix, server log
E = STATE; PREFIX = Path(os.environ.get('DD_E2E_PREFIX', STATE/'prefix'))
WINE_ENV = dict(os.environ, WINEPREFIX=str(PREFIX), WINEDEBUG='-all')
def local_appdata():
    out = subprocess.run(['wine', 'cmd', '/c', 'echo %LOCALAPPDATA%'], env=WINE_ENV, capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]
    return Path(subprocess.run(['winepath', '-u', out], env=WINE_ENV, capture_output=True, text=True, check=True).stdout.strip())
LOCAL = local_appdata()/'SWZeroCompany'
M = LOCAL/'Saved/SaveGames/ZComDen/Community/v1'
THUMBS = LOCAL/'Saved/ZComDen/thumbs'
REQUEST, RESPONSE, LOG, KEYFILE = M/'request.sav', M/'response.sav', M/'native.log', M/'connection.key'
lib_path = Path(tempfile.mkdtemp())/'core.so'
subprocess.run(['cc', '-shared', '-fPIC', str(ROOT/'native/community/core.c'), '-o', str(lib_path)], check=True)
L = ctypes.CDLL(str(lib_path))
L.dd_save_read.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(Save), ctypes.POINTER(ctypes.c_char_p)]
L.dd_save_response.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(Save), ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
FIXTURE = (ROOT/'native/community/fixtures/request-v1.sav').read_bytes()
def make(operation, wire):
    save = Save(); err = ctypes.c_char_p()
    assert L.dd_save_read(FIXTURE, len(FIXTURE), ctypes.byref(save), ctypes.byref(err))
    out = ctypes.create_string_buffer(400000); n = ctypes.c_size_t()
    assert L.dd_save_response(FIXTURE, len(FIXTURE), ctypes.byref(save), wire, out, len(out), ctypes.byref(n)), (operation, wire[:80])
    raw = bytearray(out.raw[:n.value]); old = b'DenDesignerTest01\0'; at = raw.index(old); name = operation + b'\0'
    raw[at:at+len(old)] = name; struct.pack_into('<I', raw, at-4, len(name)); struct.pack_into('<I', raw, at-25, 4+len(name))
    token = save.token; fresh = secrets.token_hex(len(token)//2).encode()[:len(token)]
    assert raw.count(token) == 1
    raw = bytes(raw).replace(token, fresh)
    check = Save(); assert L.dd_save_read(raw, len(raw), ctypes.byref(check), ctypes.byref(err)), (operation, err.value)
    return raw, fresh.decode()
def wire_of(data):
    at = data.index(b'Wire\0')+5; at = data.index(b'StrProperty\0', at)+12+4+4; flags = data[at]; at += 1+(16 if flags == 2 else 0)
    n = struct.unpack_from('<i', data, at)[0]; at += 4
    return data[at:at+n-1].decode('latin-1') if n > 0 else data[at:at-2*n-2].decode('utf-16-le')
class Bridge:
    def __init__(self, fault=None):
        M.mkdir(parents=True, exist_ok=True)
        for f in M.iterdir():
            if f.name != 'connection.key' or fault == 'keep-nothing': f.unlink()
        # Wine prefers its own built-in version.dll; Proton players set the same override.
        env = dict(WINE_ENV, WINEDLLOVERRIDES='version=n,b')
        if fault: env['DD_TEST_FAULT'] = fault
        self.process = subprocess.Popen(['wine', str(E/'bin/host.exe')], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.wait_log('loaded', 20)
    def log(self): return LOG.read_text(errors='replace') if LOG.exists() else ''
    def wait_log(self, text, seconds):
        end = time.time()+seconds
        while time.time() < end:
            if text in self.log(): return True
            time.sleep(0.1)
        raise AssertionError(f'log never said {text!r}:\n{self.log()}')
    def send(self, operation, wire=b'request'):
        raw, token = make(operation, wire)
        REQUEST.write_bytes(raw); self.raw = raw; self.token = token
        return token
    def answer(self, seconds=35, final=True):
        start = time.time(); seen = None
        while time.time()-start < seconds:
            try: data = RESPONSE.read_bytes()
            except FileNotFoundError: data = None
            if data and data != seen:
                seen = data
                try: wire = wire_of(data)
                except Exception: wire = None
                if wire and self.token in wire.split('\n')[0] and (not final or '\nprogress\t' not in wire):
                    return wire, round(time.time()-start, 1)
            time.sleep(0.05)
        return None, round(time.time()-start, 1)
    def ask(self, operation, wire=b'request', seconds=35):
        self.send(operation, wire); return self.answer(seconds)
    def stop(self):
        (E/'bin/quit').write_text('1')
        try: self.process.wait(10)
        except subprocess.TimeoutExpired: self.process.kill()
    def alive(self): return self.process.poll() is None
def message(wire):
    lines = wire.split('\n')[1:]
    return '\n'.join(l for l in lines if l != 'end')
