import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('prop_pack',ROOT/'tools/prop_packs/prop_pack.py')
pack=importlib.util.module_from_spec(spec);spec.loader.exec_module(pack)

class ManifestTests(unittest.TestCase):
    def setUp(self):self.doc=json.loads((ROOT/'authoring/prop-packs/example/pack.json').read_text())
    def test_scaffold_preserves_existing_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=pack.generate(self.doc,tmp)
            asset=folder/'Content/user.uasset';asset.write_bytes(b'keep')
            pack.generate(self.doc,tmp)
            self.assertEqual(asset.read_bytes(),b'keep')
            self.assertEqual(json.loads((folder/'Authoring/provider.json').read_text())['parent'],pack.BASE)
            self.assertIn({'Name':'DenDesignerGF','Enabled':True},json.loads((folder/(self.doc['plugin']+'.uplugin')).read_text())['Plugins'])
    def test_editor_mount_never_changes_shipping_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=pack.generate(self.doc,tmp,editor_mounted=True)
            source=json.loads((folder/(self.doc['plugin']+'.uplugin')).read_text())
            self.assertFalse(source['ExplicitlyLoaded'])
            self.assertNotIn('BuiltInInitialFeatureState',source)
            shipping=pack.descriptor(json.loads((folder/'Authoring/pack.json').read_text()))
            self.assertTrue(shipping['ExplicitlyLoaded'])
            self.assertEqual(shipping['BuiltInInitialFeatureState'],'Active')
            self.assertEqual(pack.provider(self.doc)['parent'],pack.BASE)

    def test_bad_headers(self):
        for field,value in [('schema',2),('schema',True),('plugin','../bad'),('plugin','DenDesignerGF'),('id','../bad'),('title',' '),('version','x\n'),('props',[])]:
            with self.subTest(field=field,value=value):
                doc=copy.deepcopy(self.doc);doc[field]=value
                with self.assertRaises(ValueError):pack.validate(doc)
    def test_bad_rows(self):
        for field,value in [('mesh','/Game/X.X'),('mesh','/DenPropsExample/X.X:part'),('mesh','/DenPropsExample/X.Y'),('name',''),('size',[float('nan'),1,1]),('size',[-1,1,1]),('size',[True,1,1]),('collision',1),('tags','x'*513)]:
            with self.subTest(field=field,value=value):
                doc=copy.deepcopy(self.doc);doc['props'][0][field]=value
                with self.assertRaises(ValueError):pack.validate(doc)
    def test_duplicate_meshes(self):
        self.doc['props'].append(copy.deepcopy(self.doc['props'][0]))
        with self.assertRaises(ValueError):pack.validate(self.doc)
    def test_metadata_escaping(self):
        self.doc['props'][0]['name']='Chair "A"'
        defaults=pack.provider(pack.validate(self.doc))['defaults']
        self.assertIn('\\"A\\"',defaults['Labels'])
        self.assertNotIn('load_asset',json.dumps(pack.provider(self.doc)))

if __name__=='__main__':unittest.main()
