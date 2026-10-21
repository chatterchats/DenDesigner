"""Offline migration failure, fidelity, and preservation tests (stdlib only)."""
import copy
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/migration'))
from den_save import Codec, Reader
from migrate_layouts import stage,convert,parse_json,LAYOUT

CID='BA3302BC4165EB931E86A39BFF208F71'
MESH='/Game/Props/SM_Test.SM_Test'
KEY='/Game/Hub.Hub:PersistentLevel.Fixture.Mesh'


def document():
    return {'format':1,'game':'test-version','placed':[{'id':'p0001','mesh':MESH,'t':[1,2,3],
        'r':[10,20,30],'s':[1,2,3],'solid':False,'mats':['','/Game/Props/MI_Test.MI_Test'],'from':KEY}],
        'stored':[{'id':'p0002','mesh':MESH,'t':[-1,-2,-3]}],
        'vanilla':{KEY:{'hidden':True,'r':[0,90,0],'fp':{'mesh':MESH,'at':[4,5,6]}}}}


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'source';self.source.mkdir()
        self.output=self.root/'migration'
        self.codec=Codec()

    def write(self,name,doc):
        p=self.source/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(doc if isinstance(doc,bytes) else json.dumps(doc).encode())

    def snapshot(self):
        return {p.relative_to(self.source).as_posix():p.read_bytes() for p in self.source.rglob('*') if p.is_file()}

    def decoded(self,name):
        return self.codec.decode((self.output/'SaveGames/ZComDen/Native/v1'/name).read_bytes())[1]

    def test_verified_shipping_header_preserves_payload(self):
        encoded=self.codec.encode(LAYOUT,convert(document()))
        expected=self.codec.decode(encoded)
        body=encoded[len(self.codec.header):]
        for profile in self.codec.schema['compatible_headers']:
            header=bytes.fromhex(profile['header'])
            self.assertEqual(self.codec.decode(header+body),expected)
            reader=Reader(header)
            reader.header()
            # Serialized custom-version order is not stable across launches.
            count=len(Reader(header).header()[1])
            prefix=header[:-count*20]
            records=[header[i:i+20] for i in range(len(prefix),len(header),20)]
            self.assertEqual(self.codec.decode(prefix+b''.join(reversed(records))+body),expected)

    def test_unknown_shipping_header_is_rejected(self):
        body=self.codec.encode(LAYOUT,{})[len(self.codec.header):]
        original=bytes.fromhex(self.codec.schema['compatible_headers'][0]['header'])
        for offset in [22,len(original)-1]:
            changed=bytearray(original);changed[offset]^=1
            with self.assertRaises(ValueError):self.codec.decode(bytes(changed)+body)

    def test_shipping_profile_does_not_relax_payload_validation(self):
        header=bytes.fromhex(self.codec.schema['compatible_headers'][0]['header'])
        body=self.codec.encode(LAYOUT,{})[len(self.codec.header):]
        for bad in [body.replace(b'BP_DenLayoutSave',b'BP_BadLayoutSav',1),body[:-1],body+b'x']:
            with self.assertRaises((ValueError,UnicodeError)):self.codec.decode(header+bad)

    def test_complete_layout_fidelity(self):
        self.write('home.json',document())
        manifest=stage(self.source,self.output)
        data=self.decoded('home-layout-0.sav'); rows=data['Entries']
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]['CollisionMode'],2)
        self.assertEqual(rows[0]['Materials'],['','/Game/Props/MI_Test.MI_Test'])
        self.assertEqual(rows[0]['Scale'],[1,2,3])
        self.assertEqual(rows[1]['Kind'],1)
        self.assertEqual(rows[1]['Scale'],[1,1,1])
        self.assertEqual(rows[2]['HasPosition'],False)
        self.assertEqual(rows[2]['HasRotation'],True)
        self.assertEqual(rows[2]['FingerprintPosition'],[4,5,6])
        self.assertEqual(data['WriteCompleteID'],data['ContentID'])
        self.assertEqual(data['GameVersion'],'test-version')
        self.assertEqual(manifest['saves']['home-layout-0.sav']['entries'],3)

    def test_preserve_every_original_and_backup_order(self):
        self.write('home.json',document())
        for n in range(1,6):
            doc=document();doc['placed'][0]['t'][0]=n
            self.write(f'backups/home.{n}.json',doc)
        self.write('backups/home.corrupt-123.json',b'not valid JSON')
        self.write('home.json.tmp',b'partial')
        self.write('backups/campaign-'+CID+'.dropped-123.json',document())
        before=self.snapshot()
        result=stage(self.source,self.output)
        self.assertEqual(before,self.snapshot())
        for name,data in before.items():self.assertEqual((self.output/'originals'/name).read_bytes(),data)
        self.assertEqual(len(result['saves']),6)
        self.assertEqual([self.decoded(f'home-layout-{n}.sav')['Revision'] for n in range(6)],list(range(1,7)))
        self.assertEqual([self.decoded(f'home-layout-{n}.sav')['Entries'][0]['Position'][0] for n in range(5)],[5,4,3,2,1])
        self.assertEqual(self.decoded('home-layout-5.sav')['Entries'][0]['Position'][0],1)

    def test_campaign_draft_and_presets(self):
        self.write('campaigns/'+CID.lower()+'.json',document())
        draft=document();draft['draft_at']='2026-10-20 01:00'
        self.write('campaigns/'+CID.lower()+'.draft.json',draft)
        self.write('presets/Medical Bay.json',document())
        self.write('presets/index.json',{'presets':[]})
        result=stage(self.source,self.output)
        c=self.decoded('campaign-'+CID+'-layout-0.sav')
        d=self.decoded('campaign-'+CID+'-draft-0.sav')
        self.assertEqual((c['Scope'],c['CampaignID'],c['Enabled']),('campaign',CID,True))
        self.assertEqual((d['IsDraft'],d['DraftBaseRevision'],d['DraftBaseID']),(True,0,''))
        self.assertEqual(result['saves']['campaign-'+CID+'-draft-0.sav']['legacy_draft_at'],draft['draft_at'])
        self.assertEqual(self.decoded('presets-layout-0.sav')['Entries'][0]['Name'],'Medical Bay')

    def test_draft_without_saved_layout_stays_a_draft(self):
        self.write('home.draft.json',document())
        result=stage(self.source,self.output)
        self.assertEqual(list(result['saves']),['home-draft-0.sav'])

    def test_invalid_active_layout_aborts_without_output(self):
        doc=document();doc['placed'][0]['s']=[1,0,1]
        self.write('home.json',doc)
        before=self.snapshot()
        with self.assertRaises(ValueError):stage(self.source,self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.snapshot(),before)

    def test_bad_backup_preserved_and_reported(self):
        self.write('home.json',document());self.write('backups/home.1.json',b'{')
        result=stage(self.source,self.output)
        self.assertIn('preserved but not converted',result['warnings'][0])
        self.assertEqual((self.output/'originals/backups/home.1.json').read_bytes(),b'{')
        self.assertEqual(len(result['saves']),1)

    def test_existing_destination_is_never_overwritten(self):
        self.write('home.json',document());self.output.mkdir()
        sentinel=self.output/'keep';sentinel.write_bytes(b'keep')
        with self.assertRaises(ValueError):stage(self.source,self.output)
        self.assertEqual(sentinel.read_bytes(),b'keep')

    def test_output_within_source_rejected(self):
        self.write('home.json',document())
        with self.assertRaises(ValueError):stage(self.source,self.source/'new')
        self.assertFalse((self.source/'new').exists())

    def test_symlink_not_followed(self):
        self.write('home.json',document());(self.source/'backups').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):stage(self.source,self.output)
        self.assertFalse(self.output.exists())

    def test_duplicate_names_rejected(self):
        for names in [('presets/Desk.json','presets/desk.json'),('campaigns/'+CID+'.json','campaigns/'+CID.lower()+'.json')]:
            with self.subTest(names=names):
                for p in self.source.rglob('*.json'):p.unlink()
                for name in names:self.write(name,document())
                with self.assertRaises(ValueError):stage(self.source,self.output)
                self.assertFalse(self.output.exists())

    def test_schema_errors_not_silently_dropped(self):
        cases=[]
        doc=document();doc['format']=2;cases.append(doc)
        doc=document();doc['stored'][0]['id']='p0001';cases.append(doc)
        doc=document();doc['placed'][0]['mats']=[123];cases.append(doc)
        doc=document();doc['placed'][0]['solid']=0;cases.append(doc)
        doc=document();doc['placed'][0]['t']=[True,1,2];cases.append(doc)
        doc=document();doc['placed'][0]['t']=[float('nan'),1,2];cases.append(doc)
        doc=document();doc['placed'][0]['future']=1;cases.append(doc)
        doc=document();doc['vanilla'][KEY]={'hidden':False};cases.append(doc)
        for doc in cases:
            with self.subTest(doc=doc):
                with self.assertRaises(ValueError):convert(doc)

    def test_duplicate_json_keys_and_nonfinite_constants_rejected(self):
        for data in [b'{"format":1,"format":2}',b'{"value":NaN}',b'{"value":Infinity}']:
            with self.assertRaises(ValueError):parse_json(data,'test')

    def test_unicode_codec_and_invalid_gvas(self):
        values=dict(Scope='preset',DisplayName='Médecine 🚀',Entries=convert(document())['Entries'])
        data=self.codec.encode(LAYOUT,values)
        cls,decoded=self.codec.decode(data)
        self.assertEqual(decoded['DisplayName'],values['DisplayName'])
        self.assertEqual(cls,LAYOUT)
        for bad in [data[:-1],data+b'\0',b'X'+data[1:]]:
            with self.assertRaises(ValueError):self.codec.decode(bad)
        with self.assertRaises(ValueError):self.codec.encode(LAYOUT,{'NewField':1})

    def test_unknown_directories_are_explicitly_omitted(self):
        self.write('home.json',document());self.write('thumbs/picture.png',b'cache')
        result=stage(self.source,self.output)
        self.assertEqual(result['omitted_directories'],['thumbs'])
        self.assertTrue((self.source/'thumbs/picture.png').exists())
        self.assertFalse((self.output/'originals/thumbs').exists())


if __name__=='__main__':unittest.main()
