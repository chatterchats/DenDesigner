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


class NexusLinkTests(unittest.TestCase):
    """Same rule in the command-line tool and the in-editor tool."""
    def modules(self):
        import sys
        sys.path.insert(0,str(ROOT/'authoring/prop-packs/Plugins/DenPropPackEditor/Content/Python'))
        from den_pack_editor import model
        return [pack,model]
    def doc(self):return json.loads((ROOT/'authoring/prop-packs/example/pack.json').read_text())
    def test_valid_links_are_used_and_shipped(self):
        for module in self.modules():
            for url in ['https://www.nexusmods.com/games/starwarszerocompany/mods/42','https://www.nexusmods.com/starwarszerocompany/mods/42/']:
                doc=self.doc();doc['nexus_url']=url
                self.assertEqual(module.nexus_link(module.validate(doc)),url)
                self.assertEqual(module.sharing_manifest(doc)['nexus_url'],url)
        doc=self.doc();doc['nexus_url']='https://www.nexusmods.com/games/starwarszerocompany/mods/42'
        self.assertEqual(pack.provider(doc)['defaults']['NexusURL'],doc['nexus_url'])
    def test_missing_or_empty_link_falls_back_to_a_title_search(self):
        for module in self.modules():
            for value in [None,'']:
                doc=self.doc();doc['title']='Arcade Cabinets “Deluxe” & more'
                if value is not None:doc['nexus_url']=value
                module.validate(doc)
                self.assertEqual(module.nexus_link(doc),'https://www.nexusmods.com/games/starwarszerocompany/mods?title=Arcade%20Cabinets%20%E2%80%9CDeluxe%E2%80%9D%20%26%20more')
                self.assertNotIn('nexus_url',module.sharing_manifest(doc))
        self.assertNotIn('NexusURL',pack.provider(self.doc())['defaults'])
    def test_other_links_are_refused_with_a_clear_message(self):
        for module in self.modules():
            for url in ['http://www.nexusmods.com/games/starwarszerocompany/mods/42','https://www.nexusmods.com/games/othergame/mods/42',
                        'https://nexusmods.com.evil.test/games/starwarszerocompany/mods/42','https://www.nexusmods.com/games/starwarszerocompany/mods/42?x=1"',
                        'https://www.nexusmods.com/games/starwarszerocompany/mods/','www.nexusmods.com/games/starwarszerocompany/mods/42',42]:
                doc=self.doc();doc['nexus_url']=url
                with self.assertRaises(ValueError) as raised:module.validate(doc)
                self.assertIn('Nexus search for the pack title',str(raised.exception))
