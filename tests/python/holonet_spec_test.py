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
LAYOUT_SAVE = RUNTIME + 'BP_DenLayoutSave'
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
            'EnsureCompositionService': lambda obj: None,
            'ListPresets': lambda obj: {'Names': list(self.library), 'Status': 1},
            'FindShareCode': lambda obj, Code='': {'Index': 0 if Code in self.codes or any(n.lower().endswith(' ' + Code.lower()) for n in self.library) else -1, 'Name': self.codes.get(Code, '')},
        })
        self.library = []
        self.codes = {}  # ShareCode -> composition name
        self.catalog = self.sim.instance(RUNTIME + 'BP_DenCatalog')
        self.panel = self.sim.widgets(EDITOR + 'WBP_DenHolonet')
        self.toolbar = self.sim.widgets(EDITOR + 'WBP_DenToolbar')
        self.host = self.sim.instance(HOST, CatalogProvider=self.catalog, CommunityPanel=self.panel, Toolbar=self.toolbar, CommunityToken='tok', UIOpen=True)

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
        self.library = ['HoloNet base-game fix H7854VMD']
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

    def test_library_badge_from_share_code(self):
        self.library, self.codes = ['HoloNet base-game fix'], {'H7854VMD': 'HoloNet base-game fix'}
        self.load_gallery(self.listings)
        rows = self.host.vars['CommunityBrowseRows']
        self.assertEqual([r.vars['Detail'] for r in rows], ['by Rook · 3 parts', 'by Rook · 1 parts · IN LIBRARY'])

    def test_library_badge_survives_previews_and_appears_after_an_import(self):
        self.load_gallery(self.listings)
        rows = self.host.vars['CommunityBrowseRows']
        self.assertEqual(rows[1].vars['Detail'], 'by Rook · 1 parts')
        self.library = ['HoloNet base-game fix H7854VMD']
        self.sim.run(self.host, 'RefreshCommunityCardDetails')  # what an import does
        self.assertEqual(rows[1].vars['Detail'], 'by Rook · 1 parts · IN LIBRARY')
        self.sim.run(self.host, 'RefreshCommunityCardDetail', Index=1)  # what a finished preview does
        self.assertEqual(rows[1].vars['Detail'], 'by Rook · 1 parts · IN LIBRARY')

    def test_add_and_place_now_starts_placing_the_saved_build(self):
        placed = []
        document = self.sim.instance(LAYOUT_SAVE)
        document.vars['Entries'] = [object()]
        self.sim.overrides.update(CanEdit=lambda obj: {'Ready': True}, ValidateComposition=lambda obj, Document=None: {'Accepted': True},
                                  RefreshCompositionLibrary=lambda obj: None, CompositionLibraryCurrent=lambda obj: {'Accepted': True},
                                  SavePreset=lambda obj, Name='', Document=None, ShareCode='': {'Status': 1, 'CleanName': Name},
                                  SetEditorPanel=lambda obj, Name='': obj.vars.update(ActivePanel=Name),
                                  LoadEditorComposition=lambda obj, Name='': placed.append(Name))
        self.host.vars.update(CommunityDocument=document, CommunityExpected=1, CommunityName='Lamp corner', CommunityFullName='Lamp corner H7854VMD',
                              CommunityShareCode='H7854VMD', CommunityPending=True, CommunityRequest='DOWNLOAD/H7854VMD', CommunityPlaceAfterImport=True)
        result = self.sim.run(self.host, 'CommitCommunityImport', Token='tok')
        self.assertTrue(result['Accepted'])
        self.assertEqual(placed, ['Lamp corner'])
        self.assertEqual(self.host.vars['ActivePanel'], 'compositions')
        self.assertFalse(self.host.vars['CommunityPlaceAfterImport'])

    def import_as(self, names=(), codes=None):
        """Commits an import of "Lamp corner" (H7854VMD) into a library with these names: (saved name, ShareCode) or None."""
        saved = []
        document = self.sim.instance(LAYOUT_SAVE)
        document.vars['Entries'] = [object()]
        self.codes = codes or {}
        self.sim.overrides.update(CanEdit=lambda obj: {'Ready': True}, ValidateComposition=lambda obj, Document=None: {'Accepted': True},
                                  RefreshCompositionLibrary=lambda obj: None, CompositionLibraryCurrent=lambda obj: {'Accepted': True},
                                  SavePreset=lambda obj, Name='', Document=None, ShareCode='': saved.append((Name, ShareCode)) or {'Status': 1, 'CleanName': Name})
        self.sim.engine['/Script/Engine.GameplayStatics:CreateSaveGameObject'] = lambda **kw: {'ReturnValue': document}
        self.host.vars.update(CommunityDocument=document, CommunityExpected=1, CommunityPending=True, CommunityRequest='DOWNLOAD/H7854VMD', CommunityToken='tok',
                              CompositionNames=list(names), CommunityPlaceAfterImport=False)
        self.sim.run(self.host, 'BeginCommunityImport', Token='tok', Name='Lamp corner H7854VMD', Report='Base game only.', Count=1, Anchor=(0, 0, 0))
        accepted = self.sim.run(self.host, 'CommitCommunityImport', Token='tok')['Accepted']
        return saved[0] if accepted else None

    def test_imports_get_clean_names_and_keep_their_code(self):
        self.sim.overrides.update(NormalizeName=lambda obj, Name='': {'CleanName': Name.strip(), 'Valid': True}, EnsureCompositionService=lambda obj: None)
        self.assertEqual(self.import_as(), ('Lamp corner', 'H7854VMD'))
        # A taken title (names match case-insensitively) falls back to the old "<title> <code>" name.
        self.assertEqual(self.import_as(['lamp CORNER']), ('Lamp corner H7854VMD', 'H7854VMD'))
        # Already imported, by code or under its old name: stopped, as before.
        self.assertIsNone(self.import_as(['Lamp corner'], {'H7854VMD': 'Lamp corner'}))
        self.assertIsNone(self.import_as(['Lamp corner H7854VMD']))

    def test_old_imports_adopt_their_code_once(self):
        presets = EDITOR.replace('Editor', 'Runtime') + 'BP_DenPresets'
        library = self.sim.instance(RUNTIME + 'BP_DenPresetLibrary')
        row = lambda name, code='': {'Name': name, 'ShareCode': code, 'Entries': [], 'GameVersion': '', 'HasCompositionAnchor': True, 'CompositionAnchor': (0, 0, 0)}
        library.vars['Entries'] = [row('Stack O\' Boxes 7FCX178E'), row('Lamp corner H7854VMD'), row('Lamp corner'),
                                   row('Shelf STACKERS'), row('Bar K7MP2XQ9', 'K7MP2XQ9'), row('Mine')]
        saves = []
        self.sim.overrides.update(OpenLibrary=lambda obj: {'Library': library, 'Status': 1},
                                  SaveLibrary=lambda obj, **kw: saves.append(kw) or {'Status': 1})
        service = self.sim.instance(presets)
        del self.sim.overrides['FindShareCode']  # the real lookup, not the host-side stub
        find = lambda code: self.sim.run(service, 'FindShareCode', Code=code)['Index']
        self.assertEqual([find(c) for c in ['k7mp2xq9', '7FCX178E', 'ZZZZ1111', '']], [4, 0, -1, -1])  # by code, by old name
        result = self.sim.run(service, 'AdoptShareCodes')
        self.assertEqual([(r['Name'], r['ShareCode']) for r in library.vars['Entries']],
                         [('Stack O\' Boxes', '7FCX178E'), ('Lamp corner H7854VMD', 'H7854VMD'), ('Lamp corner', ''),
                          ('Shelf STACKERS', ''), ('Bar K7MP2XQ9', 'K7MP2XQ9'), ('Mine', '')])
        self.assertTrue(result['Changed'])
        self.assertEqual(len(saves), 1)
        self.assertEqual([find(c) for c in ['7fcx178e', 'H7854VMD']], [0, 1])
        saves.clear()
        self.assertFalse(self.sim.run(service, 'AdoptShareCodes')['Changed'])
        self.assertEqual(saves, [])

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
        self.assertEqual(self.toolbar.vars['RailSharesCount'].text, '2')
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

    def test_update_target_found_when_my_shares_arrives_after_the_pick(self):
        self.host.vars['CommunityProfile'] = 'Connected as Rook'
        def review(obj):
            obj.vars['CommunityUploadName'] = obj.vars['CommunitySourceName']
        self.sim.overrides.update(SelectCommunitySourceCard=lambda obj, Key='': obj.vars.update(CommunitySourceName='old shelf'),
                                  ReviewCommunityComposition=review, EnsureHolonetShares=lambda obj: None)
        self.sim.run(self.host, 'PickHolonetSource', Key='x')  # My Shares not loaded yet
        self.assertEqual((self.host.vars['HolonetShareTarget'], self.host.vars['HolonetShareUpdate']), (-1, False))
        self.my_shares()  # the page lands
        self.assertEqual((self.host.vars['HolonetShareTarget'], self.host.vars['HolonetShareUpdate']), (1, True))
        self.host.vars['CommunityArea'] = 'upload'
        self.sim.run(self.host, 'ShareHolonetUpdate')
        self.assertEqual(self.host.vars['CommunityArea'], 'upload')  # no detour through My Shares
        self.sim.run(self.host, 'ShareHolonetNew')
        self.my_shares()  # a later reload does not undo "Share as a new build"
        self.assertFalse(self.host.vars['HolonetShareUpdate'])

    def test_areas_rail_and_subtitle(self):
        self.sim.overrides.update(EnsureHolonetShares=lambda obj: None, StyleEditorToggle=lambda obj, **kw: obj.vars.setdefault('toggled', []).append((kw['Back'].name, kw['On'])))
        self.host.vars['ActivePanel'] = 'community'
        self.sim.run(self.host, 'SetCommunityArea', Area='shares')
        visible = {name for name in ['BrowseArea', 'BrowseDenArea', 'UploadArea', 'SharesArea', 'AccountArea'] if self.panel.vars[name].visibility == 'Visible'}
        self.assertEqual(visible, {'SharesArea'})
        self.assertEqual(self.panel.vars['HolonetSubtitle'].text, 'My Shares')
        rail = dict(t for t in self.host.vars['toggled'] if t[0].startswith('Rail'))
        self.assertEqual({k for k, on in rail.items() if on}, {'RailSharesBack'})
        self.sim.run(self.host, 'SetCommunityArea', Area='browse')
        self.assertEqual(self.panel.vars['HolonetSubtitle'].text, 'Builds shared by other captains')

    def test_rail_entries_open_holonet_on_their_area(self):
        areas = []
        self.sim.overrides.update(SetEditorPanel=lambda obj, Name='': obj.vars.update(ActivePanel=Name),
                                  SetCommunityArea=lambda obj, Area='': areas.append(Area))
        self.host.vars['ActivePanel'] = 'catalog'
        self.sim.run(self.host, 'OpenHolonetArea', Area='shares')
        # Opening the window shows the remembered area (CommunityPanelChanged), so no second switch.
        self.assertEqual((self.host.vars['ActivePanel'], self.host.vars['CommunityArea'], areas), ('community', 'shares', []))
        self.sim.run(self.host, 'OpenHolonetArea', Area='account')
        self.assertEqual((self.host.vars['ActivePanel'], areas), ('community', ['account']))

    def test_import_from_your_den_opens_browse_first(self):
        fetched = []
        self.sim.overrides.update(SetEditorPanel=lambda obj, Name='': obj.vars.update(ActivePanel=Name),
                                  SetCommunityArea=lambda obj, Area='': obj.vars.update(CommunityArea=Area),
                                  StartCommunityFetch=lambda obj, Input='': fetched.append((obj.vars['ActivePanel'], Input)))
        self.host.vars.update(ActivePanel='layouts', CommunityArea='account')
        self.sim.run(self.host, 'ImportCommunityCode', Input='K7MP2XQ9')
        self.assertEqual((fetched, self.host.vars['CommunityArea']), ([('community', 'K7MP2XQ9')], 'browse'))
        self.host.vars['CommunityArea'] = 'account'
        self.sim.run(self.host, 'ImportCommunityCode', Input='H7854VMD')
        self.assertEqual((fetched[-1], self.host.vars['CommunityArea']), (('community', 'H7854VMD'), 'account'))

    def test_preload_connects_then_loads_my_shares_once(self):
        steps = []
        self.sim.overrides.update(CanEdit=lambda obj: {'Ready': True}, EnsureHolonetShares=lambda obj: steps.append('shares'),
                                  StartCommunityFetch=lambda obj, Input='': steps.append(Input) or obj.vars.update(CommunityPending=True))
        self.host.vars.update(CommunityProfile='', CommunityPending=False, HolonetPreload=0)
        for _ in range(2):
            self.sim.run(self.host, 'PollHolonetPreload')
        self.assertEqual(steps, ['CONNECT'])  # waits while the connection request runs
        self.host.vars.update(CommunityPending=False, CommunityProfile='Connected as Rook')
        for _ in range(3):
            self.sim.run(self.host, 'PollHolonetPreload')
        self.assertEqual(steps, ['CONNECT', 'shares'])

    def test_import_waits_for_a_running_request(self):
        fetched = []
        self.sim.overrides.update(CanEdit=lambda obj: {'Ready': True}, EnsureHolonetShares=lambda obj: None,
                                  StartCommunityFetch=lambda obj, Input='': fetched.append(Input) or obj.vars.update(CommunityPending=True))
        self.host.vars.update(ActivePanel='community', CommunityPending=True, HolonetPreload=2)
        self.sim.run(self.host, 'ImportCommunityCode', Input='1CZZ6YPV')
        self.assertEqual((fetched, self.host.vars['CommunityQueuedCode']), ([], '1CZZ6YPV'))
        self.assertEqual(self.panel.vars['Footer'].text, 'Importing as soon as HoloNet finishes its current request…')
        self.sim.run(self.host, 'PollHolonetPreload')
        self.assertEqual(fetched, [])  # still busy
        self.host.vars['CommunityPending'] = False
        self.sim.run(self.host, 'PollHolonetPreload')
        self.assertEqual((fetched, self.host.vars['CommunityQueuedCode']), (['1CZZ6YPV'], ''))
        # Cancel drops a waiting import.
        self.host.vars.update(CommunityPending=True, CommunityQueuedCode='H7854VMD')
        self.sim.run(self.host, 'CancelHolonetRequest')
        self.assertEqual(self.host.vars['CommunityQueuedCode'], '')

    def test_rail_lights_the_open_entry_and_joins_its_content(self):
        toggled = {}
        self.sim.overrides.update(StyleEditorToggle=lambda obj, **kw: toggled.__setitem__(kw['Back'].name, kw['On']))
        history = self.sim.instance(RUNTIME + 'BP_DenHistory')
        history.vars['Version'] = 5
        self.host.vars['History'] = history
        t = self.toolbar.vars
        # The folded rail's icon lights with its labelled entry.
        for panel, area, lit, joined in [('', 'browse', set(), False), ('catalog', 'upload', {'CatalogBack', 'IconCatalogBack'}, True),
                                         ('community', 'upload', {'RailShareBack', 'IconShareBack'}, True), ('settings', 'upload', set(), False)]:
            self.host.vars.update(ActivePanel=panel, CommunityArea=area)
            self.sim.run(self.host, 'RefreshEditorRail')
            self.assertEqual({name for name, on in toggled.items() if on}, lit, panel)
            self.assertFalse({'RailDensBack', 'IconDensBack'} & set(toggled))
            self.assertEqual((t['RailJoined'].visibility, t['RailAlone'].visibility),
                             ('HitTestInvisible', 'Collapsed') if joined else ('Collapsed', 'HitTestInvisible'), panel)
        for profile, dot in [('Connected as Rook', 'HitTestInvisible'), ('Not connected.', 'Collapsed')]:
            self.host.vars['CommunityProfile'] = profile
            self.sim.run(self.host, 'RefreshEditorRail')
            self.assertEqual((t['HolonetDot'].visibility, t['HolonetIconDot'].visibility), (dot, dot))
        # The stored count holds while the layout is at the version the Storeroom last listed; folded, it's a badge.
        self.host.vars.update(StoreCountVersion=5, StoreBuilding=False, StoreTotal=12)
        self.sim.run(self.host, 'RefreshEditorRail')
        self.assertEqual((t['StoreroomCount'].text, t['IconStoreroomBadgeText'].text, t['IconStoreroomBadge'].visibility), ('12', '12', 'HitTestInvisible'))
        for change in [dict(StoreBuilding=True), dict(StoreCountVersion=4), dict(StoreTotal=0)]:
            self.host.vars.update({'StoreCountVersion': 5, 'StoreBuilding': False, 'StoreTotal': 12, **change})
            self.sim.run(self.host, 'RefreshEditorRail')
            self.assertEqual((t['StoreroomCount'].text, t['IconStoreroomBadge'].visibility), ('', 'Collapsed'), change)
        # My Shares' badge copies the count ReadHolonetShares wrote.
        for count, shown in [('3', 'HitTestInvisible'), ('', 'Collapsed')]:
            t['RailSharesCount'].text = count
            self.sim.run(self.host, 'RefreshEditorRail')
            self.assertEqual((t['IconSharesBadgeText'].text, t['IconSharesBadge'].visibility), (count, shown))

    def test_rail_folds_to_icons_and_the_content_follows(self):
        t = self.toolbar.vars
        for labels, frame, icons, width, left in [(True, 'Visible', 'Collapsed', 232, 243), (False, 'Collapsed', 'Visible', 64, 75)]:
            self.host.vars['RailLabels'] = labels
            self.sim.run(self.host, 'RefreshEditorRail')
            self.assertEqual((t['RailFrame'].visibility, t['RailIcons'].visibility), (frame, icons), labels)
            self.assertEqual(t['LibraryTabs'].offsets, f'(Left=12,Top=80,Right={width},Bottom=58)')
            # The content starts on the rail's last pixel, whichever entry is open.
            self.assertEqual(self.panel.vars['Panel'].position, (left, 80))

    def test_placing_folds_the_rail_until_the_drop(self):
        t = self.toolbar.vars
        self.host.vars.update(RailLabels=True, RailAutoFold=True)
        self.sim.run(self.host, 'RefreshEditorRail')
        self.assertEqual((t['RailIcons'].visibility, self.panel.vars['Panel'].position), ('Visible', (75, 80)))
        self.sim.run(self.host, 'CancelPlacement')
        self.assertEqual((self.host.vars['RailAutoFold'], t['RailFrame'].visibility, self.host.vars['RailLabels']), (False, 'Visible', True))
        # Folded by hand, a drop leaves it folded.
        self.host.vars.update(RailLabels=False, RailAutoFold=True)
        self.sim.run(self.host, 'CancelPlacement')
        self.assertEqual(t['RailIcons'].visibility, 'Visible')

    def test_fold_pin_is_saved_and_the_code_icon_unfolds_and_focuses(self):
        saved = []
        document = self.sim.instance(RUNTIME + 'BP_DenPreferencesSave')
        self.sim.overrides.update(EnsurePreferenceService=lambda obj: None,
                                  ChangePreference=lambda obj, Key='', Value='': saved.append((Key, Value)) or {'Status': 1, 'Document': document, 'Changed': True})
        self.host.vars['PreferenceService'] = self.sim.instance(RUNTIME + 'BP_DenPreferences')
        self.sim.run(self.host, 'SetRailLabels', Labels=False)
        self.assertEqual((self.host.vars['RailLabels'], saved, self.toolbar.vars['RailIcons'].visibility), (False, [('rail_labels', 'false')], 'Visible'))
        self.assertIs(self.host.vars['PreferencesDocument'], document)
        self.sim.run(self.host, 'OpenRailCode')
        self.assertEqual((self.host.vars['RailLabels'], saved[-1], self.toolbar.vars['RailFrame'].visibility), (True, ('rail_labels', 'true'), 'Visible'))
        # The field takes focus on the next tick, once the unfolded rail has laid out.
        code = self.toolbar.vars['CommunityCode']
        self.assertFalse(code.focused)
        self.sim.run(self.host, 'PollRailCodeFocus')
        self.assertEqual((code.focused, self.host.vars['RailCodeFocus']), (True, False))

    def test_a_finished_request_clears_contacting(self):
        del self.sim.overrides['ReleaseCommunityMailbox']
        self.sim.engine['/Script/Engine.GameplayStatics:DeleteGameInSlot'] = lambda **kw: dict(ReturnValue=True)
        for message, shown in [('Contacting HoloNet… (needs the Den Designer HoloNet bridge installed)', ''),
                               ('Added to your Compositions. 14 parts.', 'Added to your Compositions. 14 parts.')]:
            self.host.vars['CommunityMessage'] = message
            self.sim.run(self.host, 'ReleaseCommunityMailbox')
            self.assertEqual((self.host.vars['CommunityMessage'], self.panel.vars['Footer'].text), (shown, shown))

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
        baseline = lint_specs.load(lint_specs.head_baseline())
        pins, pairs = lint_specs.engine_pins(baseline), lint_specs.tree_pairs(baseline)
        known = set(lint_specs.lint(baseline, pins, pairs)[0])
        problems, _ = lint_specs.lint(lint_specs.load(lint_specs.GENERATED), pins, pairs)
        self.assertEqual([p for p in problems if p not in known], [])


if __name__ == '__main__':
    unittest.main()
