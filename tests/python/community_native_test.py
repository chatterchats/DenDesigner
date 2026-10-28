"""Portable native parser/serializer tests. These do not run the shipped game."""
import copy
import ctypes
import hashlib
import json
from pathlib import Path
import random
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'native/community'
HASH = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p)

@HASH
def sha256(pointer, count, output):
    raw = hashlib.sha256(ctypes.string_at(pointer, count)).hexdigest().encode()+b'\0'
    ctypes.memmove(output, raw, len(raw))
    return 1

class Save(ctypes.Structure):
    _fields_ = [('token',ctypes.c_char*65),('input',ctypes.c_char*257),
        ('size_offset',ctypes.c_size_t),('length_offset',ctypes.c_size_t),
        ('value_offset',ctypes.c_size_t),('end',ctypes.c_size_t)]

def canonical(doc):
    return json.dumps(doc,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

class NativeCommunityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which('cc')
        if not compiler: raise unittest.SkipTest('A host C compiler is required for native parser checks')
        cls.temporary = tempfile.TemporaryDirectory()
        library = Path(cls.temporary.name)/'core.so'
        subprocess.run([compiler,'-Wall','-Wextra','-Werror','-fPIC','-shared',str(SOURCE/'core.c'),'-o',str(library)],check=True)
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.dd_document.argtypes = [ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_char_p,HASH,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_char_p)]
        cls.lib.dd_listing.argtypes = [ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.POINTER(ctypes.c_size_t),ctypes.c_void_p,ctypes.POINTER(ctypes.c_char_p)]
        cls.lib.dd_save_read.argtypes = [ctypes.c_char_p,ctypes.c_size_t,ctypes.POINTER(Save),ctypes.POINTER(ctypes.c_char_p)]
        cls.lib.dd_save_response.argtypes = [ctypes.c_char_p,ctypes.c_size_t,ctypes.POINTER(Save),ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
        cls.fixture = (SOURCE/'fixtures/request-v1.sav').read_bytes()
        cls.sample = json.loads((ROOT/'tests/fixtures/sharing/published-monitor-v1.json').read_text())
    @classmethod
    def tearDownClass(cls): cls.temporary.cleanup()
    def validate(self, doc=None, raw=None, rehash=False):
        doc = copy.deepcopy(doc or self.sample)
        if rehash: doc['integrity']['payload_sha256'] = hashlib.sha256(canonical(doc['payload'])).hexdigest()
        raw = raw if raw is not None else canonical(doc)
        wire = ctypes.create_string_buffer(48*1024)
        error = ctypes.c_char_p()
        accepted = self.lib.dd_document(raw,len(raw),b'DenDesignerTest01',b'0'*32,sha256,wire,len(wire),ctypes.byref(error))
        return accepted, wire.value, error.value
    def test_reviewed_sample_validates_into_expected_wire(self):
        accepted, wire, _ = self.validate()
        self.assertTrue(accepted)
        self.assertIn(b'\ncount\t1\npart\t/Game/',wire)
        self.assertTrue(wire.endswith(b'\nend'))
        self.assertNotIn(b'\nend\n',wire)
        self.assertIn(b'packs: none',wire)
    def test_known_mesh_arrangements_support128_distinct_parts(self):
        doc = copy.deepcopy(self.sample)
        part = doc['payload']['entries'][0]
        doc['payload']['entries'] = [dict(part,Key='part-'+str(i),Position=[i*10,0,0]) for i in range(128)]
        accepted, wire, _ = self.validate(doc,rehash=True)
        self.assertTrue(accepted)
        self.assertIn(b'\ncount\t128\n',wire)
        self.assertEqual(wire.count(b'\npart\t'),128)
        doc['payload']['entries'].append(dict(part,Key='part-128'))
        self.assertFalse(self.validate(doc,rehash=True)[0])
    def test_unsupported_and_malformed_documents_never_validate(self):
        changes = [lambda d:d.update(schema_version=2),lambda d:d.update(schema_version=True),
            lambda d:d.update(content_type='den'),lambda d:d['compatibility'].update(game_version='other'),
            lambda d:d['payload']['entries'][0].update(Mesh='/tmp/exec.exe'),
            lambda d:d['payload']['entries'][0].update(Position=[.5,0,0]),
            lambda d:d['payload']['entries'][0].update(Scale=[0,1,1]),
            lambda d:d['payload']['entries'][0].update(Position=[10000001,0,0]),
            lambda d:d['payload']['entries'][0].update(Hidden=True),
            lambda d:d['payload']['entries'][0].update(Kind=2),
            lambda d:d['payload']['entries'][0].update(CollisionMode=3),
            lambda d:d['payload']['entries'][0].update(Unknown='ignored'),
            lambda d:d['metadata'].update(title='\nInjected record'),
            lambda d:d['metadata'].update(title=' leading space'),
            lambda d:d['metadata'].update(title='Unicode snowman \u2603')]
        for change in changes:
            doc = copy.deepcopy(self.sample);change(doc)
            with self.subTest(doc=doc): self.assertFalse(self.validate(doc,rehash=True)[0])
    def test_dependency_unknown_pack_material_and_unreviewed_mesh_rejected(self):
        for field, value in [('packs',[{'id':'test-pack','version':'1'}]),
                             ('unknown_assets',[{'path':'/Game/A.A','kind':'mesh'}]),
                             ('assets',[])]:
            doc = copy.deepcopy(self.sample);doc['dependencies'][field] = value
            accepted,_,error = self.validate(doc)
            self.assertFalse(accepted);self.assertIn(b'Dependencies:',error)
        doc = copy.deepcopy(self.sample);doc['payload']['entries'][0]['Materials']=['/Game/Material.Material']
        self.assertFalse(self.validate(doc,rehash=True)[0])
    def test_integrity_duplicate_fields_and_noncanonical_payload_rejected(self):
        doc = copy.deepcopy(self.sample);doc['payload']['entries'][0]['Position']=[3,0,0]
        self.assertFalse(self.validate(doc)[0])
        raw = canonical(self.sample)
        for bad in [raw.replace(b'"schema_version":1',b'"schema_version":1,"schema_version":1'),
                    raw.replace(b'"schema_version":1',b'"schema_version":NaN'),
                    raw.replace(b'"schema_version":1',b'"schema_version":1,"\\u0073chema_version":1'),
                    json.dumps(self.sample,sort_keys=True,indent=2).encode(),
                    raw[:-1], b'['*1000, raw+b'{}']:
            self.assertFalse(self.validate(raw=bad)[0])
        doc = copy.deepcopy(self.sample);doc['payload']['entries']*=2
        self.assertFalse(self.validate(doc,rehash=True)[0])
    def test_listing_version_identity_hash_and_size(self):
        raw = canonical(self.sample)
        item = dict(code='DenDesignerTest01',kind='comp',schema_version=1,document_bytes=len(raw),document_sha256=hashlib.sha256(raw).hexdigest())
        def validate(value):
            encoded=canonical(value);size=ctypes.c_size_t();digest=ctypes.create_string_buffer(65);error=ctypes.c_char_p()
            return self.lib.dd_listing(encoded,len(encoded),b'DenDesignerTest01',ctypes.byref(size),digest,ctypes.byref(error)),size.value,digest.value
        self.assertEqual(validate({'api_version':'v1','item':item}), (1,len(raw),hashlib.sha256(raw).hexdigest().encode()))
        for key,value in [('code','OtherCode'),('kind','den'),('schema_version',2),('document_bytes',4194305),('document_bytes',0),('document_sha256','x'*64)]:
            self.assertFalse(validate({'api_version':'v1','item':dict(item,**{key:value})})[0])
    def test_exact_gvas_fixture_and_atomic_response_serialization(self):
        save=Save();error=ctypes.c_char_p()
        self.assertTrue(self.lib.dd_save_read(self.fixture,len(self.fixture),ctypes.byref(save),ctypes.byref(error)))
        self.assertEqual(save.token,b'0123456789abcdef0123456789abcdef')
        self.assertEqual(save.input,b'DenDesignerTest01')
        wire=self.validate()[1];output=ctypes.create_string_buffer(65536);written=ctypes.c_size_t()
        self.assertTrue(self.lib.dd_save_response(self.fixture,len(self.fixture),ctypes.byref(save),wire,output,len(output),ctypes.byref(written)))
        result=output.raw[:written.value]
        self.assertEqual(result[:save.size_offset],self.fixture[:save.size_offset])
        self.assertEqual(struct.unpack_from('<I',result,save.size_offset)[0],len(wire)+5)
        self.assertEqual(struct.unpack_from('<I',result,save.length_offset)[0],len(wire)+1)
        self.assertEqual(result[save.value_offset:save.value_offset+len(wire)+1],wire+b'\0')
        self.assertEqual(result[save.value_offset+len(wire)+1:],self.fixture[save.end:])
    def test_publish_mailbox_is_bounded_and_cannot_replace_fetch_wire(self):
        error=ctypes.c_char_p();save=Save()
        self.assertTrue(self.lib.dd_save_read(self.fixture,len(self.fixture),ctypes.byref(save),ctypes.byref(error)))
        body=b'{"format":"zcom-share","schema_version":1}'
        output=ctypes.create_string_buffer(65536);written=ctypes.c_size_t()
        self.assertTrue(self.lib.dd_save_response(self.fixture,len(self.fixture),ctypes.byref(save),body,output,len(output),ctypes.byref(written)))
        changed=output.raw[:written.value]
        self.assertFalse(self.lib.dd_save_read(changed,len(changed),ctypes.byref(Save()),ctypes.byref(error)))
        old=b'DenDesignerTest01\0';at=changed.index(old)
        # Replace the complete local FString and its measured size tag.
        changed=bytearray(changed[:at]+b'PUBLISH\0'+changed[at+len(old):])
        struct.pack_into('<I',changed,at-4,8)
        # Payload size is four bytes of FString length plus eight bytes of data.
        flags=changed[at-4-17]  # editor fixture's GUID flag precedes its 16-byte GUID
        self.assertEqual(flags,2)
        struct.pack_into('<I',changed,at-4-21,12)
        result=Save()
        self.assertTrue(self.lib.dd_save_read(bytes(changed),len(changed),ctypes.byref(result),ctypes.byref(error)))
        self.assertEqual(result.input,b'PUBLISH')
        self.assertEqual(changed[result.value_offset:result.end-1],body)

    def test_gvas_truncation_unknown_class_schema_and_random_bytes_fail_closed(self):
        error=ctypes.c_char_p()
        for length in range(len(self.fixture)):
            save=Save()
            self.assertFalse(self.lib.dd_save_read(self.fixture[:length],length,ctypes.byref(save),ctypes.byref(error)))
        for offset in (0,4,8,12,16,18,20,self.fixture.index(b'BP_DenCommunityWireSave'),self.fixture.index(b'Token'),self.fixture.index(b'StrProperty')):
            bad=bytearray(self.fixture);bad[offset]^=0x7f;save=Save()
            self.assertFalse(self.lib.dd_save_read(bytes(bad),len(bad),ctypes.byref(save),ctypes.byref(error)))
        rng=random.Random(271828)
        for _ in range(500):
            bad=rng.randbytes(rng.randrange(1,1024));save=Save()
            self.assertFalse(self.lib.dd_save_read(bad,len(bad),ctypes.byref(save),ctypes.byref(error)))
    def test_shipped_game_tags_without_editor_guids_preserve_their_layout(self):
        fixture=(SOURCE/'fixtures/request-shipped-v1.sav').read_bytes()
        save=Save();error=ctypes.c_char_p()
        self.assertTrue(self.lib.dd_save_read(fixture,len(fixture),ctypes.byref(save),ctypes.byref(error)))
        self.assertEqual(save.input,b'https://share.zcom.app/comp/DenDesignerTest01')
        self.assertEqual(save.token,b'0123456789abcdef0123456789abcdef')
        self.assertEqual(fixture[save.length_offset-1],0)
        wire=self.validate()[1];output=ctypes.create_string_buffer(65536);written=ctypes.c_size_t()
        self.assertTrue(self.lib.dd_save_response(fixture,len(fixture),ctypes.byref(save),wire,output,len(output),ctypes.byref(written)))
        result=output.raw[:written.value]
        self.assertEqual(result[:save.size_offset],fixture[:save.size_offset])
        self.assertEqual(result[save.size_offset+4:save.length_offset],fixture[save.size_offset+4:save.length_offset])
        self.assertEqual(result[save.value_offset:save.value_offset+len(wire)+1],wire+b'\0')
        self.assertEqual(result[save.value_offset+len(wire)+1:],fixture[save.end:])
        for length in range(len(fixture)):
            self.assertFalse(self.lib.dd_save_read(fixture[:length],length,ctypes.byref(Save()),ctypes.byref(error)))
        for flags in [1,3,255]:
            bad=bytearray(fixture);bad[save.length_offset-1]=flags
            self.assertFalse(self.lib.dd_save_read(bytes(bad),len(bad),ctypes.byref(Save()),ctypes.byref(error)))
    def test_code_allowlist(self):
        for text in (b'DenDesignerTest01',b'https://share.zcom.app/comp/DenDesignerTest01',b'https://zcom.app/comp/DenDesignerTest01/'):
            code=ctypes.create_string_buffer(33);self.assertTrue(self.lib.dd_code(text,code));self.assertEqual(code.value,b'DenDesignerTest01')
        for text in (b'bad',b'https://evil.test/comp/DenDesignerTest01',b'https://share.zcom.app.evil.test/comp/DenDesignerTest01',b'https://share.zcom.app:443/comp/DenDesignerTest01',b'https://zcom.app/comp/DenDesignerTest01?x=1',b'file:///tmp/evil',b'https://evil@zcom.app/comp/DenDesignerTest01'):
            code=ctypes.create_string_buffer(33);self.assertFalse(self.lib.dd_code(text,code))

    def request_with(self, operation, wire):
        error=ctypes.c_char_p();save=Save()
        self.assertTrue(self.lib.dd_save_read(self.fixture,len(self.fixture),ctypes.byref(save),ctypes.byref(error)))
        output=ctypes.create_string_buffer(65536);written=ctypes.c_size_t()
        self.assertTrue(self.lib.dd_save_response(self.fixture,len(self.fixture),ctypes.byref(save),wire,output,len(output),ctypes.byref(written)))
        changed=bytearray(output.raw[:written.value]);old=b'DenDesignerTest01\0';at=changed.index(old)
        name=operation+b'\0';changed[at:at+len(old)]=name
        struct.pack_into('<I',changed,at-4,len(name));struct.pack_into('<I',changed,at-25,4+len(name))
        return bytes(changed)

    def test_connection_credentials_require_explicit_auth_message_and_valid_key(self):
        key=b'zcu_'+b'a'*64;error=ctypes.c_char_p()
        for operation,wire,valid in [(b'AUTH',b'1\t'+key,True),(b'AUTH',b'0\t'+key,True),
            (b'AUTH',b'2\t'+key,False),(b'AUTH',b'1\t'+key+b'x',False),
            (b'AUTH',b'1\t'+b'zcu_'+b'g'*64,False),(b'CONNECT',key,False),
            (b'FORGET',b'request',True),(b'DenDesignerTest01',b'1\t'+key,False)]:
            raw=self.request_with(operation,wire);parsed=Save()
            self.assertEqual(bool(self.lib.dd_save_read(raw,len(raw),ctypes.byref(parsed),ctypes.byref(error))),valid)
            if valid and operation==b'AUTH':
                output=ctypes.create_string_buffer(65536);written=ctypes.c_size_t()
                self.assertTrue(self.lib.dd_save_response(raw,len(raw),ctypes.byref(parsed),b'Connected',output,len(output),ctypes.byref(written)))
                self.assertNotIn(key,output.raw[:written.value])

    def test_cached_thumbnail_publish_header_survives_native_mailbox_validation(self):
        error=ctypes.c_char_p()
        for wire,valid in [(b'Composition_0123abcd.png\n{}',True),
                           (b'Composition_0123abcd.png',False),
                           (b'Composition_0123abcd.png\n',False),
                           (b'../../secret.png\n{}',False)]:
            raw=self.request_with(b'PUBLISH',wire)
            self.assertEqual(bool(self.lib.dd_save_read(raw,len(raw),ctypes.byref(Save()),ctypes.byref(error))),valid)

class ProxyExportTests(unittest.TestCase):
    def test_proxy_covers_version_imports_of_game_and_graphics_dependencies(self):
        exports = {line.strip().split('=')[0] for line in (SOURCE/'version.def').read_text().splitlines() if '=DD_' in line}
        expected = {base+suffix for base in ['GetFileVersionInfo','GetFileVersionInfoEx','GetFileVersionInfoSize','GetFileVersionInfoSizeEx','VerFindFile','VerInstallFile','VerLanguageName','VerQueryValue'] for suffix in ['A','W']}
        self.assertEqual(exports, expected)
        dependencies = json.loads((SOURCE/'fixtures/version-imports.json').read_text())
        self.assertIn('VerQueryValueA', dependencies['d3d12core.dll']['version_imports'])
        for name, record in dependencies.items():
            self.assertTrue(set(record['version_imports']) <= exports, name)

if __name__=='__main__': unittest.main()
