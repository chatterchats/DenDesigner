"""Portable exports, dependency preflight, native migration and registry invariants."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.sharing import contract as c
from tools.sharing.registry import Registry, share_code
from tools.prop_packs.prop_pack import validate as validate_pack, sharing_manifest

FIXTURES = ROOT / 'tests/fixtures/sharing'
def fixture(name): return json.loads((FIXTURES / (name + '.json')).read_text())


class SharingTests(unittest.TestCase):
    def setUp(self):
        self.doc = fixture('den-v1')
        self.packs = fixture('packs')
        self.game = fixture('game-assets')

    def export(self, local, kind='den', **kw):
        return c.export_layout(local, kind, self.doc['metadata'],
            dict(self.doc['compatibility'], native_fingerprint='' if kind == 'composition' else self.doc['compatibility']['native_fingerprint']),
            self.packs, self.game, **kw)

    def available(self, doc):
        return {a['path']: a['kind'] for a in doc['dependencies']['assets']}

    def installed(self): return {p['id']: p['version'] for p in self.packs}

    def test_native_save_migration_is_allowlisted_and_round_trips(self):
        local = fixture('native-layout-v1')
        exported = self.export(local)
        self.assertEqual(exported, self.doc)
        self.assertEqual(c.loads(c.canonical(exported)), exported)
        for secret in ('SECRET-CAMPAIGN', 'private', 'Credentials', 'Preferences', 'Source', 'StorageKey'):
            self.assertNotIn(secret, c.canonical(exported).decode())
        restored = c.import_layout(exported, exported['compatibility'], self.installed(), self.available(exported))
        self.assertEqual([e['Kind'] for e in restored['Entries']], [0, 1, 2])
        self.assertTrue(restored['Entries'][2]['Hidden'])
        self.assertEqual(restored['Entries'][2]['Key'], local['Entries'][2]['Key'])
        self.assertEqual(restored['Entries'][2]['FingerprintPosition'], [100, 0, 0])
        self.assertEqual(self.export(restored), exported)
        self.assertEqual(set(restored), {'SchemaVersion', 'Entries'})
        with self.assertRaises(ValueError): self.export(dict(local, SchemaVersion=2))

    def test_composition_anchor_offsets_material_slots_and_rotation_survive(self):
        source = fixture('native-composition-v1')
        doc = self.export(source, 'composition')
        self.assertEqual(doc, fixture('composition-v1'))
        restored = c.import_layout(doc, doc['compatibility'], self.installed(), self.available(doc))
        self.assertEqual(restored['CompositionAnchor'], [500, 600, 0])
        self.assertEqual(restored['Entries'][1]['Position'], [60, 20, 30])
        self.assertEqual(restored['Entries'][0]['Materials'][0], '')
        self.assertEqual(self.export(restored, 'composition'), doc)
        legacy = dict(source); del legacy['HasCompositionAnchor']; del legacy['CompositionAnchor']
        with self.assertRaisesRegex(ValueError, 'explicit capture anchor'): self.export(legacy, 'composition')
        self.assertEqual(self.export(legacy, 'composition', anchor=[500, 600, 0]), doc)

    def test_dependencies_include_override_pack_exclude_unused_and_check_assets(self):
        self.assertEqual({p['id'] for p in self.doc['dependencies']['packs']}, {'furniture-pack', 'finishes-pack'})
        versions = self.installed(); available = self.available(self.doc)
        del available['/Finishes/Materials/MI_Blue.MI_Blue']
        self.assertIn('asset:/Finishes/Materials/MI_Blue.MI_Blue', c.compatibility_issues(self.doc, self.doc['compatibility'], versions, available))
        with self.assertRaises(ValueError): c.import_layout(self.doc, self.doc['compatibility'], versions, available)
        versions['furniture-pack'] = '1.0.1'
        self.assertIn('pack:furniture-pack', c.compatibility_issues(self.doc, self.doc['compatibility'], versions, self.available(self.doc)))
        unknown = self.export(dict(fixture('native-layout-v1'), Entries=[dict(fixture('native-layout-v1')['Entries'][0], Materials=['/External/MI_Unknown.MI_Unknown'])]))
        self.assertEqual(unknown['dependencies']['unknown_assets'], [dict(path='/External/MI_Unknown.MI_Unknown', kind='material')])
        available = self.available(unknown); available['/External/MI_Unknown.MI_Unknown'] = 'material'
        self.assertIn('unknown-owner:/External/MI_Unknown.MI_Unknown', c.compatibility_issues(unknown, unknown['compatibility'], versions, available))
        self.packs.append(copy.deepcopy(self.packs[0]))
        with self.assertRaisesRegex(ValueError, 'Conflicting'): self.export(fixture('native-layout-v1'))

    def test_native_compatibility_inventory_is_order_independent_and_strict(self):
        inventory = fixture('native-inventory')
        self.assertEqual(c.native_fingerprint(inventory), self.doc['compatibility']['native_fingerprint'])
        other = dict(key='/Game/Maps/Den.Den:PersistentLevel.Other', mesh=inventory[0]['mesh'], position=[2, 3, 4])
        self.assertEqual(c.native_fingerprint(inventory + [other]), c.native_fingerprint([other] + inventory))
        inventory[0]['position'][0] += 1
        target = dict(self.doc['compatibility'], native_fingerprint=c.native_fingerprint(inventory))
        with self.assertRaisesRegex(ValueError, 'native_fingerprint'):
            c.import_layout(self.doc, target, self.installed(), self.available(self.doc))
        with self.assertRaises(ValueError): c.native_fingerprint(inventory * 2)

    def test_reject_corruption_future_character_private_fields_and_invalid_values(self):
        mutations = [lambda d: d.update(schema_version=2), lambda d: d.update(content_type='character'),
            lambda d: d['payload']['entries'][0].update(Position=[float('nan'), 0, 0]),
            lambda d: d['payload']['entries'][0].update(Source='private'),
            lambda d: d['payload']['entries'][0].update(Scale=[0, 1, 1]),
            lambda d: d['payload']['entries'][0].update(Mesh='/home/private.uasset'),
            lambda d: d['payload']['entries'][0].update(Kind=True),
            lambda d: d['payload']['entries'].append(copy.deepcopy(d['payload']['entries'][0])),
            lambda d: d['dependencies']['assets'].pop(),
            lambda d: d['payload']['entries'][0].update(Position=[99, 0, 0]),
            lambda d: d['metadata']['media'][0].update(mime='image/svg+xml'),
            lambda d: d['metadata']['media'][0].update(url='file:///private')]
        for mutate in mutations:
            doc = copy.deepcopy(self.doc); mutate(doc)
            with self.subTest(doc=doc), self.assertRaises(ValueError): c.validate(doc)
        with self.assertRaises(ValueError): c.loads('{"format":1,"format":2}')
        with self.assertRaises(ValueError): c.loads(' ' * (c.MAX_BYTES + 1))
        doc = fixture('composition-v1'); doc['payload']['entries'] *= 65
        doc['integrity']['payload_sha256'] = c.digest(doc['payload'])
        with self.assertRaises(ValueError): c.validate(doc)

    def test_explicit_pack_ownership_validation_and_legacy_migration(self):
        for pack in self.packs: validate_pack(pack)
        pack = dict(self.packs[0], LocalPath='/private/authoring', Credentials='secret')
        sidecar = sharing_manifest(pack)
        self.assertNotIn('LocalPath', sidecar)
        self.assertNotIn('Credentials', sidecar)
        self.assertEqual(sidecar['assets'], pack['assets'])
        validate_pack(sidecar)
        for change in (lambda p: p['assets'].append(copy.deepcopy(p['assets'][0])),
                       lambda p: p['assets'][0].update(path='/Another/SM.SM'),
                       lambda p: p['assets'][0].update(kind='material')):
            pack = copy.deepcopy(self.packs[0]); change(pack)
            with self.assertRaises(ValueError): validate_pack(pack)
        legacy = copy.deepcopy(self.packs[0]); del legacy['assets']
        deps = c.dependencies(self.doc['payload'], [legacy, self.packs[1]], self.game)
        self.assertEqual(deps['assets'][0]['path'], self.doc['dependencies']['assets'][0]['path'])
        self.assertTrue(any(a['asset_id'].startswith('legacy-') for a in deps['assets']))


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:'); self.addCleanup(self.db.close)
        self.registry = Registry(self.db)
        self.doc = fixture('den-v1')
        self.listing = self.registry.create_listing('den', self.doc['metadata']['author']['id'])

    def test_revisions_are_immutable_codes_global_and_resolve_without_type(self):
        first = self.registry.publish(self.listing, self.doc)
        newer = copy.deepcopy(self.doc); newer['metadata']['title'] = 'New title'
        second = self.registry.publish(self.listing, newer)
        self.assertEqual((first['revision'], second['revision']), (1, 2))
        self.assertEqual(self.registry.resolve(first['share_code'])['document'], self.doc)
        self.assertEqual(self.registry.resolve(second['share_code'])['document'], newer)
        self.assertEqual(first['listing_id'], second['listing_id'])
        for query in ('UPDATE revisions SET document=document', 'DELETE FROM revisions', 'UPDATE listings SET content_type=content_type'):
            with self.assertRaises(sqlite3.IntegrityError): self.db.execute(query)
        self.db.rollback()
        with patch('tools.sharing.registry.share_code', side_effect=[first['share_code'], 'Z' * 32]):
            comp = fixture('composition-v1')
            listing = self.registry.create_listing('composition', comp['metadata']['author']['id'])
            published = self.registry.publish(listing, comp)
        self.assertEqual(published['share_code'], 'Z' * 32)
        self.assertEqual(self.registry.resolve('Z' * 32)['document']['content_type'], 'composition')

    def test_collision_exhaustion_rolls_back_and_identity_mismatch_fails(self):
        first = self.registry.publish(self.listing, self.doc)
        with patch('tools.sharing.registry.share_code', return_value=first['share_code']), self.assertRaisesRegex(ValueError, 'retry limit'):
            self.registry.publish(self.listing, self.doc)
        self.assertEqual(self.db.execute('SELECT count(*) FROM revisions').fetchone()[0], 1)
        doc = copy.deepcopy(self.doc); doc['metadata']['author']['id'] = 'other'
        with self.assertRaises(ValueError): self.registry.publish(self.listing, doc)
        self.assertEqual(self.registry.publish(self.listing, self.doc)['revision'], 2)
        self.assertIsNone(self.registry.resolve('A' * 32))
        with self.assertRaises(ValueError): self.registry.resolve('../bad')
        for _ in range(20): self.assertRegex(share_code(), r'^[A-Za-z0-9]{32}$')

    def test_separate_connections_allocate_distinct_revisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'community.sqlite')
            db = sqlite3.connect(path); registry = Registry(db)
            listing = registry.create_listing('den', self.doc['metadata']['author']['id']); db.close()
            def publish(_):
                connection = sqlite3.connect(path)
                try: return Registry(connection).publish(listing, self.doc)
                finally: connection.close()
            with ThreadPoolExecutor(max_workers=2) as pool:
                published = list(pool.map(publish, range(2)))
            self.assertEqual({p['revision'] for p in published}, {1, 2})
            self.assertEqual(len({p['share_code'] for p in published}), 2)

    def test_database_upgrade_reopen_preserves_published_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'community.sqlite')
            db = sqlite3.connect(path); registry = Registry(db)
            listing = registry.create_listing('den', self.doc['metadata']['author']['id'])
            published = registry.publish(listing, self.doc); db.close()
            db = sqlite3.connect(path); registry = Registry(db)
            self.assertEqual(registry.resolve(published['share_code'])['document'], self.doc)
            db.execute('PRAGMA user_version=2')
            with self.assertRaises(ValueError): Registry(db)
            db.close()

if __name__ == '__main__': unittest.main()
