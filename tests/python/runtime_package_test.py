"""Runtime downloads keep one manager component, complete metadata and immutable payloads."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/build'))
from gf_build_info import CONTAINERS, PAKS
from package_gf import PACKAGE_ROOT, package


class RuntimePackageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        shutil.copytree(ROOT / 'distribution', self.root / 'distribution')
        shutil.copy2(ROOT / 'LICENSE', self.root / 'LICENSE')
        self.payloads = {name: ('fixture:' + name).encode() for name in CONTAINERS}
        for name, data in self.payloads.items():
            p = self.root / PAKS / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        version = json.loads((self.root / 'distribution/pak/modinfo.json').read_text())['version']
        self.build = {'version': version, 'prototype': False, 'entry_point': '/Fixture/Coordinator',
                      'cooked_assets': 76}
        self.cooked = patch('package_gf.require_cooked');self.cooked.start();self.addCleanup(self.cooked.stop)
        self.verify = patch('package_gf.verify', return_value=self.build)
        self.verify.start(); self.addCleanup(self.verify.stop)

    def test_one_nested_component_with_matching_metadata_and_hashed_inventory(self):
        result = package(self.root)
        expected = set(CONTAINERS) | {'modinfo.json', 'zcom-mod.json', 'README.md', 'CREDITS.md', 'LICENSE', 'manifest.json'}
        with zipfile.ZipFile(result['runtime']['archive']) as z:
            self.assertEqual(set(z.namelist()), {f'{PACKAGE_ROOT}/{name}' for name in expected})
            info = json.loads(z.read(f'{PACKAGE_ROOT}/modinfo.json'))
            mod = json.loads(z.read(f'{PACKAGE_ROOT}/zcom-mod.json'))
            self.assertEqual(info, {k: mod[v] for k, v in [('title', 'name'), ('version', 'version'),
                                                         ('author', 'author'), ('description', 'description')]})
            self.assertEqual(mod['version'], self.build['version'])
            self.assertEqual(mod['type'], ['iostore'])
            self.assertIs(mod['requires']['ue4ss'], False)
            self.assertEqual(mod['id'], 'community.den-designer')
            self.assertEqual(mod['game']['appId'], 2075800)
            manifest = json.loads(z.read(f'{PACKAGE_ROOT}/manifest.json'))
            self.assertEqual(manifest['preview'], '-preview.' in self.build['version'])
            self.assertEqual(manifest['verification_scope'], 'build_and_package')
            self.assertEqual(set(manifest['files']), set(z.namelist()) - {f'{PACKAGE_ROOT}/manifest.json'})
            for name, record in manifest['files'].items():
                data = z.read(name)
                self.assertEqual(record, {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
            for name, data in self.payloads.items():self.assertEqual(z.read(f'{PACKAGE_ROOT}/{name}'), data)
        self.assertEqual(set(result), {'runtime'})
        self.assertEqual(list((self.root / 'dist/packages').glob('*.zip')), [Path(result['runtime']['archive'])])
        self.assertEqual(package(self.root), result, 'Repeated packaging preserves bytes and checksums')

    def test_mismatched_metadata_refuses_to_write_archives(self):
        path = self.root / 'distribution/pak/zcom-mod.json'; original = path.read_bytes()
        for key, value in [('version', '0.0.0'), ('description', 'different'), ('id', 'community.other'),
                           ('type', ['ue4ss']), ('requires', {'ue4ss': True}), ('game', {'appId': 1})]:
            with self.subTest(key=key):
                doc = json.loads(original); doc[key] = value; path.write_text(json.dumps(doc))
                with patch('package_gf.archive') as write:
                    with self.assertRaises(ValueError):package(self.root)
                    write.assert_not_called()
        path.write_bytes(original)

    def test_same_version_changed_metadata_preserves_the_existing_archive(self):
        result = package(self.root); path = Path(result['runtime']['archive']); before = path.read_bytes()
        for name in ['modinfo.json', 'zcom-mod.json']:
            p = self.root / 'distribution/pak' / name
            doc = json.loads(p.read_text()); doc['description'] += ' Changed.'; p.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, 'already exists with different content'):package(self.root)
        self.assertEqual(path.read_bytes(), before)

    def test_stable_version_does_not_claim_live_game_verification(self):
        self.build['version'] = '1.0.0'
        for name in ['modinfo.json', 'zcom-mod.json']:
            p = self.root / 'distribution/pak' / name
            doc = json.loads(p.read_text()); doc['version'] = '1.0.0'; p.write_text(json.dumps(doc))
        result = package(self.root)
        with zipfile.ZipFile(result['runtime']['archive']) as z:
            manifest = json.loads(z.read(f'{PACKAGE_ROOT}/manifest.json'))
            self.assertFalse(manifest['preview'])
            self.assertEqual(manifest['verification_scope'], 'build_and_package')
            self.assertNotIn('full_regression_complete', manifest)
            self.assertNotIn(f'{PACKAGE_ROOT}/acceptance.json', z.namelist())


if __name__ == '__main__':unittest.main()
