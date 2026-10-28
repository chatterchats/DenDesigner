"""Verify a deployable service patch and published document; no live service mutation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.sharing.contract import loads

ROOT = Path(__file__).resolve().parents[2]
SLICE = ROOT / 'tools/sharing/service_slice'
SERVICE = SLICE / 'foundation'


class CommunityServiceTest(unittest.TestCase):
    def test_valid_document_and_independent_catalog_source(self):
        raw = (SLICE / 'composition.json').read_bytes()
        doc = loads(raw)
        listing = json.loads((SLICE / 'listing.json').read_text())
        self.assertEqual(doc['content_type'], 'composition')
        self.assertEqual(len(doc['payload']['entries']), 1)
        self.assertEqual(doc['dependencies']['packs'], [])
        self.assertEqual(doc['dependencies']['unknown_assets'], [])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), listing['document_sha256'])
        self.assertEqual(len(raw), listing['document_bytes'])
        evidence = json.loads((SLICE / 'catalog-evidence.json').read_text())
        catalog = (ROOT / evidence['source']).read_bytes()
        self.assertEqual(hashlib.sha256(catalog).hexdigest(), evidence['catalog_sha256'])
        self.assertIn(evidence['catalog_row'], json.loads(catalog)['items'])
        self.assertEqual(doc['payload']['entries'][0]['Mesh'], evidence['catalog_row']['path'])
        inventory = json.loads((SLICE / 'test-inventory.json').read_text())
        self.assertEqual(inventory['target'], doc['compatibility'])
        self.assertEqual(inventory['available_assets'], {doc['payload']['entries'][0]['Mesh']: 'mesh'})

    @unittest.skipUnless(shutil.which('node'), 'Node needed for service integration')
    def test_reviewable_worker_patch_executes(self):
        manifest = json.loads((SERVICE / 'manifest.json').read_text())
        for relative, expected in manifest['files'].items():
            self.assertEqual(hashlib.sha256((SERVICE / relative).read_bytes()).hexdigest(), expected, relative)
        self.assertEqual(hashlib.sha256((SERVICE / 'src/worker.js').read_bytes()).hexdigest(),
                         (SLICE / 'source.sha256').read_text().split()[0])
        spec = importlib.util.spec_from_file_location('prepare_service_slice', SLICE / 'prepare.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            output = module.prepare(SERVICE, Path(temp) / 'prepared')
            for name in ('catalog.js', 'views.js', 'security.js'):
                shutil.copyfile(SERVICE / 'src' / name, output / name)
            for name in ('package.json', 'composition.json', 'worker.test.mjs'):
                shutil.copyfile(SLICE / name, output / name)
            run = subprocess.run(['node', str(output / 'worker.test.mjs')], text=True, capture_output=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('# tests 5', run.stdout)
            upstream = output / 'upstream'
            (upstream / 'src').mkdir(parents=True)
            (upstream / 'test').mkdir()
            shutil.copyfile(SLICE / 'package.json', upstream / 'package.json')
            for name in ('worker.js', 'catalog.js', 'views.js', 'security.js', 'published-composition.js'):
                shutil.copyfile(output / name, upstream / 'src' / name)
            shutil.copyfile(output / 'upstream-worker.test.js', upstream / 'test/worker.test.js')
            upstream_run = subprocess.run(['node', str(upstream / 'test/worker.test.js')], text=True, capture_output=True, timeout=30)
            self.assertEqual(upstream_run.returncode, 0, upstream_run.stdout + upstream_run.stderr)
            self.assertIn('# tests 8', upstream_run.stdout)
            self.assertEqual((output / 'worker.patch').read_bytes(), (SLICE / 'worker.patch').read_bytes())
            changed = (SERVICE / 'src/worker.js').read_text().replace("import { securityHeaders } from './security.js';", '')
            with self.assertRaisesRegex(ValueError, 'Worker changed'):
                module.patched_worker(changed)


if __name__ == '__main__':
    unittest.main()
