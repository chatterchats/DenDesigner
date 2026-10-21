"""Real Blueprint preferences + SaveGame tests, confined to the kit Saved tree."""
import os
from pathlib import Path


def run(unreal, root, fixture, field, field_name, check):
    from runtime_preferences import DEFAULTS, BINDINGS, ROW, KEY_NAMES
    saved=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())).resolve()
    assert saved == Path(os.environ['DENDESIGNER_TEST_SAVED']).resolve()
    codec=unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenKeyNames'))
    check(all(fixture.call_method('RoundTripKey',(codec,name))==(True,name,True) for name in KEY_NAMES),
          'every supported persisted key resolves to a valid native FKey and back')
    check(fixture.call_method('RoundTripKey',(codec,'NotARealKey'))==(False,'',False),
          'unknown key names never construct a usable input key')
    cls=unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenPreferencesSave')
    doc=unreal.GameplayStatics.create_save_game_object(cls)
    store=unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenPreferencesStore'))
    key='test_preferences_native'
    paths=[saved/'SaveGames'/(store.call_method('BankSlot',(key,i,False))+'.sav') for i in range(6)]
    originals={p:p.read_bytes() for p in paths if p.is_file()}

    def read(key, target=doc):return target.call_method('ReadPreference',(key,))
    def write(key,value,target=doc):return target.call_method('WritePreference',(key,value))
    def load():return store.call_method('LoadPreferences',(key,False,0))
    def save(target=doc):return store.call_method('SavePreferences',(key,target,False,0,''))
    def disk():return {p:p.read_bytes() for p in paths if p.is_file()}
    def row_pairs(target):return [(field(r,'Key',ROW),field(r,'Value',ROW)) for r in target.get_editor_property('Entries')]

    try:
        for p in paths:p.unlink(missing_ok=True)
        check(load()[1] == 0 and not disk(),'missing preferences do not write defaults')
        check(all(read(k)==(value,True,False) for k,value in DEFAULTS.items()),'native preferences preserve all shipped control and editing defaults')
        check(write('fly_speed','900')==(True,False) and row_pairs(doc)==[], 'writing an untouched default does not create an override')
        check(read('unknown')==('',False,False),'unknown setting has no effective value')
        check(write('unknown','true')==(False,False),'unknown preference writes are rejected')
        before=row_pairs(doc)
        invalid=[('fly_speed','199'),('fly_speed','3001'),('fly_speed','900oops'),('fly_speed','nan'),
                 ('fly_speed','inf'),('fly_speed','.'),('fly_speed','1e999'),('look_speed','0'),
                 ('fast_multiplier','8.1'),('snap','7'),('reach','0'),('gimbal','spin'),
                 ('autosave','yes'),('toggle_modifier','meta'),('toggle_key','LeftControl'),
                 ('key_store','Escape'),('key_store','LeftAlt'),('key_store','RightAlt'),
                 ('key_store','Home'),('toggle_key','W'),('key_store','LeftMouseButton'),('key_store','Unknown'),('key_store','C')]
        check(all(write(k,value)==(False,False) for k,value in invalid) and row_pairs(doc)==before,
              'invalid numbers, choices, fixed keys and occupied bindings leave preferences unchanged')
        check(write('fly_speed','1.2e3')==(True,True) and write('look_speed','3,5')==(True,True),
              'camera preferences accept validated numeric text')
        check(write('fly_speed','1.2e3')==(True,False),'unchanged preference reports no mutation')
        check(write('key_store','V')==(True,True) and write('key_copy','X')==(True,True),
              'rebinding frees the former key for another command')
        check(write('key_store','X')==(False,False) and read('key_store')[0]=='V',
              'conflicting rebind cannot strand either command')
        check(write('select_floors','false')==(True,True) and write('autosave','false')==(True,True),
              'native floor and draft preferences are writable')
        check(list(doc.call_method('RecentMeshes'))==[],'new preferences have no recent meshes')
        for path in ['', '/Game/Bad', 'SM_Test', '/Game/Bad.SM:Subobject', '/Game/../Bad.Bad', '/Game/Bad Name.Bad']:
            check(not doc.call_method('RememberMesh',(path,)), 'invalid recent path is ignored: '+repr(path))
        mesh=lambda i:f'/Game/Test/SM_{i}.SM_{i}'
        check(all(doc.call_method('RememberMesh',(mesh(i),)) for i in range(45)), 'native recent history accepts asset paths')
        expected=[mesh(i) for i in range(44,4,-1)]
        check(list(doc.call_method('RecentMeshes'))==expected,'recent history keeps the newest forty in order')
        check(doc.call_method('RememberMesh',(mesh(20),)) and list(doc.call_method('RecentMeshes'))==[mesh(20),*[p for p in expected if p!=mesh(20)]],
              'reusing a mesh promotes it without duplicates')
        saved_doc,status=save()
        check(status==1 and saved_doc is not None,'preferences save through isolated verified rotating banks')
        loaded,status,bank=load()
        check(status==1 and row_pairs(loaded)==row_pairs(doc),'settings, key names and recents survive SaveGame roundtrip')
        check(read('key_store',loaded)==('V',True,True) and len(loaded.call_method('RecentMeshes'))==40,
              'loaded preference document retains its native accessors')
        check(write('fly_speed','1500',loaded)==(True,True) and save(loaded)[1]==1,'preferences write a second revision')
        latest,status,bank=load();before=disk()
        next_path=paths[(bank+1)%6];prior=next_path.read_bytes() if next_path.is_file() else None
        next_path.unlink(missing_ok=True);next_path.mkdir()
        try:check(save()[1]==6,'preference IO failure is reported')
        finally:
            next_path.rmdir()
            if prior is not None:next_path.write_bytes(prior)
        check(disk()==before and read('fly_speed',load()[0])[0]=='1500','failed write preserves persisted preferences')
        # Services must reopen current disk data, not overwrite it from stale
        # settings or catalog snapshots. Both instances use an isolated key.
        service_cls=unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenPreferences')
        service=unreal.new_object(service_cls);other=unreal.new_object(service_cls)
        for obj in [service,other]:fixture.call_method('SetPreferencesKey',(obj,key))
        check(service.call_method('OpenPreferences')[1]==1,'preferences service opens the existing document')
        current,status,changed=service.call_method('ChangePreference',('look_speed','4'))
        check(status==1 and changed and read('look_speed',current)[0]=='4','preferences service persists and returns the verified snapshot')
        before_noop=disk()
        check(service.call_method('ChangePreference',('look_speed','4'))[1:]==(1,False) and disk()==before_noop,
              'unchanged settings do not consume a backup bank')
        check(service.call_method('ChangePreference',('key_store','Home'))[1:]==(7,False) and disk()==before_noop,
              'service rejects a toggle-key conflict without writing')
        current,status,changed=other.call_method('RememberRecent',(mesh(100),))
        check(status==1 and changed and read('look_speed',current)[0]=='4' and list(current.call_method('RecentMeshes'))[0]==mesh(100),
              'recent update from a second service preserves the latest setting')
        before_noop=disk()
        check(other.call_method('RememberRecent',(mesh(100),))[1:]==(1,False) and disk()==before_noop,
              'already-most-recent mesh does not write another backup')
        recents_before=list(current.call_method('RecentMeshes'))
        reset,status,changed=service.call_method('ResetSettings')
        check(status==1 and changed and all(read(k,reset)[0]==value for k,value in DEFAULTS.items()),
              'reset restores all controls together without intermediate binding conflicts')
        check(list(reset.call_method('RecentMeshes'))==recents_before,'reset settings preserves recent mesh history')
        before_noop=disk()
        check(service.call_method('ResetSettings')[1:]==(1,False) and disk()==before_noop,'repeated reset does not write defaults')
        # Restore the original two-revision fixture before corruption checks.
        for p in paths:p.unlink(missing_ok=True)
        for p,data in before.items():p.write_bytes(data)
        # Corrupt values are contained at the accessor, even in a structurally
        # valid SaveGame. They cannot drive camera speed or runtime input.
        rows=list(latest.get_editor_property('Entries'))
        damaged=next(r for r in rows if field(r,'Key',ROW)=='fly_speed')
        damaged.set_editor_property(field_name('Value',ROW),'not a number')
        fixture.call_method('SetPreferencesEntries',(latest,rows))
        check(read('fly_speed',latest)==('900',True,False),'malformed persisted preference falls back to its safe default')
        future=unreal.GameplayStatics.create_save_game_object(cls)
        fixture.call_method('SetPreferencesSchemaVersion',(future,2))
        check(save(future)[1]==7 and disk()==before,'newer in-memory preferences cannot overwrite known data')
        future_loaded=load()[0];fixture.call_method('SetPreferencesSchemaVersion',(future_loaded,2))
        check(unreal.GameplayStatics.save_game_to_slot(future_loaded,store.call_method('BankSlot',(key,bank,False)),0),
              'future-schema test fixture saved only in kit namespace')
        future_bytes=disk()
        fallback,fallback_status=service.call_method('OpenPreferences')
        check(fallback_status==4 and fallback is not None and read('fly_speed',fallback)[0]=='900', 'newer preference file exposes defaults with explicit read-only status')
        check(service.call_method('ChangePreference',('look_speed','5'))[1]==4 and service.call_method('ResetSettings')[1]==4 and other.call_method('RememberRecent',(mesh(101),))[1]==4, 'all service mutations respect newer-schema protection')
        check(load()[1]==4 and save()[1]==4 and disk()==future_bytes,'newer persisted preferences block writes without damaging any bank')
        # Restore current header, then tear the newest bank; recover prior settings.
        for p,data in before.items():p.write_bytes(data)
        paths[bank].write_bytes(b'torn preferences')
        recovered,status,_=load()
        check(status==2 and recovered is not None and read('fly_speed',recovered)[0]=='1.2e3',
              'torn preferences recover the prior complete bank')
        for p in paths:
            if p.is_file():p.write_bytes(b'torn preferences')
        corrupt=disk()
        check(load()[1]==3 and save()[1]==3 and disk()==corrupt,'unrecoverable preferences remain intact for explicit recovery')
        fallback,status=service.call_method('OpenPreferences')
        check(status==3 and read('fly_speed',fallback)[0]=='900' and service.call_method('ChangePreference',('fly_speed','1000'))[1]==3 and disk()==corrupt,
              'damaged preferences offer safe read-only defaults and retain evidence')
        for p in paths:p.unlink(missing_ok=True)
        fallback,status=service.call_method('OpenPreferences')
        check(status==0 and fallback is not None and not disk(),'opening absent preferences returns defaults without a write')
        check(service.call_method('ChangePreference',('fly_speed','900'))[1:]==(1,False) and not disk(),'accepting default settings does not create a file')
        check(service.call_method('ChangePreference',('fly_speed','1100'))[1:]==(1,True) and load()[1]==1,'first real preference change creates an isolated store')
    finally:
        for p in paths:p.unlink(missing_ok=True)
        for p,data in originals.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
