"""Preset library regression, using real SaveGame IO in the kit only."""
import os
from pathlib import Path


def run(unreal,root,source,fixture,field,field_name,check):
    saved=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())).resolve()
    assert saved == Path(os.environ['DENDESIGNER_TEST_SAVED']).resolve()
    manager=unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenPresets'))
    library_type=root+'ST_DenPresetValue'

    def slot(i):
        return manager.call_method('BankSlot',('presets',i,False))

    paths=[saved/'SaveGames'/(slot(i)+'.sav') for i in range(6)]
    assert all(p.is_relative_to(saved/'SaveGames/ZComDen/Native/v1') and not p.is_dir() for p in paths)
    originals={p:p.read_bytes() for p in paths if p.exists()}

    def listing():
        names,status=manager.call_method('ListPresets')
        return list(names),status

    def save(name,doc=source):
        return manager.call_method('SavePreset',(name,doc,''))

    def load(name):
        return manager.call_method('LoadPreset',(name,))

    def prop(obj,name):
        return obj.get_editor_property(name)

    def disk():
        return {p.name:p.read_bytes() for p in paths if p.is_file()}

    def position(doc):
        value=field(prop(doc,'Entries')[0],'Position')
        return (value.x,value.y,value.z)

    try:
        for p in paths:
            p.unlink(missing_ok=True)
        check(listing() == ([],0), 'absent preset library lists empty without writing a file')
        check(not disk() and load('missing')[1] == 0, 'missing preset does not create storage')
        for name in ['', ' '*3, 'x'*41, 'two\nlines', 'tab\tname', 'bad\x7f']:
            check(save(name)[0] == 7, f'invalid preset name rejected: {name!r}')
        check(save('Nothing',None)[0] == 7 and not disk(), 'invalid preset document does not create library')
        check(save('  Zeta  ') == (1,'Zeta') and save('alpha')[0] == 1, 'preset names trim and save')
        names,status=listing()
        check(status == 1 and names == ['alpha','Zeta'], 'preset list sorts names')
        copy,status=load('zETA')
        check(status == 1 and prop(copy,'DisplayName') == 'Zeta' and prop(copy,'Scope') == 'preset', 'preset lookup is case-insensitive and restores display name')
        check(len(prop(copy,'Entries')) == len(prop(source,'Entries')) and position(copy) == position(source), 'preset restores all layout entries')
        check(list(field(prop(copy,'Entries')[0],'Materials')) == list(field(prop(source,'Entries')[0],'Materials')), 'nested material slots survive preset serialization')
        check(field(prop(copy,'Entries')[1],'Kind') == 1 and field(prop(copy,'Entries')[2],'Hidden'), 'preset retains Storeroom entries and native edits')
        first=prop(copy,'Entries')[0]
        first.set_editor_property(field_name('Position'),unreal.Vector(901,902,903))
        assert copy.call_method('WriteEntry',(first,True))
        fixture.call_method('SetGameVersion',(copy,'preset-fixture-v2'))
        check(position(load('Zeta')[0]) == position(source), 'editing a loaded preset does not change its saved snapshot')
        check(save('zEtA',copy) == (1,'zEtA') and len(listing()[0]) == 2, 'saving an existing name replaces it without duplicates')
        reloaded,status=load('ZETA')
        check(status == 1 and position(reloaded) == (901,902,903) and prop(reloaded,'GameVersion') == 'preset-fixture-v2', 'preset replacement persists edited payload and game version')
        # Unicode and path punctuation are display data; neither becomes a filename.
        check(save('../Médecine',copy)[0] == 1 and load('../Médecine')[1] == 1, 'Unicode and path-like preset names remain display data')
        check(all(p.name.startswith('presets-layout-') for p in paths if p.exists()), 'preset names never become filesystem paths')
        lib,status,bank=manager.call_method('LoadLibrary',('presets',False,0))
        assert status == 1
        previous,status,_=manager.call_method('LoadLibrary',('presets',False,prop(lib,'Revision')))
        check(status == 1 and len(prop(previous,'Entries')) == 2, 'previous preset library is available as a backup')
        # Fail the next write, then confirm it cannot alter the current library.
        before=disk()
        next_path=paths[(bank+1)%6]
        older=next_path.read_bytes() if next_path.is_file() else None
        next_path.unlink(missing_ok=True)
        next_path.mkdir()
        try:
            check(save('Should not appear')[0] == 6, 'preset save reports a write failure')
            check('Should not appear' not in listing()[0], 'failed preset creation leaves no library entry')
            check(manager.call_method('DeletePreset',('alpha',)) == 6 and load('alpha')[1] == 1, 'failed preset deletion preserves the preset')
        finally:
            next_path.rmdir()
            if older is not None:
                next_path.write_bytes(older)
        check(disk() == before, 'failed preset operations preserve all saved library bytes')
        check(manager.call_method('DeletePreset',('ALPHA',)) == 1 and load('alpha')[1] == 0, 'deleting a preset removes only its named entry')
        check(load('Zeta')[1] == 1 and load('../Médecine')[1] == 1, 'other presets survive deletion')
        before=disk()
        check(manager.call_method('DeletePreset',('already absent',)) == 1 and disk() == before, 'deleting an absent preset is a no-op')
        lib,status,bank=manager.call_method('LoadLibrary',('presets',False,0))
        assert status == 1
        previous,status,_=manager.call_method('LoadLibrary',('presets',False,prop(lib,'Revision')))
        names=[field(row,'Name',library_type) for row in prop(previous,'Entries')]
        check(status == 1 and 'alpha' in names, 'deleted preset remains in the previous library backup')
        # A torn current library recovers an older whole library, never half a row.
        complete=paths[bank].read_bytes()
        marker=complete.find(b'WriteCompleteID\0')
        assert marker > 4
        paths[bank].write_bytes(complete[:marker-4])
        check(listing()[1] == 2 and load('alpha')[1] == 2, 'incomplete library recovers previous complete presets')
        paths[bank].write_bytes(complete)
        fixture.call_method('SetLibrarySchemaVersion',(lib,2))
        assert unreal.GameplayStatics.save_game_to_slot(lib,slot(bank),0)
        future=disk()
        check(listing()[1] == 4 and save('Blocked')[0] == 4 and manager.call_method('DeletePreset',('Zeta',)) == 4 and disk() == future, 'newer preset library blocks modification')
    finally:
        for p in paths:
            if p in originals:
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(originals[p])
            else:
                p.unlink(missing_ok=True)
