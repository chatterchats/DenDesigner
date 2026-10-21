"""Installation, conflict, interruption and source-preservation regression."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/migration"))
from den_save import Codec
from install_migration import install, NATIVE
from migrate_layouts import stage

CID = "BA3302BC4165EB931E86A39BFF208F71"
DOC = {"format": 1, "placed": [{"id": "p1", "mesh": "/Game/Props/SM_Test.SM_Test", "t": [1, 2, 3]}]}


class InstallTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "original"; self.source.mkdir()
        (self.source / "home.json").write_text(json.dumps(DOC))
        self.stage = self.root / "staged"
        self.saved = self.root / "SWZeroCompany/Saved"
        (self.saved / "SaveGames").mkdir(parents=True)
        self.target = self.saved / NATIVE
        self.not_running = patch("install_migration.game_running", return_value=False)
        self.not_running.start(); self.addCleanup(self.not_running.stop)

    def snapshot(self, root):
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def prepare(self):
        return stage(self.source, self.stage)

    def test_preview_does_not_create_any_game_files(self):
        self.prepare()
        before = self.snapshot(self.saved)
        result = install(self.stage, self.saved)
        self.assertFalse(result["applied"])
        self.assertEqual(result["install"], ["home-layout-0.sav"])
        self.assertEqual(before, self.snapshot(self.saved))
        self.assertFalse(self.target.parent.exists())

    def test_install_preserves_originals_and_unrelated_data_and_is_repeatable(self):
        self.prepare()
        self.target.mkdir(parents=True)
        sentinel = self.target / "preferences-layout-0.sav"; sentinel.write_bytes(b"keep preference bytes")
        user = self.saved / "SaveGames/campaign.sav"; user.write_bytes(b"keep campaign bytes")
        before = self.snapshot(self.source); staged = self.snapshot(self.stage)
        result = install(self.stage, self.saved, True)
        self.assertTrue(result["applied"])
        self.assertEqual((self.target / "home-layout-0.sav").read_bytes(),
                         (self.stage / NATIVE / "home-layout-0.sav").read_bytes())
        self.assertEqual(sentinel.read_bytes(), b"keep preference bytes")
        self.assertEqual(user.read_bytes(), b"keep campaign bytes")
        self.assertEqual(before, self.snapshot(self.source))
        self.assertEqual(staged, self.snapshot(self.stage))
        again = install(self.stage, self.saved, True)
        self.assertEqual(again["install"], [])
        self.assertEqual(again["already_identical"], ["home-layout-0.sav"])

    def test_other_bank_of_same_scope_blocks_import(self):
        self.prepare(); self.target.mkdir(parents=True)
        existing = self.target / "home-layout-5.sav"; existing.write_bytes(b"user data")
        before = self.snapshot(self.saved)
        with self.assertRaisesRegex(ValueError, "already exists"):
            install(self.stage, self.saved, True)
        self.assertEqual(before, self.snapshot(self.saved))

    def test_existing_draft_or_case_variant_blocks_import(self):
        self.prepare(); self.target.mkdir(parents=True)
        for name in ["home-draft-0.sav", "HOME-layout-0.sav"]:
            with self.subTest(name=name):
                existing = self.target / name; existing.write_bytes(b"draft")
                with self.assertRaises(ValueError): install(self.stage, self.saved, True)
                self.assertEqual(existing.read_bytes(), b"draft"); existing.unlink()

    def test_same_filename_with_different_data_is_preserved(self):
        self.prepare(); self.target.mkdir(parents=True)
        existing = self.target / "home-layout-0.sav"; existing.write_bytes(b"newer edit")
        with self.assertRaisesRegex(ValueError, "differs"): install(self.stage, self.saved, True)
        self.assertEqual(existing.read_bytes(), b"newer edit")

    def test_game_running_or_starting_during_staging_prevents_publication(self):
        self.prepare()
        for states in [[True], [False, True]]:
            with self.subTest(states=states), patch("install_migration.game_running", side_effect=states):
                with self.assertRaisesRegex(ValueError, "game|Game|Close"): install(self.stage, self.saved, True)
                self.assertFalse(self.target.exists())
        self.assertFalse(list(self.saved.rglob(".den-import-*")))

    def test_changed_original_or_save_hash_is_rejected(self):
        self.prepare()
        for relative in ["originals/home.json", str(NATIVE / "home-layout-0.sav")]:
            with self.subTest(relative=relative):
                p = self.stage / relative; before = p.read_bytes(); p.write_bytes(before + b" ")
                with self.assertRaisesRegex(ValueError, "Hash mismatch"): install(self.stage, self.saved, True)
                p.write_bytes(before)
        self.assertFalse(self.target.exists())

    def test_payload_disagreement_rejected_even_with_updated_manifest_hash(self):
        self.prepare(); codec = Codec()
        p = self.stage / NATIVE / "home-layout-0.sav"
        cls, doc = codec.decode(p.read_bytes()); doc["Entries"][0]["Position"] = [900, 2, 3]
        data = codec.encode(cls, doc); p.write_bytes(data)
        manifest = self.stage / "migration.json"; m = json.loads(manifest.read_text())
        m["saves"][p.name]["sha256"] = hashlib.sha256(data).hexdigest()
        manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, "differs from preserved JSON"):
            install(self.stage, self.saved, True)
        self.assertFalse(self.target.exists())

    def test_manifest_paths_and_symlinks_do_not_escape_staging(self):
        self.prepare()
        path = self.stage / "migration.json"; original = path.read_bytes()
        m = json.loads(original); record = m["originals"].pop("home.json")
        m["originals"]["../outside.json"] = record; path.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, "inside"): install(self.stage, self.saved, True)
        path.write_bytes(original)
        source = self.stage / "originals/home.json"; source.unlink(); source.symlink_to(self.source / "home.json")
        with self.assertRaisesRegex(ValueError, "Symlinks"): install(self.stage, self.saved, True)
        self.assertFalse(self.target.exists())

    def test_destination_symlink_does_not_write_elsewhere(self):
        self.prepare(); self.target.parent.mkdir(parents=True)
        outside = self.root / "outside"; outside.mkdir()
        self.target.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlinks"): install(self.stage, self.saved, True)
        self.assertEqual(list(outside.iterdir()), [])

    def test_unlisted_staged_file_rejected(self):
        self.prepare(); (self.stage / NATIVE / "unexpected.sav").write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError, "Unlisted"): install(self.stage, self.saved, True)

    def test_partial_publication_rolls_back_only_this_installs_files(self):
        (self.source / "backups").mkdir()
        (self.source / "backups/home.1.json").write_text(json.dumps(DOC))
        self.prepare(); self.target.mkdir(parents=True)
        sentinel = self.target / "preferences-layout-0.sav"; sentinel.write_bytes(b"keep")
        real_link = os.link; seen = []
        def fail_second(src, dst):
            seen.append(Path(dst).name)
            if len(seen) == 2:
                raise OSError("simulated disk error")
            return real_link(src, dst)
        with patch("install_migration.os.link", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "disk error"): install(self.stage, self.saved, True)
        self.assertEqual(seen[0], "home-layout-1.sav")  # latest first
        self.assertEqual(list(self.target.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"keep")
        self.assertTrue(install(self.stage, self.saved, True)["applied"])

    def test_retry_completes_identical_partial_install(self):
        (self.source / "backups").mkdir()
        (self.source / "backups/home.1.json").write_text(json.dumps(DOC))
        self.prepare(); self.target.mkdir(parents=True)
        newest = "home-layout-1.sav"
        (self.target / newest).write_bytes((self.stage / NATIVE / newest).read_bytes())
        result = install(self.stage, self.saved, True)
        self.assertEqual(result["already_identical"], [newest])
        self.assertEqual(result["install"], ["home-layout-0.sav"])

    def test_campaign_drafts_and_presets_install_with_correct_scopes(self):
        (self.source / "campaigns").mkdir()
        (self.source / "presets").mkdir()
        (self.source / "campaigns" / (CID.lower() + ".json")).write_text(json.dumps(DOC))
        (self.source / "campaigns" / (CID.lower() + ".draft.json")).write_text(json.dumps(DOC))
        (self.source / "presets/Chair.json").write_text(json.dumps(DOC))
        self.prepare()
        result = install(self.stage, self.saved, True)
        self.assertEqual(len(result["install"]), 4)
        self.assertTrue((self.target / ("campaign-" + CID + "-draft-0.sav")).is_file())

    def test_destination_conflict_appearing_during_staging_is_preserved(self):
        self.prepare()
        def starts_editing():
            self.target.mkdir(parents=True, exist_ok=True)
            (self.target / "home-layout-0.sav").write_bytes(b"new user save")
            return False
        calls = 0
        def check():
            nonlocal calls
            calls += 1
            return starts_editing() if calls == 2 else False
        with patch("install_migration.game_running", side_effect=check):
            with self.assertRaisesRegex(ValueError, "differs"): install(self.stage, self.saved, True)
        self.assertEqual((self.target / "home-layout-0.sav").read_bytes(), b"new user save")


if __name__ == "__main__":
    unittest.main()
