"""The creator handoff must include its dependencies without private files or art."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/prop_packs'))
from package_prop_authoring import package


class BundleTests(unittest.TestCase):
    def test_standalone_dependencies_and_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copy2(ROOT / 'LICENSE', root / 'LICENSE')
            shutil.copytree(ROOT / 'authoring/prop-packs', root / 'authoring/prop-packs')
            binaries = root / 'authoring/prop-packs/Plugins/ZComAuthoring/Binaries/Linux'
            binaries.mkdir(parents=True)
            (binaries / 'editor.so').write_bytes(b'local-only')
            for sub, names in [('tools/prop_packs', ['prop_pack.py', 'build_prop_pack.sh']),
                               ('unreal/scripts', ['build_prop_pack.py', 'verify_prop_pack.py'])]:
                (root / sub).mkdir(parents=True)
                for name in names:
                    shutil.copy2(ROOT / sub / name, root / sub / name)
            with zipfile.ZipFile(package(root)) as archive:
                names = archive.namelist()
                self.assertEqual(archive.read('LICENSE'), (ROOT / 'LICENSE').read_bytes())
                self.assertIn('Plugins/DenDesignerGF/Content/Runtime/BP_DenPropPack.uasset', names)
                self.assertIn('Plugins/ZComAuthoring/Content/Python/zcom_authoring.py', names)
                self.assertTrue(any(n.endswith('.Build.cs') for n in names))
                self.assertEqual(sum(n.endswith('.uasset') for n in names), 1)
                self.assertFalse(any(n.endswith(('.fbx', '.png', '.so', '.dll')) for n in names))
                for name, digest in json.loads(archive.read('SHA256SUMS.json')).items():
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)
                for name in names:
                    if name.endswith(('.py', '.sh', '.cpp', '.h', '.cs')):
                        text = archive.read(name).decode()
                        self.assertNotIn('/run/media/chats/', text, name)
                        self.assertNotIn('SWZCMergedKit', text, name)


if __name__ == '__main__':
    unittest.main()
