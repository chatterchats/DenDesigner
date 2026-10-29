"""HoloNet window logic, run offline from the generated Blueprint specs.

The bridge (native/community/core.c) produces the wire text from the real
HoloNet fixtures; the generated graphs consume it through
tools/build/simulate_specs.py. This checks what the graphs compute. Unreal
compiles them and the in-game checklist covers the rest.
"""
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/build'))
from simulate_specs import Simulator, ENGINE, KML  # noqa: E402
import lint_specs  # noqa: E402

RUNTIME = '/DenDesignerGF/Runtime/'
EDITOR = '/DenDesignerGF/Editor/'
HOST = RUNTIME + 'BP_DenEditorHost'
ITEM = EDITOR + 'BP_DenCatalogItem'
FIXTURES = ROOT / 'tests/fixtures/sharing'
ENGINE.setdefault(KML + 'BreakRotator', lambda InRot=(0, 0, 0): dict(Roll=InRot[0], Pitch=InRot[1], Yaw=InRot[2]))


class HolonetSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        library = Path(cls.temp.name) / 'core.so'
        subprocess.run(['cc', '-shared', '-fPIC', str(ROOT / 'native/community/core.c'), '-o', str(library)], check=True)
        cls.core = ctypes.CDLL(str(library))
        cls.core.dd_gallery_page.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t]
        cls.core.dd_shares_page.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t]
        cls.listings = [json.loads((FIXTURES / f'holonet-composition-{name}.listing.json').read_text())['item'] for name in ('pack', 'base')]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.started = []
        self.sim = Simulator.load(overrides={
            'NewCatalogItem': self.new_item,
            'StartCommunityTransfer': lambda obj, **kw: self.started.append(kw),
            'ReleaseCommunityMailbox': lambda obj: None,
            'CancelCommunityFetch': lambda obj: None,
            'RefreshCommunityDetailPreview': lambda obj: None,
        })
        self.catalog = self.sim.instance(RUNTIME + 'BP_DenCatalog')
        self.panel = self.sim.widgets(EDITOR + 'WBP_DenHolonet')
        self.host = self.sim.instance(HOST, CatalogProvider=self.catalog, CommunityPanel=self.panel, CommunityToken='tok', UIOpen=True)

    def new_item(self, obj, **fields):
        item = self.sim.instance(ITEM)
        item.vars.update({k: v for k, v in fields.items() if k in item.vars})
        return {'Item': item}

    def gallery_lines(self, items, page=0, pages=1, total=None):
        data = json.dumps(dict(api_version='v1', items=items, page=page + 1, pages=pages, total=len(items) if total is None else total)).encode()
        out = ctypes.create_string_buffer(48 * 1024)
        self.assertTrue(self.core.dd_gallery_page(data, len(data), 0, page, out, len(out)))
        return ['ZCOM-COMMUNITY\t1\ttok'] + out.value.decode().rstrip('\n').split('\n') + ['end']

    def load_gallery(self, items, **kw):
        self.host.vars['CommunityWireLines'] = self.gallery_lines(items, **kw)
        self.sim.run(self.host, 'ReadCommunityGallery')

    def test_cards_readiness_and_library_badge(self):
        self.host.vars['CommunitySourceNames'] = ['HoloNet base-game fix H7854VMD']
        self.load_gallery(self.listings)
        v = self.host.vars
        self.assertEqual(v['CommunityBrowseCodes'], ['T93765D1', 'H7854VMD'])
        self.assertEqual(v['CommunityBrowseReady'], [False, True])
        self.assertEqual(v['CommunityBrowseRequirements'][0], 'Needs the Arcade Cabinets “Deluxe” prop pack. Get it on Nexus, then import.')
        self.assertEqual(v['CommunityBrowseRequirements'][1], 'Ready to import · base game only')
        self.assertEqual(v['CommunityBrowsePackURLs'], ['https://www.nexusmods.com/games/starwarszerocompany/mods/42', ''])
        self.assertEqual(v['CommunityBrowseDescriptions'][0], 'Base game, a pack\nand an unknown mod. Café ☃')
        rows = v['CommunityBrowseRows']
        self.assertEqual(rows[0].vars['Title'], 'Rook’s arcade nook — v2…')
        self.assertEqual(rows[0].vars['Detail'], 'by Rook · 3 parts')
        self.assertEqual(rows[1].vars['Detail'], 'by Rook · 1 parts · IN LIBRARY')
        self.assertEqual(rows[0].vars['Preview'], 'Needs Arcade Cabinets “Deluxe” (prop pack)')
        self.assertEqual(len(self.panel.vars['CommunityListings'].items), 2)
        self.assertEqual(self.panel.vars['GalleryStatus'].text, 'Page 1 of 1 · builds: 2')

    def test_installed_pack_makes_a_build_ready(self):
        self.catalog.vars['RegisteredPackIDs'] = ['arcade-cabinets']
        self.load_gallery(self.listings[:1])
        self.assertEqual(self.host.vars['CommunityBrowseReady'], [True])
        self.assertEqual(self.host.vars['CommunityBrowseRequirements'][0],
                         'Ready to import · some parts come from mods HoloNet doesn’t list; they won’t appear unless you have them · uses Arcade Cabinets “Deluxe”')

    def test_only_what_i_can_use_hides_cards_on_this_page(self):
        self.host.vars['CommunityBrowseUsable'] = True
        self.load_gallery(self.listings, pages=3, total=20)
        self.assertEqual([i.vars['Title'] for i in self.panel.vars['CommunityListings'].items], ['HoloNet base-game fixture'])
        self.assertEqual(self.panel.vars['GalleryStatus'].text, 'Page 1 of 3 · builds: 20 · hidden here: 1')
        self.sim.run(self.host, 'ToggleHolonetUsable')
        self.assertEqual(len(self.panel.vars['CommunityListings'].items), 2)

    def test_detail_pane(self):
        footprinted = dict(self.listings[1], footprint_cm=[62, 40, 118])
        self.load_gallery([self.listings[0], footprinted])
        for index, expected in [(0, dict(DetailTitle='Rook’s arcade nook — v2…', DetailByline='by Rook · revision 1 · 2026-10-29', FactPartsValue='3', FactFootprintValue='Not given', FactCodeValue='T93765D1')),
                                (1, dict(FactFootprintValue='0.6 × 0.4 × 1.2 m', DetailReadyText='Ready to import · base game only'))]:
            self.host.vars['CommunityBrowseSelected'] = index
            self.sim.run(self.host, 'RefreshCommunityDetail')
            for field, value in expected.items():
                self.assertEqual(self.panel.vars[field].text, value, field)
            self.assertEqual(self.panel.vars['GetPack'].visibility, 'Visible' if index == 0 else 'Collapsed')
        self.host.vars['CommunityBrowseSelected'] = -1
        self.sim.run(self.host, 'RefreshCommunityDetail')
        self.assertEqual(self.panel.vars['DetailTitle'].text, 'Select a build')
        self.assertEqual(self.panel.vars['DetailReady'].visibility, 'Collapsed')

    def test_browse_request_carries_sort_and_search(self):
        self.host.vars.update(ActivePanel='community', CommunityArea='browse', CommunityBrowseSearch='café', CommunityBrowsePage=2)
        self.sim.overrides['CanStartCommunityBrowse'] = lambda obj: {'Allowed': True}
        self.sim.run(self.host, 'SortHolonetImports')
        self.assertEqual(self.started[-1], {'Input': 'CATALOG/0', 'Payload': 'imports\tall\tcafé'})
        self.assertEqual(self.host.vars['CommunityBrowseSort'], 'imports')

    def my_shares(self):
        items = [dict(code='T93765D1', title='Rook’s arcade nook — v2…', revision=1, latest_revision=3, import_count=12),
                 dict(code='H7854VMD', title='Old shelf', revision=2, import_count=0, hidden=True)]
        data = json.dumps(dict(items=items, page=1, pages=1, total=2)).encode()
        out = ctypes.create_string_buffer(8192)
        self.assertTrue(self.core.dd_shares_page(data, len(data), 0, out, len(out)))
        self.host.vars['CommunityWireLines'] = ['ZCOM-COMMUNITY\t1\ttok'] + out.value.decode().rstrip('\n').split('\n') + ['end']
        self.sim.run(self.host, 'ReadHolonetShares')

    def test_my_shares_list_and_picking_one_to_update(self):
        self.host.vars['CommunityProfile'] = 'Connected as Rook - Remembered connection.'
        self.my_shares()
        v = self.host.vars
        self.assertEqual(v['HolonetShareCodes'], ['T93765D1', 'H7854VMD'])
        self.assertEqual(v['HolonetShareRevisions'], [3, 2])
        self.assertEqual([i.vars['Title'] for i in self.panel.vars['ShareListings'].items],
                         ['Rook’s arcade nook — v2…  ·  T93765D1  ·  revision 3  ·  imports: 12  ·  Public', 'Old shelf  ·  H7854VMD  ·  revision 2  ·  imports: 0  ·  Hidden'])
        self.assertEqual(self.panel.vars['SharesCount'].text, 'Shares: 2')
        self.sim.run(self.host, 'PickHolonetShare', Key='share:1')
        self.assertEqual((v['HolonetShareTarget'], v['HolonetShareUpdate'], v['CommunityArea']), (1, True, 'upload'))
        self.assertEqual(self.panel.vars['ShareUpdateLabel'].text, 'Update Old shelf · H7854VMD (becomes revision 3)')
        self.assertEqual(self.panel.vars['SubmitCommunityLabel'].text, 'Share update')
        self.assertEqual(self.panel.vars['ChangelogBox'].visibility, 'Visible')
        self.assertEqual(self.panel.vars['ShareNote'].text, 'Shares the saved copy of this composition, not your unsaved edits. Sharing as Rook.')
        self.sim.run(self.host, 'ShareHolonetNew')
        self.assertEqual(self.panel.vars['ChangelogBox'].visibility, 'Collapsed')
        self.assertEqual(self.panel.vars['SubmitCommunityLabel'].text, 'Share')

    def test_share_form_states(self):
        self.sim.run(self.host, 'RefreshHolonetShare')
        self.assertEqual((self.panel.vars['ShareOffline'].visibility, self.panel.vars['ShareFormFields'].visibility), ('Visible', 'Collapsed'))
        self.host.vars.update(CommunityProfile='Connected as Rook', HolonetShowResult=True, CommunityPublicCode='T93765D1')
        self.sim.run(self.host, 'RefreshHolonetShare')
        self.assertEqual((self.panel.vars['ShareOffline'].visibility, self.panel.vars['ShareResult'].visibility, self.panel.vars['ShareFooter'].visibility), ('Collapsed', 'Visible', 'Collapsed'))

    def test_publish_wire(self):
        self.host.vars.update(CommunityProfile='Connected as Rook', CommunityUploadJSON='{"payload":{}}', CommunityUploadThumbnail='Composition_0123abcd.png',
                              CommunityUploadLibraryID='7', CommunitySourceLibraryID='7')
        self.sim.overrides.update(CanEdit=lambda obj: {'Ready': True}, EnsureCompositionService=lambda obj: None, CommunitySourceCurrent=lambda obj: {'Accepted': True})
        self.panel.vars['PublishTitle'].text = 'Back\\bar'
        self.panel.vars['PublishDescription'].text = 'Two tables'
        self.panel.vars['PublishChangelog'].text = 'Moved bottles'
        self.my_shares()
        self.sim.run(self.host, 'SubmitCommunityComposition')
        self.assertEqual(self.started[-1], {'Input': 'PUBLISH', 'Payload': 'Composition_0123abcd.png\ntitle\tBack\\\\bar\ndescription\tTwo tables\npayload\n{"payload":{}}'})
        self.host.vars.update(HolonetShareTarget=0, HolonetShareUpdate=True)
        self.sim.engine['/Script/Engine.BlueprintPathsLibrary:FileExists'] = lambda InPath='': {'ReturnValue': InPath == 'C:/Saved/ZComDen/thumbs/Composition_0123abcd_512.png'}
        self.sim.run(self.host, 'SubmitCommunityComposition')
        self.assertEqual(self.started[-1]['Payload'], 'Composition_0123abcd_512.png\ntitle\tBack\\\\bar\ndescription\tTwo tables\nupdate\tT93765D1\t3\nchangelog\tMoved bottles\npayload\n{"payload":{}}')
        self.panel.vars['PublishTitle'].text = '   '
        before = len(self.started)
        self.sim.run(self.host, 'SubmitCommunityComposition')
        self.assertEqual((len(self.started), self.host.vars['CommunityMessage']), (before, 'Give the build a title first.'))

    def test_picking_a_source_suggests_the_matching_share(self):
        self.host.vars['CommunityProfile'] = 'Connected as Rook'
        self.my_shares()
        def select(obj, Key=''):
            obj.vars['CommunitySourceName'] = 'old shelf'
        def review(obj):
            obj.vars['CommunityUploadName'] = obj.vars['CommunitySourceName']
        self.sim.overrides.update(SelectCommunitySourceCard=select, ReviewCommunityComposition=review)
        self.sim.run(self.host, 'PickHolonetSource', Key='x')
        self.assertEqual((self.host.vars['HolonetShareTarget'], self.host.vars['HolonetShareUpdate']), (1, True))
        self.assertEqual(self.panel.vars['PublishTitle'].text, 'old shelf')
        self.sim.overrides['SelectCommunitySourceCard'] = lambda obj, Key='': obj.vars.update(CommunitySourceName='Something new')
        self.sim.run(self.host, 'PickHolonetSource', Key='y')
        self.assertEqual((self.host.vars['HolonetShareTarget'], self.host.vars['HolonetShareUpdate']), (-1, False))
        self.assertEqual(self.panel.vars['PublishTitle'].text, 'old shelf')  # a typed title is kept

    def test_areas_rail_and_subtitle(self):
        self.sim.overrides.update(EnsureHolonetShares=lambda obj: None, StyleEditorToggle=lambda obj, **kw: obj.vars.setdefault('toggled', []).append((kw['Label'].name, kw['On'])))
        self.sim.run(self.host, 'SetCommunityArea', Area='shares')
        visible = {name for name in ['BrowseArea', 'BrowseDenArea', 'UploadArea', 'SharesArea', 'AccountArea'] if self.panel.vars[name].visibility == 'Visible'}
        self.assertEqual(visible, {'SharesArea'})
        self.assertEqual(self.panel.vars['HolonetSubtitle'].text, 'My Shares')
        rail = dict(t for t in self.host.vars['toggled'] if t[0].startswith('Rail'))
        self.assertEqual({k for k, on in rail.items() if on}, {'RailSharesLabel'})
        self.sim.run(self.host, 'SetCommunityArea', Area='browse')
        self.assertEqual(self.panel.vars['HolonetSubtitle'].text, 'Builds shared by other captains')

    def test_connection_pill(self):
        for profile, pill in [('', 'Not connected'), ('Connected as Rook - Remembered connection.', 'Connected as Rook'),
                              ('Disconnected for this session.', 'Not connected'), ('Connected to HoloNet', 'Connected to HoloNet')]:
            self.host.vars['CommunityProfile'] = profile
            self.sim.run(self.host, 'RefreshCommunityFeedback')
            self.assertEqual(self.panel.vars['ConnectionLabel'].text, pill)

    def test_successful_share_shows_the_code_and_bumps_the_revision(self):
        self.host.vars.update(CommunityProfile='Connected as Rook', CommunityPending=True, CommunityRequest='PUBLISH')
        self.my_shares()
        self.host.vars.update(HolonetShareTarget=0, HolonetShareUpdate=True, CommunityPending=True)
        self.sim.run(self.host, 'FailCommunityFetch', Token='tok', Message='Published: https://zcom.app/comp/T93765D1')
        v = self.host.vars
        self.assertEqual((v['CommunityPublicCode'], v['CommunityPublicURL']), ('T93765D1', 'https://zcom.app/comp/T93765D1'))
        self.assertEqual(self.panel.vars['ShareResultCode'].text, 'T93765D1')
        self.assertEqual(self.panel.vars['PublishResult'].text, 'zcom.app/comp/T93765D1')
        self.assertEqual(self.panel.vars['ShareResultTitle'].text, 'Shared · the update is live')
        self.assertEqual(v['HolonetShareRevisions'][0], 4)
        self.assertEqual(self.panel.vars['ShareResult'].visibility, 'Visible')
        self.assertTrue(v['HolonetSharesStale'])

    def test_submission_declares_packs_and_footprint(self):
        self.catalog.vars.update(RegisteredPackIDs=['arcade-cabinets'], PackMounts=['ArcadePack'], PackTitles=['Arcade Cabinets “Deluxe”'], PackVersions=['1.2.0'], PackNexusURLs=[''])
        queue = self.sim.instance(RUNTIME + 'BP_DenThumbnails', FootprintNames=['Composition_0123abcd.png'], FootprintSizes=[(62.2, 40, 118.6)])
        self.host.vars['ThumbnailWorker'] = queue
        self.sim.overrides.update(ValidAssetPath=lambda obj, Path='': {'Valid': True}, ValidCompositionTransform=lambda obj, Value=None: {'Valid': True})
        part = lambda mesh, materials=(): dict(Mesh=mesh, Position=(80.5, 0, 0), Rotation=(0, 0, 90), Scale=(1, 1, 1), CollisionMode=0, Materials=list(materials))
        doc = self.sim.instance(RUNTIME + 'BP_DenLayoutSave', Entries=[part('/Game/A/B.B'), part('/ArcadePack/Meshes/SM.SM', ['', '/ArcadePack/M/MI.MI'])])
        out = self.sim.run(self.host, 'BuildCommunitySubmission', Document=doc, Thumbnail='Composition_0123abcd.png')
        sent = json.loads(out['JSON'])
        self.assertTrue(out['Ready'])
        self.assertEqual(sent['metadata']['footprint_cm'], [62, 40, 119])
        self.assertEqual(sent['dependencies']['packs'], [dict(id='arcade-cabinets', mount='ArcadePack', version='1.2.0', title='Arcade Cabinets “Deluxe”', url='')])
        self.assertEqual([e['Mesh'] for e in sent['payload']['entries']], ['/Game/A/B.B', '/ArcadePack/Meshes/SM.SM'])
        out = self.sim.run(self.host, 'BuildCommunitySubmission', Document=doc, Thumbnail='Composition_ffffffff.png')
        self.assertNotIn('footprint_cm', json.loads(out['JSON'])['metadata'])
        summary = self.sim.run(self.catalog, 'DescribeSources', Paths=['/Game/A/B.B', '/ArcadePack/Meshes/SM.SM', '/ArcadePack/M/MI.MI', '/OtherMod/X.X'])['Summary']
        self.assertEqual(summary, 'Uses prop packs: Arcade Cabinets “Deluxe”. People need them installed to use it. 1 asset(s) come from other mods; HoloNet lists them, but can’t link to them.')
        self.assertEqual(self.sim.run(self.catalog, 'DescribeSources', Paths=['/Game/A/B.B'])['Summary'], 'Base game only · anyone with Den Designer can use it.')

    def test_pack_records_and_declarations(self):
        pack = self.sim.instance(RUNTIME + 'BP_DenPropPack', PackID='arcade-cabinets', Title='Arcade', Author='Rook', Version='1.2.0', NexusURL='https://www.nexusmods.com/games/starwarszerocompany/mods/42',
                                 Paths=['/ArcadePack/Meshes/SM_Cabinet.SM_Cabinet'], Labels=['Cab'], Details=['d'], Dimensions=[(1, 1, 1)], Solid=[True], SearchTexts=[''])
        self.catalog.vars.update(PendingPacks=[pack], CurrentPack=pack, PackCursor=0)
        self.assertTrue(self.sim.run(self.catalog, 'BeginPropPack')['Accepted'])
        self.assertEqual(self.catalog.vars['PackMounts'], ['ArcadePack'])
        declared = json.loads(self.sim.run(self.catalog, 'DeclarePacks', Paths=['/Game/A/B.B', '/arcadepack/x/Y.Y'])['JSON'])
        self.assertEqual(declared, [dict(id='arcade-cabinets', mount='ArcadePack', version='1.2.0', title='Arcade', url='https://www.nexusmods.com/games/starwarszerocompany/mods/42')])


class GeneratedSpecTests(unittest.TestCase):
    def test_generated_specs_are_current_and_lint_clean(self):
        script = ("import json,sys;sys.path.insert(0,sys.argv[1]);import runtime;"
                  "print(json.dumps({n+'.json':json.dumps(s,indent=2)+'\\n' for n,s in runtime.specs()}))")
        fresh = json.loads(subprocess.run([sys.executable, '-I', '-c', script, str(ROOT / 'unreal/specs')], check=True, capture_output=True, text=True).stdout)
        committed = {p.name: p.read_text() for p in lint_specs.GENERATED.glob('*.json')}
        self.assertEqual(sorted(fresh), sorted(committed), 'Run python3 -I unreal/specs/runtime.py')
        self.assertEqual([n for n in fresh if fresh[n] != committed[n]], [], 'Run python3 -I unreal/specs/runtime.py')
        pins = lint_specs.engine_pins(lint_specs.load(lint_specs.head_baseline()))
        known = set(lint_specs.lint(lint_specs.load(lint_specs.head_baseline()), pins)[0])
        problems, _ = lint_specs.lint(lint_specs.load(lint_specs.GENERATED), pins)
        self.assertEqual([p for p in problems if p not in known], [])


if __name__ == '__main__':
    unittest.main()
