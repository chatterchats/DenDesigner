"""The editor handoff includes Python and UMG, but no custom binary or compiler inputs."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/prop_packs'))
from package_editor_authoring import package


class EditorBundleTests(unittest.TestCase):
    def setup_root(self,root):
        shutil.copy2(ROOT/'LICENSE',root/'LICENSE')
        shutil.copytree(ROOT/'authoring/prop-packs',root/'authoring/prop-packs')

    def test_complete_bundle_without_native_modules(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.setup_root(root)
            with zipfile.ZipFile(package(root)) as z:
                names=z.namelist()
                self.assertIn('Plugins/DenPropPackEditor/Content/UI/EUW_PropPacks.uasset',names)
                self.assertIn('Plugins/DenPropPackEditor/Content/Python/init_unreal.py',names)
                self.assertIn('Plugins/DenPropPackEditor/Content/Python/den_pack_editor/service.py',names)
                self.assertIn('Plugins/DenDesignerGF/Content/Runtime/BP_DenPropPack.uasset',names)
                self.assertFalse(any(n.endswith(('.cpp','.h','.cs','.so','.dll','.sh','.bat','.pyc')) for n in names))
                self.assertFalse(any('ZComAuthoring' in n or '/Binaries/' in n for n in names))
                plugin=json.loads(z.read('Plugins/DenPropPackEditor/DenPropPackEditor.uplugin'))
                self.assertFalse(plugin.get('Modules'))
                self.assertIn('PythonScriptPlugin',[p['Name'] for p in plugin['Plugins']])
                meta=json.loads(z.read('manifest.json'))
                self.assertTrue(meta['bundled_python'])
                self.assertFalse(meta['requires_external_python'])
                self.assertFalse(meta['requires_manual_scripts'])
                self.assertIsNone(meta['engine_build_id'])
                for name,digest in meta['files'].items():self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(),digest)

    def test_build_and_personal_files_are_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.setup_root(root)
            plugin=root/'authoring/prop-packs/Plugins/DenPropPackEditor'
            for name in ('Binaries/Win64/old.dll','Source/old.cpp','Content/Python/__pycache__/old.pyc','Saved/private.txt'):
                p=plugin/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'not for export')
            with zipfile.ZipFile(package(root)) as z:
                self.assertFalse(any('old.' in n or 'private' in n for n in z.namelist()))

if __name__=='__main__':unittest.main()
