"""Optional installer preflight and ownership checks in disposable fake games."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('install_community_tested', ROOT / 'tools/build/install_community.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class CommunityInstallTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'game'
        self.target = self.game / 'SWZeroCompany/Binaries/Win64'
        self.target.mkdir(parents=True)
        self.exe = self.target / 'SWZeroCompany.exe'
        self.exe.write_bytes(b'test executable, never launched')
        self.supported = hashlib.sha256(self.exe.read_bytes()).hexdigest()

    def archive(self, version='0.1.0-test.1', binary=b'test bridge', mutate=None, extra=None):
        files = {'Binaries/Win64/version.dll': binary,
                 'Binaries/Win64/den-community.exe': binary + b' worker',
                 'COMMUNITY-BRIDGE.md': b'test documentation', 'LICENSE': b'test license'}
        manifest = {'format': 1, 'version': version, 'requires_runtime': '1.1.0-preview.22',
                    'requires_ue4ss': False, 'requires_python': False, 'supported_executable_sha256': self.supported,
                    'files': {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in files.items()}}
        if mutate:
            mutate(manifest, files)
        path = self.root / (version + '.zip')
        with zipfile.ZipFile(path, 'w') as output:
            for name, data in files.items():
                output.writestr(name, data)
            output.writestr('manifest.json', json.dumps(manifest))
            if extra:
                output.writestr(*extra)
        return path

    def install(self, archive, running=lambda: False):
        return installer.install(archive, self.game, running=running, supported_exe=self.supported)

    def state(self):
        return {p.name: p.read_bytes() for p in self.target.iterdir() if p.is_file()}

    def test_install_idempotent_and_owned_upgrade(self):
        archive = self.archive()
        result = self.install(archive)
        self.assertEqual(result['archive_sha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(result['supported_executable_sha256'], self.supported)
        self.assertEqual(result['requires_runtime'], '1.1.0-preview.22')
        self.assertEqual(set(self.state()), {'SWZeroCompany.exe', 'version.dll', 'den-community.exe', installer.RECORD})
        before = self.state()
        self.assertEqual(self.install(archive), result)
        self.assertEqual(self.state(), before)
        newer = self.archive(version='0.1.0-test.2', binary=b'new bridge')
        upgraded = self.install(newer)
        self.assertEqual(upgraded['version'], '0.1.0-test.2')
        self.assertEqual((self.target / 'version.dll').read_bytes(), b'new bridge')
        self.assertEqual(json.loads((self.target / installer.RECORD).read_text())['binaries'], upgraded['binaries'])

    def test_unknown_existing_files_never_overwritten(self):
        archive = self.archive()
        for name in installer.BINARIES:
            with self.subTest(name=name):
                path = self.target / name
                path.write_bytes(b'unknown proxy')
                before = self.state()
                with self.assertRaisesRegex(ValueError, 'unknown existing'):
                    self.install(archive)
                self.assertEqual(self.state(), before)
                path.unlink()

    def test_owned_record_does_not_authorize_modified_binary(self):
        archive = self.archive()
        self.install(archive)
        (self.target / 'version.dll').write_bytes(b'some other mod replaced it')
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'unknown existing'):
            self.install(self.archive(version='0.1.0-test.2'))
        self.assertEqual(self.state(), before)

    def test_running_game_checked_before_any_write_and_again_before_stage(self):
        archive = self.archive()
        for answers in ([True], [False, True]):
            with self.subTest(answers=answers):
                sequence = iter(answers)
                before = self.state()
                with self.assertRaisesRegex(ValueError, 'running|started'):
                    self.install(archive, running=lambda: next(sequence))
                self.assertEqual(self.state(), before)

    def test_invalid_archives_and_wrong_executable_fail_before_writes(self):
        cases = [lambda m, f: f.__setitem__('LICENSE', b'tampered'),
                 lambda m, f: m.__setitem__('supported_executable_sha256', '0' * 64),
                 lambda m, f: m.__setitem__('requires_ue4ss', True),
                 lambda m, f: m['files'].pop('LICENSE')]
        for index, mutate in enumerate(cases):
            with self.subTest(index=index):
                before = self.state()
                with self.assertRaises(ValueError):
                    self.install(self.archive(version='bad' + str(index), mutate=mutate))
                self.assertEqual(self.state(), before)
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.install(self.archive(version='extra', extra=('../outside', b'bad')))
        self.exe.write_bytes(b'unsupported game update')
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'supported bridge build'):
            self.install(self.archive())
        self.assertEqual(self.state(), before)

    def test_crc_corruption_rejected_before_writes(self):
        archive = self.archive()
        raw = archive.read_bytes()
        position = raw.index(b'test bridge')
        archive.write_bytes(raw[:position] + bytes([raw[position] ^ 1]) + raw[position + 1:])
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'CRC'):
            self.install(archive)
        self.assertEqual(self.state(), before)

    def test_production_compatibility_is_fixed_and_symlinks_rejected(self):
        archive = self.archive()
        with self.assertRaisesRegex(ValueError, 'compatibility declaration'):
            installer.validated_archive(archive)  # Fake manifest cannot select an arbitrary production executable.
        destination = self.root / 'another mod.dll'
        destination.write_bytes(b'other')
        (self.target / 'version.dll').symlink_to(destination)
        with self.assertRaisesRegex(ValueError, 'symlink binary'):
            self.install(archive)
        self.assertEqual(destination.read_bytes(), b'other')
        self.assertFalse((self.target / installer.RECORD).exists())

    def test_proc_detection_matches_executable_arguments_not_shell_search_text(self):
        proc = self.root / 'proc'
        (proc / '123').mkdir(parents=True)
        (proc / '123/cmdline').write_bytes(b'bash\0-c\0rg value /Game/SWZeroCompany.exe\0')
        self.assertFalse(installer.game_running(proc))
        (proc / '124').mkdir()
        (proc / '124/cmdline').write_bytes(b'/usr/bin/wine\0C:\\Game Files\\SWZeroCompany\\Binaries\\Win64\\SWZeroCompany.exe\0')
        self.assertTrue(installer.game_running(proc))


if __name__ == '__main__':
    unittest.main()
