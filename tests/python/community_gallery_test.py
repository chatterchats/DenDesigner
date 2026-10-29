"""HoloNet pages, cards, My Shares and profile replies stay bounded value messages."""
import ctypes,json,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
LISTING=json.loads((ROOT/'tests/fixtures/sharing/holonet-composition-pack.listing.json').read_text())['item']
class GalleryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();path=Path(cls.tmp.name)/'core.so'
  subprocess.run(['cc','-Wall','-Wextra','-Werror','-shared','-fPIC',str(ROOT/'native/community/core.c'),'-o',str(path)],check=True)
  cls.lib=ctypes.CDLL(str(path))
  cls.lib.dd_catalog_request.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_int),ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int]
  for name in ['dd_gallery_page']:getattr(cls.lib,name).argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_size_t]
  cls.lib.dd_shares_page.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.c_int,ctypes.c_void_p,ctypes.c_size_t]
  cls.lib.dd_profile.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t]
  cls.lib.dd_publish_text.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_size_t]
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def catalog(self,wire,page=0):
  wire=wire.encode();legacy=ctypes.c_int();out=ctypes.create_string_buffer(512)
  ok=self.lib.dd_catalog_request(wire,len(wire),ctypes.byref(legacy),out,len(out),page)
  return (out.value.decode(),bool(legacy.value)) if ok else None
 def gallery(self,items,legacy=False,page=0,**extra):
  data=json.dumps(dict(api_version='v1',items=items,**extra)).encode();out=ctypes.create_string_buffer(48*1024)
  if not self.lib.dd_gallery_page(data,len(data),legacy,page,out,len(out)):return None
  return [line.split('\t') for line in out.value.decode().rstrip('\n').split('\n')]
 def test_search_and_sort_become_one_server_request_per_page(self):
  self.assertEqual(self.catalog('newest\tall\t'),('/api/v1/compositions?page=1&per_page=8&sort=newest',False))
  self.assertEqual(self.catalog('imports\tbase\t  Caf\u00e9 & lamp ',page=2),('/api/v1/compositions?page=3&per_page=8&sort=imports&base_game=1&q=Caf%C3%A9%20%26%20lamp',False))
  # preview.22's panel sends just its search text: newest, six per page.
  self.assertEqual(self.catalog('lamp 14'),('/api/v1/compositions?page=1&per_page=6&sort=newest&q=lamp%2014',True))
  self.assertEqual(self.catalog(' '),('/api/v1/compositions?page=1&per_page=6&sort=newest',True))
  for bad in ['newest\tall','popular\tall\tx','newest\tmine\tx','newest\tall\tx\ty','x'*81,'a zcu_'+'0'*64,'line\nbreak']:
   self.assertIsNone(self.catalog(bad),bad)
  self.assertIsNone(self.catalog('x',page=10000))
 def test_cards_carry_separate_fields_and_pack_rows(self):
  rows=self.gallery([LISTING,dict(LISTING,code='H7854VMD',requirements=dict(packs=[],unknown_assets=[]),base_game_only=True)],page=1,total=10,pages=2)
  self.assertEqual(rows[0],['gallery','1','2','10'])
  card=rows[1];self.assertEqual(len(card),12)
  self.assertEqual(card[:9],['card','T93765D1','Rook\u2019s arcade nook \u2014 v2\u2026','Rook','3','1','1','0','1'])
  self.assertEqual(card[9],'2026-10-29T02:23:35.000Z')
  self.assertEqual(card[10],'')  # this listing has no footprint
  self.assertEqual(card[11],'Base game, a pack\\nand an unknown mod. Caf\u00e9 \u2603')
  self.assertEqual(rows[2],['pack','T93765D1','arcade-cabinets','Arcade Cabinets \u201cDeluxe\u201d','1.2.0','1','https://www.nexusmods.com/games/starwarszerocompany/mods/42'])
  self.assertEqual(rows[3][:9],['card','H7854VMD','Rook\u2019s arcade nook \u2014 v2\u2026','Rook','3','1','1','1','0'])
  self.assertEqual(len(rows),4)
 def test_footprint_is_shown_in_metres(self):
  for value,text in [([62,40,118],'0.6 \u00d7 0.4 \u00d7 1.2 m'),([240.4,80,2105.5],'2.4 \u00d7 0.8 \u00d7 21.1 m'),([4,0,0],'0.0 \u00d7 0.0 \u00d7 0.0 m'),
                     (None,''),([1,2],''),([-1,2,3],''),([1e3,2,3],'10.0 \u00d7 0.0 \u00d7 0.0 m')]:
   rows=self.gallery([dict(LISTING,footprint_cm=value)])
   self.assertEqual(rows[1][10],text,value)
 def test_pack_links_fall_back_to_a_nexus_title_search(self):
  for url in [None,'','http://www.nexusmods.com/games/starwarszerocompany/mods/42','https://www.nexusmods.com/games/othergame/mods/1','https://evil.test/starwarszerocompany/','https://www.nexusmods.com/games/starwarszerocompany/mods/42"onclick','https://www.nexusmods.com/games/starwarszerocompany/']:
   pack=dict(LISTING['requirements']['packs'][0],url=url)
   if url is None:del pack['url']
   rows=self.gallery([dict(LISTING,requirements=dict(packs=[pack],unknown_assets=[]))])
   self.assertEqual(rows[2][6],'https://www.nexusmods.com/games/starwarszerocompany/mods?title=Arcade%20Cabinets%20%E2%80%9CDeluxe%E2%80%9D',url)
 def test_text_never_breaks_rows_and_descriptions_are_escaped_and_cut(self):
  item=dict(LISTING,title='Tab\there\nnow',description='back\\slash\r\nline\t'+'x'*2000,creator=dict(display_name='  '))
  rows=self.gallery([item])
  self.assertEqual(rows[1][2],'Tab here now');self.assertEqual(rows[1][3],'Unknown creator')
  self.assertTrue(rows[1][11].startswith('back\\\\slash\\nline x'));self.assertEqual(len(rows[1][11].replace('\\\\','\\').replace('\\n','\n')),1000)
 def test_unusable_items_are_skipped_and_bad_pages_rejected(self):
  # Not a code, no revision, or not in the server's upper-case form.
  rows=self.gallery([dict(LISTING,code='https://evil.invalid/x'),dict(LISTING,revision=0),dict(LISTING,code='lower123'),LISTING])
  self.assertEqual([r[1] for r in rows if r[0]=='card'],['T93765D1'])
  self.assertIsNone(self.gallery([LISTING]*9))
  data=json.dumps(dict(api_version='v2',items=[])).encode();out=ctypes.create_string_buffer(1024)
  self.assertFalse(self.lib.dd_gallery_page(data,len(data),0,0,out,len(out)))
  self.assertEqual(self.gallery([]),[['gallery','0','0','0']])
 def test_real_holonet_gallery_page(self):
  # Saved from the live server code: a 1-based page with pages, total and full listing items.
  data=(ROOT/'tests/fixtures/sharing/holonet-gallery-page.json').read_bytes();out=ctypes.create_string_buffer(48*1024)
  self.assertTrue(self.lib.dd_gallery_page(data,len(data),0,0,out,len(out)))
  rows=[l.split('\t') for l in out.value.decode().rstrip('\n').split('\n')]
  self.assertEqual(rows[0],['gallery','0','1','2'])
  cards={r[1]:r for r in rows if r[0]=='card'}
  self.assertEqual(sorted(cards),['H7854VMD','T93765D1'])
  self.assertEqual(cards['H7854VMD'][2:11],['HoloNet base-game fixture','Rook','1','1','1','1','0','2026-10-29T02:23:35.000Z','0.6 \u00d7 0.4 \u00d7 1.2 m'])
  self.assertEqual([r[2] for r in rows if r[0]=='pack'],['arcade-cabinets'])
 def test_preview22_rows_stay_compatible(self):
  rows=self.gallery([LISTING],legacy=True,total=100,pages=17)
  self.assertEqual(rows[0],['gallery','0','8','48'])
  self.assertEqual(len(rows[1]),8)
  self.assertEqual(rows[1][:7],['listing','T93765D1','Rook\u2019s arcade nook \u2014 v2\u2026','Base game, a pack and an unknown mod. Caf\u00e9 \u2603','Rook','3','1'])
  self.assertEqual(rows[1][7],'Pack: Arcade Cabinets \u201cDeluxe\u201d 1.2.0 | UNKNOWN: /OtherMod/Meshes/SM_Thing.SM_Thing')
  self.assertIsNone(self.gallery([LISTING]*7,legacy=True))
 def test_my_shares_page(self):
  items=[dict(code='T93765D1',title='Nook',revision=1,latest_revision=3,import_count=12,hidden=False,updated_at='2026-10-29T02:23:35.000Z'),
         dict(code='H7854VMD',title='Hidden one',revision=2,import_count=0,visibility='hidden'),dict(code='bad code',revision=1)]
  data=json.dumps(dict(items=items,page=1,pages=1,total=3)).encode();out=ctypes.create_string_buffer(8192)
  self.assertTrue(self.lib.dd_shares_page(data,len(data),0,out,len(out)))
  self.assertEqual([l.split('\t') for l in out.value.decode().rstrip('\n').split('\n')],
   [['shares','0','1','3'],['share','T93765D1','Nook','3','12','public','2026-10-29T02:23:35.000Z'],['share','H7854VMD','Hidden one','2','0','hidden','']])
 def test_profile_name(self):
  def profile(value):
   data=json.dumps(value).encode();out=ctypes.create_string_buffer(260)
   return self.lib.dd_profile(data,len(data),out,len(out)),out.value.decode()
  uid='11111111-1111-4111-8111-111111111111'
  self.assertEqual(profile(dict(user_id=uid,display_name='Chatter\u2603\tChats')),(1,'Chatter\u2603 Chats'))
  self.assertEqual(profile(dict(user_id=uid)),(1,''))
  self.assertEqual(profile(dict(user_id=uid,display_name='x'*100)),(1,'x'*64))
  for bad in [dict(),dict(user_id='nope'),dict(user_id=uid.replace('-','x'))]:self.assertEqual(profile(bad)[0],0)
 def test_publish_text_unescapes_and_bounds(self):
  def decode(value,limit=120,multiline=False):
   raw=value.encode();out=ctypes.create_string_buffer(2048)
   return out.value.decode() if self.lib.dd_publish_text(raw,len(raw),limit,multiline,out,len(out)) else None
  self.assertEqual(decode('Caf\u00e9 \\\\ \U0001F680'),'Caf\u00e9 \\ \U0001F680')
  self.assertEqual(decode('one\\ntwo',multiline=True),'one\ntwo')
  self.assertIsNone(decode('one\\ntwo'));self.assertIsNone(decode('tab\there'));self.assertIsNone(decode('bad \\x escape'))
  self.assertEqual(decode('\u00e9'*120),'\u00e9'*120);self.assertIsNone(decode('\u00e9'*121))
  self.assertIsNone(decode('key zcu_'+'a'*64))
  raw=b'\xc3\x28';out=ctypes.create_string_buffer(16);self.assertFalse(self.lib.dd_publish_text(raw,2,10,0,out,16))
