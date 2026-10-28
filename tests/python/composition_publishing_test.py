"""Cross-repository publication bytes -> portable contract -> native import.

Fake D1/R2, actual service handlers and native parser; no network or game saves.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class CompositionPublishingTests(unittest.TestCase):
    def test_service_publication_imports_without_losing_values(self):
        service = ROOT.parent/'ZComShare'
        test = service/'test/publishing.test.js'
        if not test.exists():
            self.skipTest('Adjacent Community publishing service checkout is required')
        if not shutil.which('node') or not shutil.which('cc'):
            self.skipTest('Node 22 and host C compiler required')
        from tools.sharing.contract import loads
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            output = tmp/'published.json'
            result = subprocess.run(['node', str(test)], env={**os.environ, 'ZCOM_PUBLISH_EXPORT':str(output)}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            document = loads(output.read_bytes())
            library = tmp/'core.so'
            subprocess.run(['cc','-Wall','-Wextra','-Werror','-shared','-fPIC',str(ROOT/'native/community/core.c'),'-o',str(library)], check=True)
            lib = ctypes.CDLL(str(library))
            hash_type = ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p)
            @hash_type
            def sha(pointer, count, out):
                ctypes.memmove(out,hashlib.sha256(ctypes.string_at(pointer,count)).hexdigest().encode()+b'\0',65)
                return 1
            lib.dd_document.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_char_p,hash_type,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_char_p)]
            raw=output.read_bytes();wire=ctypes.create_string_buffer(49152);error=ctypes.c_char_p()
            self.assertTrue(lib.dd_document(raw,len(raw),b'published01',b'0'*32,sha,wire,len(wire),ctypes.byref(error)),error.value)
            self.assertIn(b'\t1.25\t-2.5\t3',wire.value)
            self.assertIn(b'\t0.125\t1\t2',wire.value)
            self.assertIn(b'\nmaterial\t\nmaterial\t/ExamplePack/Materials/Red.Red',wire.value)
            self.assertEqual(document['metadata']['author']['id'],'author')
            self.assertEqual(len(document['metadata']['media']),1)
            self.assertEqual(len(document['dependencies']['unknown_assets']),2)
            # Thumbnail metadata cannot turn an otherwise invalid transform into
            # a safe wire; validation and payload integrity remain independent.
            document['payload']['entries'][0]['Scale']=[0,1,1]
            payload=json.dumps(document['payload'],sort_keys=True,separators=(',',':')).encode()
            document['integrity']['payload_sha256']=hashlib.sha256(payload).hexdigest()
            bad=json.dumps(document,sort_keys=True,separators=(',',':')).encode()
            self.assertFalse(lib.dd_document(bad,len(bad),b'published01',b'0'*32,sha,wire,len(wire),ctypes.byref(error)))
