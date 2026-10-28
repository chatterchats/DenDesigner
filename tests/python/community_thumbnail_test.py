"""Render-cache allocator slack must never become uploaded PNG bytes."""
import ctypes
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]

def chunk(kind, data):
    return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data)&0xffffffff)

def image():
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\xff\x80\x40\xff'))+chunk(b'IEND',b'')

class CachePNGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();path=Path(cls.temp.name)/'cache.so'
        subprocess.run(['cc','-Wall','-Wextra','-Werror','-shared','-fPIC',str(ROOT/'native/community/core.c'),'-o',str(path)],check=True)
        cls.lib=ctypes.CDLL(str(path));cls.lib.dd_cached_png.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def read(self, data):
        size=ctypes.c_size_t();ok=self.lib.dd_cached_png(data,len(data),ctypes.byref(size));return ok,size.value
    def test_keeps_exact_encoded_image_and_excludes_exporter_slack(self):
        png=image();padded=png+b'allocator slack: synthetic secret-shaped bytes zcu_'+b'a'*64
        self.assertEqual(self.read(png),(1,len(png)))
        self.assertEqual(self.read(padded),(1,len(png)))
        self.assertEqual(padded[:self.read(padded)[1]],png)
    def test_damaged_or_unsupported_stream_is_not_repaired(self):
        png=image()
        badcrc=bytearray(png);badcrc[30]^=1
        oversized=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1025,1,8,6,0,0,0))+png[33:]
        for bad in [b'fake.png',png[:-1],bytes(badcrc),oversized,png[:33]+chunk(b'acTL',b'12345678')+png[33:]]:
            with self.subTest(size=len(bad)):self.assertEqual(self.read(bad),(0,0))
