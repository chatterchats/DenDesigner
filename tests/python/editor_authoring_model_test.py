"""Schema, ownership and export checks independent of Unreal."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'authoring/prop-packs/Plugins/DenPropPackEditor/Content/Python'))
from den_pack_editor import model


def pack():
    return dict(schema=1,plugin='MyPack',id='my-pack',title='Furniture',author='Test',version='1.0',props=[dict(name='Chair',mesh='/MyPack/Props/Chair.Chair',size=[1,2,3],collision=True,tags='',description='')])


class ModelTests(unittest.TestCase):
    def test_empty_draft_is_not_publishable(self):
        doc=pack();doc['props']=[]
        self.assertEqual(model.validate(doc,allow_empty=True),doc)
        with self.assertRaises(ValueError):model.validate(doc)

    def test_invalid_metadata_rejected(self):
        for key,value in [('plugin','../escape'),('plugin','DenPropPackEditor'),('id','UPPER'),('title',' padded')]:
            with self.subTest(key=key,value=value):
                doc=pack();doc[key]=value
                with self.assertRaises(ValueError):model.validate(doc)
        for key,value in [('mesh','/OtherPack/Chair.Chair'),('size',[float('nan'),0,0]),('size',[-1,0,0]),('collision',1),('name','bad\nname')]:
            with self.subTest(key=key):
                doc=pack();doc['props'][0][key]=value
                with self.assertRaises(ValueError):model.validate(doc)

    def test_duplicate_mesh_case_insensitive(self):
        doc=pack();doc['props'].append(copy.deepcopy(doc['props'][0]))
        doc['props'][1]['mesh']='/MyPack/Props/CHAIR.CHAIR'
        with self.assertRaises(ValueError):model.validate(doc)

    def test_stable_identity_and_no_folder_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'Plugins').mkdir();doc=pack()
            folder=model.save(root,doc)
            self.assertEqual(model.read(folder),doc)
            with self.assertRaises(ValueError):model.save(root,doc)
            doc['title']='Changed';model.save(root,doc,folder)
            doc['id']='changed-id'
            with self.assertRaises(ValueError):model.save(root,doc,folder)
            self.assertEqual(model.read(folder)['id'],'my-pack')

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'Plugins').mkdir();(root/'outside').mkdir()
            (root/'Plugins/MyPack').symlink_to(root/'outside',target_is_directory=True)
            with self.assertRaises(ValueError):model.owned_folder(root,'MyPack')

    def test_inventory_full_paths_and_namespace(self):
        doc=pack()
        entries=['<ContainerHeader>']+[f'../../../SWZeroCompany/Plugins/MyPack/Content/{p}.uasset' for p in ('MyPack','BP_PropPack','Props/Chair')]
        listing='\n'.join(f'Display: "{p}" offset: 1' for p in entries)
        self.assertEqual(len(model.inventory(listing,doc)),4)
        with self.assertRaises(ValueError):model.inventory(listing.replace('Props/Chair','Wrong/Chair'),doc)
        with self.assertRaises(ValueError):model.inventory(listing+'\nDisplay: "../../../SWZeroCompany/Content/Leak.uasset" offset: 1',doc)

    def test_shipping_descriptor_activates_without_native_module(self):
        source=model.descriptor(pack());shipping=model.descriptor(pack(),True)
        self.assertFalse(source['ExplicitlyLoaded']);self.assertTrue(source['EnabledByDefault'])
        self.assertTrue(shipping['ExplicitlyLoaded']);self.assertEqual(shipping['BuiltInInitialFeatureState'],'Active')
        self.assertNotIn('Modules',shipping)

if __name__=='__main__':unittest.main()
