"""Native startup/shortcut tests; only the kit's isolated Saved tree is writable."""
import os,uuid
from pathlib import Path


def run(unreal,check):
    from runtime_coordinator import COORDINATOR
    from runtime_shortcut import SHORTCUT
    from runtime_preferences import DOCUMENT
    from runtime_session import STORE
    from runtime import LAYOUT
    cls=lambda path:unreal.EditorAssetLibrary.load_blueprint_class(path)
    prop=lambda obj,key:obj.get_editor_property(key)
    doc=unreal.GameplayStatics.create_save_game_object(cls(DOCUMENT))
    shortcut=unreal.new_object(cls(SHORTCUT))
    shortcut.call_method('Configure',(None,))
    check(prop(shortcut,'KeyName')=='Home' and prop(shortcut,'Modifier')=='ctrl' and not shortcut.call_method('Pressed',(None,)),
          'standalone shortcut defaults safely without a preference document or player')
    assert doc.call_method('WritePreference',('toggle_key','F8'))[0]
    assert doc.call_method('WritePreference',('toggle_modifier','alt'))[0]
    shortcut.call_method('Configure',(doc,))
    check(prop(shortcut,'KeyName')=='F8' and prop(shortcut,'Modifier')=='alt','standalone shortcut reads the configured key and modifier')
    check(not doc.call_method('WritePreference',('toggle_key','F9'))[0], 'opening shortcut rejects the conflicting F9 key')
    shortcut.call_method('Configure',(None,))
    check(prop(shortcut,'KeyName')=='Home' and prop(shortcut,'Modifier')=='ctrl','refreshing missing preferences restores the default opening chord')
    samples=[False,True,True,True,False,False,True,False]
    check([shortcut.call_method('ObserveKey',(down,)) for down in samples]==
          [False,True,False,False,False,False,True,False],
          'opening shortcut emits one edge per press across held and idle frames')
    check(shortcut.call_method('ObserveKey',(True,)),
          'opening shortcut accepts the next press after release')
    shortcut.call_method('Configure',(None,))
    check(not shortcut.call_method('ObserveKey',(True,)),
          'preference refresh during opening cannot retrigger the held shortcut')

    saved=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())).resolve()
    assert saved==Path(os.environ['DENDESIGNER_TEST_SAVED']).resolve()
    storage=unreal.new_object(cls(STORE));campaign=uuid.uuid4().hex.upper();key='campaign-'+campaign
    paths=[saved/'SaveGames'/(storage.call_method('BankSlot',(k,i,d))+'.sav') for k in ['home',key,'preferences'] for d in [False,True] for i in range(2 if d else 6)]
    assert all(p.is_relative_to(saved/'SaveGames/ZComDen/Native/v1') and not p.is_dir() for p in paths)
    originals={p:p.read_bytes() for p in paths if p.exists()}
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);owner=actors.spawn_actor_from_class(unreal.Actor,unreal.Vector(),unreal.Rotator(),transient=True)
    coordinator=unreal.new_object(cls(COORDINATOR),outer=owner)
    host=None
    def drain():
        for _ in range(300):
            if not prop(host,'Busy'):return
            host.call_method('Pump')
        raise AssertionError('coordinator layout did not finish')
    try:
        for p in paths:p.unlink(missing_ok=True)
        guid=unreal.GuidLibrary.new_guid();text,known=coordinator.call_method('CampaignText',(guid,))
        check(known and len(text)==32 and text==text.upper() and '-' not in text,'current campaign GUID converts to the established layout key format')
        check(coordinator.call_method('CampaignText',(unreal.Guid(),))==('',False),'unset current campaign GUID cannot become a campaign layout key')
        check(coordinator.call_method('PrepareLayout',(campaign,)),'coordinator opens an absent layout without writing a replacement')
        host=prop(coordinator,'Host');drain()
        check(prop(coordinator,'Initialized') and prop(coordinator,'ResolvedKey')=='home' and prop(host,'ActiveCampaignID')==campaign,
              'Den startup resolves Home using the actual supplied current campaign identity')
        check(not prop(host,'Editing') and not prop(host,'UIOpen') and not any(p.exists() for p in paths),
              'background layout application opens no UI and writes no layout, preferences or draft')
        coordinator.call_method('UpdateShortcut')
        check(prop(coordinator,'Shortcut') is not None,'world coordinator owns an opening shortcut independent of the editor UI')
        check(coordinator.call_method('EnsureHost') and prop(coordinator,'Host')==host,'repeated initialization reuses the world host')
        own,status=storage.call_method('MakeCampaign',(campaign,prop(host,'WorkingDocument')))
        assert status==1
        check(coordinator.call_method('PrepareLayout',(campaign,)),'coordinator can re-resolve a campaign override')
        drain()
        check(prop(coordinator,'ResolvedKey')==key and prop(host,'SessionKey')==key and prop(coordinator,'Host')==host,
              'campaign layout selection reuses the same host and world snapshots')
        for p in paths:
            if p.name.startswith(key+'-layout-'):p.unlink(missing_ok=True)
        bad=saved/'SaveGames'/(storage.call_method('BankSlot',(key,0,False))+'.sav');bad.parent.mkdir(parents=True,exist_ok=True);bad.write_bytes(b'damaged coordinator fixture')
        check(not coordinator.call_method('PrepareLayout',(campaign,)) and prop(coordinator,'LayoutStatus')==3,
              'unreadable campaign layout refuses an editing session rather than silently editing Home')
        drain()
        check(not prop(host,'Editing') and bad.read_bytes()==b'damaged coordinator fixture',
              'failed startup leaves corrupt layout bytes unchanged and no editing session active')
        coordinator.call_method('Shutdown')
        check(prop(coordinator,'Host') is None and prop(coordinator,'Shortcut') is None and not prop(coordinator,'Initialized'),
              'world shutdown releases its host, shortcut and initialization state')
        coordinator.call_method('Shutdown')
        check(prop(coordinator,'Host') is None,'world shutdown is idempotent')
    finally:
        coordinator.call_method('Shutdown');actors.destroy_actor(owner)
        for p in paths:p.unlink(missing_ok=True)
        for p,data in originals.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
