"""Public catalogue pagination and display metadata remain bounded value messages."""
import ctypes,json,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class GalleryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();path=Path(cls.tmp.name)/'core.so'
  subprocess.run(['cc','-Wall','-Wextra','-Werror','-shared','-fPIC',str(ROOT/'native/community/core.c'),'-o',str(path)],check=True)
  cls.lib=ctypes.CDLL(str(path));cls.codes=(ctypes.c_char*33)*6
  cls.lib.dd_gallery_select.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_int,ctypes.POINTER(ctypes.c_char*33),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]
  cls.lib.dd_gallery_row.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t]
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def select(self,items,query='',page=0,fixture=False):
  data=json.dumps(dict(api_version='v1',items=items,fixture=fixture)).encode();codes=self.codes();pages=ctypes.c_int();total=ctypes.c_int()
  n=self.lib.dd_gallery_select(data,len(data),query.encode(),page,codes,ctypes.byref(pages),ctypes.byref(total))
  return n,[codes[i].value.decode() for i in range(max(0,n))],pages.value,total.value
 def test_search_and_pages_are_actual_public_codes(self):
  items=[dict(code=f'Public{i:02d}',title='Lamp '+str(i),description='Actual listed composition',revision=1) for i in range(15)]
  self.assertEqual(self.select(items,page=1),(6,[f'Public{i:02d}' for i in range(6,12)],3,15))
  self.assertEqual(self.select(items,query='lamp 14'),(1,['Public14'],1,1))
  self.assertEqual(self.select(items,query='missing'),(0,[],0,0))
  self.assertEqual(self.select([dict(code='Legacy01',title='Unrevisioned stale entry')]),(0,[],0,0))
 def test_rejects_fixture_injection_invalid_codes_and_oversized_feeds(self):
  self.assertEqual(self.select([dict(code='https://evil.invalid/x',title='bad')])[0],-1)
  self.assertEqual(self.select([],fixture=True)[0],-1)
  self.assertEqual(self.select([dict(code='Public01',title='x')]*49)[0],-1)
 def test_detail_is_bounded_metadata_and_never_a_remote_navigation_target(self):
  row=dict(code='Public01',title='Lamp',description='A nice lamp\nSecond line',creator=dict(id='actual-owner',display_name='Actual creator'),part_count=3,revision=7,requirements=dict(packs=[],unknown_assets=[dict(path='/Pack/Lamp.Lamp')]))
  raw=json.dumps(dict(api_version='v1',item=row)).encode();out=ctypes.create_string_buffer(8192)
  self.assertTrue(self.lib.dd_gallery_row(raw,len(raw),b'Public01',out,len(out)))
  fields=out.value.decode().rstrip('\n').split('\t');self.assertEqual(len(fields),8)
  self.assertEqual(fields[1:3],['Public01','Lamp']);self.assertEqual(fields[4:7],['Actual creator','3','7'])
  self.assertIn('UNKNOWN: /Pack/Lamp.Lamp',fields[7]);self.assertNotIn('\n',fields[3])
