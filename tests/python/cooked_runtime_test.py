"""Packaging must reject a missing or stale shipping-deserialization check."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/build'))
from package_gf import require_cooked


class CookedRuntimeTests(unittest.TestCase):
    def test_requires_success_for_exact_container_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            build = {'version': 'test', 'containers': {'runtime.utoc': 'abc'}, 'cooked_assets': 107}
            with self.assertRaisesRegex(ValueError, 'missing'):
                require_cooked(root, build)
            path = root / 'dist/verification/community/cooked-runtime/report.json'
            path.parent.mkdir(parents=True)
            valid = dict(version='test', containers=build['containers'], parsed_packages=107, errors=0, script_data=True)
            for change in [{'containers': {'runtime.utoc': 'old'}}, {'errors': 1}, {'script_data': False}, {'parsed_packages': 106}]:
                path.write_text(json.dumps(dict(valid, **change)))
                with self.assertRaisesRegex(ValueError, 'stale or failed'):
                    require_cooked(root, build)
            path.write_text(json.dumps(valid))
            require_cooked(root, build)
