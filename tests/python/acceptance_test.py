"""Release packaging must fail closed on incomplete, stale or substituted evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/build'))
from gf_acceptance import REQUIREMENTS, SHIPPED_INPUTS, payload_inputs, verify_acceptance
from package_gf import package


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name in SHIPPED_INPUTS:
            p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(name)
        self.build = {'version': '0.7.0', 'prototype': False, 'containers': {'example.pak': 'candidate'}}
        proof = self.root / 'process.json'; proof.write_text(json.dumps({'pid': 123, 'ue4ss_loaded': False}))
        self.report = {'format': 1, 'build': copy.deepcopy(self.build), 'payload_inputs': payload_inputs(self.root),
                       'reviewed_by': 'unit-test fixture, not real acceptance', 'remaining': [],
                       'evidence': {'process.json': hashlib.sha256(proof.read_bytes()).hexdigest()},
                       'requirements': {key: {'passed': True, 'standalone': True, 'summary': 'Synthetic test only',
                                             'process_evidence': 'process.json', 'evidence': ['process.json']}
                                        for key in REQUIREMENTS}}
        self.path = self.root / 'acceptance.json'

    def verify(self):
        self.path.write_text(json.dumps(self.report))
        return verify_acceptance(self.root, self.build, self.path)

    def test_certificate_excludes_private_evidence_and_reviewer(self):
        certificate = self.verify()
        self.assertTrue(certificate['full_regression_complete'])
        self.assertEqual(set(certificate['requirements']), set(REQUIREMENTS))
        self.assertNotIn('process.json', json.dumps(certificate))
        self.assertNotIn('unit-test fixture', json.dumps(certificate))

    def test_missing_requirement_or_failed_result_rejected(self):
        for change in ('missing', 'failed', 'integer_true'):
            with self.subTest(change=change):
                old = copy.deepcopy(self.report)
                if change == 'missing': del self.report['requirements']['travel']
                else: self.report['requirements']['travel']['passed'] = False if change == 'failed' else 1
                with self.assertRaises(ValueError): self.verify()
                self.report = old

    def test_pending_or_absent_remaining_rejected(self):
        self.report['remaining'] = ['range check']
        with self.assertRaises(ValueError): self.verify()
        del self.report['remaining']
        with self.assertRaises(ValueError): self.verify()

    def test_source_or_container_build_mismatch_rejected(self):
        self.report['build']['containers']['example.pak'] = 'other build'
        with self.assertRaisesRegex(ValueError, 'exact verified build'): self.verify()

    def test_changed_document_or_tool_rejected(self):
        (self.root / SHIPPED_INPUTS[0]).write_text('updated instructions')
        with self.assertRaisesRegex(ValueError, 'Shipped files changed'): self.verify()

    def test_changed_evidence_rejected_even_when_still_valid_json(self):
        (self.root / 'process.json').write_text(json.dumps({'pid': 456, 'ue4ss_loaded': False}))
        with self.assertRaisesRegex(ValueError, 'evidence changed'): self.verify()

    def test_development_run_cannot_satisfy_standalone_requirement(self):
        self.report['requirements']['controls']['standalone'] = False
        with self.assertRaisesRegex(ValueError, 'Standalone runtime'): self.verify()

    def test_loaded_or_unknown_loader_state_rejected(self):
        for value in (True, None, 0):
            (self.root / 'process.json').write_text(json.dumps({'pid': 123, 'ue4ss_loaded': value}))
            self.report['evidence']['process.json'] = hashlib.sha256((self.root / 'process.json').read_bytes()).hexdigest()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'UE4SS absent'): self.verify()

    def test_unreferenced_or_missing_evidence_rejected(self):
        self.report['evidence']['extra.json'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'unreferenced'): self.verify()
        self.report['evidence'] = {}
        with self.assertRaises(ValueError): self.verify()

    def test_symlink_substitution_rejected(self):
        (self.root / 'process.json').rename(self.root / 'other.json')
        (self.root / 'process.json').symlink_to('other.json')
        with self.assertRaisesRegex(ValueError, 'symlinks'): self.verify()

    def test_path_traversal_rejected(self):
        self.report['evidence'] = {'../process.json': '0' * 64}
        for row in self.report['requirements'].values():
            row.update(evidence=['../process.json'], process_evidence='../process.json')
        with self.assertRaisesRegex(ValueError, 'Invalid evidence path'): self.verify()

    def test_stable_packaging_requires_gate_before_writing_archive(self):
        with patch('package_gf.verify', return_value=self.build), patch('package_gf.archive') as archive:
            with self.assertRaisesRegex(ValueError, 'requires --acceptance'): package(self.root)
            archive.assert_not_called()

    def test_preview_cannot_be_marked_as_accepted(self):
        build = dict(self.build, version='0.7.0-preview.4')
        with patch('package_gf.verify', return_value=build), patch('package_gf.archive') as archive:
            with self.assertRaisesRegex(ValueError, 'Preview packages cannot claim'): package(self.root, self.path)
            archive.assert_not_called()


if __name__ == '__main__':
    unittest.main()
