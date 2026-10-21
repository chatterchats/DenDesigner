"""Headless Blueprint execution tests for the pak runtime, in the KIT's Saved only."""
import json
import os
import sys
import traceback
from pathlib import Path

import unreal
import zcom_authoring

REPO = Path(os.environ['DENDESIGNER_REPO'])
sys.path.insert(0, str(REPO / 'unreal/specs'))
from runtime import ROOT, ENTRY, LAYOUT, MUTATION, CHANGE, Graph, v, specs

failures = []
checks = 0


def check(ok, label):
    global checks
    checks += 1
    unreal.log(f'DENNATIVE_CHECK {"ok" if ok else "FAIL"}: {label}')
    if not ok:
        failures.append(label)


def field_name(name, path=ENTRY):
    spec = next(s for _, s in specs() if s['path'] == path)
    f = next(f for f in spec['fields'] if f['name'] == name)
    return name + '_0_' + f['guid'].replace('-', '').upper()


def field(row, name, path=ENTRY):
    return row.get_editor_property(field_name(name, path))


def fixture_spec():
    g = Graph()
    g.node('row', 'make_struct', struct=ENTRY, defaults={
        'Mesh': '/Game/Test/SM_Test.SM_Test', 'Scale': '1,2,3',
        'Rotation': '10,20,30', 'HasPosition': 'true', 'HasRotation': 'true',
        'HasScale': 'true', 'CollisionMode': '2', 'Source': '/Game/Test.Map:PersistentLevel.Source',
        'HasFingerprint': 'true', 'FingerprintMesh': '/Game/Test/SM_Test.SM_Test',
        'FingerprintPosition': '7,8,9'})
    g.wire(('entry.Kind', 'row.Kind'), ('entry.Key', 'row.Key'),
           ('entry.Position', 'row.Position'), ('row.ST_DenEntry', 'result.Value'))
    g.chain('entry', 'result')
    mutation = Graph()
    mutation.node('row', 'make_struct', struct=MUTATION)
    mutation.wire(('entry.Value', 'row.Value'), ('entry.Present', 'row.Present'), ('row.ST_DenMutation', 'result.Mutation'))
    mutation.chain('entry', 'result')
    setters = []
    for name, kind in [('DisplayName','string'), ('Enabled','bool'), ('SchemaVersion','int'), ('EntryCount','int'), ('GameVersion','string')]:
        setter = Graph()
        setter.set('set', LAYOUT + ':' + name)
        setter.wire(('entry.Document','set.self'), ('entry.Value','set.' + name))
        setter.chain('entry','set')
        setters.append(setter.function('Set' + name, inputs=[v('Document','object:' + LAYOUT), v('Value',kind)]))
    for name, kind in [('RetryInterval','double'),('MaxRetries','int'),('MaxSteps','int'),('AssetTimeout','double'),('BudgetSeconds','double'),('WorldActors','object:/Script/Engine.Actor[]')]:
        setter=Graph()
        owner=ROOT+('BP_DenWorld' if name=='WorldActors' else 'BP_DenApply')
        setter.set('set',owner+':'+name)
        setter.wire(('entry.Manager','set.self'),('entry.Value','set.'+name))
        setter.chain('entry','set')
        setters.append(setter.function('SetApply'+name,inputs=[v('Manager','object:'+ROOT+'BP_DenApply'),v('Value',kind)]))
    for name,kind in [('Editing','bool'),('DraftDue','double'),('DraftInterval','double'),('DraftEnabled','bool')]:
        setter=Graph();setter.set('set',ROOT+'BP_DenSession:'+name)
        setter.wire(('entry.Session','set.self'),('entry.Value','set.'+name));setter.chain('entry','set')
        setters.append(setter.function('SetSession'+name,inputs=[v('Session','object:'+ROOT+'BP_DenSession'),v('Value',kind)]))
    issue=Graph()
    issue.get('issues',ROOT+'BP_DenApply:Issues');issue.wire(('entry.Manager','issues.self'))
    from runtime import arr,unpack
    arr(issue,'item','Get','issues.Issues');issue.wire(('entry.Index','item.Index'))
    unpack(issue,'data',ROOT+'ST_DenApplyIssue','item.Item')
    issue.wire(('data.Value','result.Value'),('data.Code','result.Code'));issue.chain('entry','result')
    setters.append(issue.function('ReadApplyIssue',inputs=[v('Manager','object:'+ROOT+'BP_DenApply'),v('Index','int')],outputs=[v('Value','struct:'+ENTRY),v('Code','int')]))
    setter = Graph()
    setter.set('set', ROOT + 'BP_DenPresetLibrary:SchemaVersion')
    setter.wire(('entry.Document','set.self'), ('entry.Value','set.SchemaVersion'))
    setter.chain('entry','set')
    setters.append(setter.function('SetLibrarySchemaVersion', inputs=[v('Document','object:' + ROOT + 'BP_DenPresetLibrary'), v('Value','int')]))
    for name,kind in [('SchemaVersion','int'),('Entries','struct:'+ROOT+'ST_DenPreference[]')]:
        setter=Graph();setter.set('set',ROOT+'BP_DenPreferencesSave:'+name)
        setter.wire(('entry.Document','set.self'),('entry.Value','set.'+name));setter.chain('entry','set')
        setters.append(setter.function('SetPreferences'+name,inputs=[v('Document','object:'+ROOT+'BP_DenPreferencesSave'),v('Value',kind)]))
    setter=Graph();setter.set('set',ROOT+'BP_DenPreferences:PreferencesKey')
    setter.wire(('entry.Service','set.self'),('entry.Key','set.PreferencesKey'));setter.chain('entry','set')
    setters.append(setter.function('SetPreferencesKey',inputs=[v('Service','object:'+ROOT+'BP_DenPreferences'),v('Key','string')]))
    from runtime_key_names import CODEC, INPUT
    keytest=Graph();keytest.call('resolve',CODEC+':KeyFromName')
    keytest.call('describe',CODEC+':NameFromKey');keytest.call('valid',INPUT+'Key_IsValid')
    keytest.wire(('entry.Codec','resolve.self'),('entry.Name','resolve.Name'),('entry.Codec','describe.self'),('resolve.Key','describe.Key'),('resolve.Key','valid.Key'),
                 ('resolve.Known','result.Known'),('describe.Name','result.Canonical'),('valid.ReturnValue','result.Valid'))
    keytest.chain('entry','resolve','describe','result')
    setters.append(keytest.function('RoundTripKey',inputs=[v('Codec','object:'+CODEC),v('Name','string')],outputs=[v('Known','bool'),v('Canonical','string'),v('Valid','bool')]))
    samekeys=Graph();samekeys.call('same',INPUT+'EqualEqual_KeyKey')
    samekeys.wire(('entry.A','same.A'),('entry.B','same.B'),('same.ReturnValue','result.Equal'));samekeys.chain('entry','result')
    setters.append(samekeys.function('SameInputKeys',inputs=[v('A','struct:/Script/InputCore.Key'),v('B','struct:/Script/InputCore.Key')],outputs=[v('Equal','bool')]))
    return dict(kind='blueprint', path='/Game/DenNativeTests/BP_Fixture', parent='/Script/Engine.SaveGame',
                functions=[g.function('MakeEntry', inputs=[v('Kind','int'), v('Key','string'), v('Position','vector')],
                                      outputs=[v('Value','struct:' + ENTRY)]),
                           mutation.function('MakeMutation', inputs=[v('Value', 'struct:' + ENTRY), v('Present', 'bool')],
                                             outputs=[v('Mutation', 'struct:' + MUTATION)]), *setters])


try:
    paths = sorted((REPO / 'unreal/generated/runtime').glob('*.json'))
    if os.environ.get('DENDESIGNER_EXISTING') == '1':
        unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([ROOT.rstrip('/'), '/DenDesignerGF/Editor'], True)
        missing = [s['path'] for _,s in specs() if not unreal.EditorAssetLibrary.does_asset_exist(s['path'])]
        if not paths or missing:
            raise RuntimeError('existing runtime assets are missing: ' + ', '.join(missing))
        unreal.log('DENNATIVE using existing runtime assets without reauthoring')
    elif not paths or not zcom_authoring.build(paths):
        raise RuntimeError('runtime authoring failed')
    from runtime_store import FIELDS
    save_spec = next(s for _,s in specs() if s['path'] == LAYOUT)
    check(set(FIELDS) == {f['name'] for f in save_spec['variables']}, 'store clone and readback cover every persisted layout field')
    fixture = fixture_spec()
    report = json.loads(unreal.ZComAuthoringLibrary.build_asset_from_json(json.dumps(fixture)))
    check(report['ok'], 'fixture compiles: ' + str(report.get('messages', [])))
    if not report['ok']:
        raise RuntimeError('fixture authoring failed')
    make = unreal.GameplayStatics.create_save_game_object(unreal.EditorAssetLibrary.load_blueprint_class(fixture['path']))
    cls = unreal.EditorAssetLibrary.load_blueprint_class(LAYOUT)
    doc = unreal.GameplayStatics.create_save_game_object(cls)

    def entry(kind, key, xyz):
        return make.call_method('MakeEntry', (kind, key, unreal.Vector(*xyz)))

    def rows(value):
        return value.get_editor_property('Entries')

    def find(value, kind, key):
        return value.call_method('FindEntry', (kind, key))

    def put(value, row, present=True):
        return value.call_method('WriteEntry', (row, present))

    def xyz(row, name='Position'):
        p = field(row, name)
        return (p.x, p.y, p.z)

    def mutation(value, present=True):
        return make.call_method('MakeMutation', (value, present))

    def batch(target, mutations):
        result = target.call_method('ApplyBatch', (mutations,))
        # Blueprint array inputs are reference parameters: Python also returns
        # the input array before the two explicit outputs.
        assert len(result) == 3 and isinstance(result[1], bool)
        return result[1:]

    slot = 'ZComDen/Tests/NativeLayoutRoundtripV2'
    prior = unreal.GameplayStatics.does_save_game_exist(slot, 0)
    if prior:
        old = unreal.GameplayStatics.load_game_from_slot(slot, 0)
        check(old is not None and len(rows(old)) == 3, 'layout loads after asset rebuild')
        check(xyz(rows(old)[0]) == (21,22,23), 'rebuilt schema retains edited transform')
        check(field(rows(old)[1], 'Kind') == 1, 'rebuilt schema retains Storeroom kind')

    check(doc.get_editor_property('SchemaVersion') == 1, 'schema version default')
    check(find(doc, 0, 'missing') == -1, 'empty lookup returns missing')
    a = entry(0, 'p0001', (1,2,3))
    b = entry(0, 'p0002', (4,5,6))
    c = entry(2, '/Game/Hub.Hub:PersistentLevel.Chair.Mesh', (7,8,9))
    check(put(doc, a) and put(doc, b) and put(doc, c), 'placed and vanilla entries accepted')
    check(len(rows(doc)) == 3 and find(doc, 0, 'p0002') == 1, 'lookup scans beyond first entry')
    check(find(doc, 1, 'p0002') == -1, 'lookup distinguishes stored and placed')
    check(find(doc, 0, 'absent') == -1, 'lookup terminates for absent key')
    check(put(doc, entry(0, 'p0002', (21,22,23))), 'replace accepted')
    check(len(rows(doc)) == 3 and xyz(rows(doc)[1]) == (21,22,23), 'replace preserves count and changes correct item')
    check(xyz(rows(doc)[1], 'Scale') == (1,2,3), 'nonuniform scale retained')
    read = doc.call_method('ReadEntry', (0, 'p0002'))
    check(read[0] and xyz(read[1]) == (21,22,23), 'ReadEntry returns value and presence')
    read = doc.call_method('ReadEntry', (0, 'absent'))
    check(not read[0], 'ReadEntry reports absence without out-of-bounds read')
    check(put(doc, a, False) and find(doc, 0, 'p0001') == -1, 'remove entry')
    check(find(doc, 0, 'p0002') == 0, 'lookup follows indices shifted by removal')
    check(put(doc, a, False) and len(rows(doc)) == 2, 'removing absent entry is harmless')
    check(not put(doc, entry(3, 'bad', (0,0,0))) and len(rows(doc)) == 2, 'invalid kind rejected')
    check(not put(doc, entry(0, '', (0,0,0))) and len(rows(doc)) == 2, 'empty key rejected')
    check(put(doc, c, False) and put(doc, entry(1, 'p0001', (1,2,3))), 'Storeroom entry replaces removed native test entry')
    batchdoc = unreal.GameplayStatics.create_save_game_object(cls)
    accepted, changes = batch(batchdoc, [mutation(a), mutation(b)])
    check(accepted and len(rows(batchdoc)) == 2 and len(changes) == 2, 'grouped edit applies both entries')
    check(not field(changes[0], 'BeforeExists', CHANGE) and field(field(changes[0], 'Before', CHANGE), 'Key') == 'p0001', 'absent before-value retains identity for undo')
    accepted, changes = batch(batchdoc, [mutation(a, False), mutation(entry(1, 'p0001', (1,2,3)))])
    check(accepted and find(batchdoc, 0, 'p0001') == -1 and find(batchdoc, 1, 'p0001') >= 0, 'grouped store moves placed entry to Storeroom')
    accepted, _ = batch(batchdoc, [mutation(b, False), mutation(entry(9, 'invalid', (0,0,0)))])
    check(not accepted and find(batchdoc, 0, 'p0002') >= 0 and len(rows(batchdoc)) == 2, 'invalid batch rolls back earlier mutation')
    accepted, changes = batch(batchdoc, [mutation(entry(0, 'p0002', (10,20,30))), mutation(entry(0, 'p0002', (40,50,60)))])
    check(accepted and xyz(field(changes[1], 'Before', CHANGE)) == (10,20,30), 'repeated identity captures sequential before-values')
    check(xyz(rows(batchdoc)[0]) == (40,50,60), 'batch records final repeated-key value')
    accepted, _ = batch(batchdoc, [])
    check(not accepted and len(rows(batchdoc)) == 2, 'empty batch leaves document unchanged')
    history_class = unreal.EditorAssetLibrary.load_blueprint_class(ROOT + 'BP_DenHistory')
    history = unreal.new_object(history_class)
    historydoc = unreal.GameplayStatics.create_save_game_object(cls)
    history.call_method('Initialize', (historydoc,))

    def commit(edits, label='Edit', merge='', when=0):
        result = history.call_method('Commit', (edits, label, merge, when))
        assert len(result) == 2 and isinstance(result[1], bool)
        return result[1]

    def dirty():
        return history.call_method('IsDirty')

    check(not dirty() and not history.call_method('Undo')[0], 'new session is clean and has no undo')
    check(commit([mutation(a), mutation(b)], 'Place pair') and dirty(), 'grouped commit marks session dirty')
    history.call_method('MarkSaved')
    check(not dirty(), 'successful-save marker clears dirty state')
    stored_a = entry(1, 'p0001', (1,2,3))
    check(commit([mutation(a, False), mutation(stored_a)], 'Store prop'), 'store command commits as one step')
    ok, _ = history.call_method('Undo')
    check(ok and find(historydoc, 0, 'p0001') >= 0 and find(historydoc, 1, 'p0001') == -1, 'undo store restores placed prop and removes Storeroom entry')
    check(not dirty(), 'undo to saved version is clean')
    ok, _ = history.call_method('Redo')
    check(ok and find(historydoc, 0, 'p0001') == -1 and find(historydoc, 1, 'p0001') >= 0 and dirty(), 'redo store restores both changes and dirty state')
    before_steps = len(history.get_editor_property('UndoSteps'))
    check(not commit([mutation(b, False), mutation(entry(7, 'bad', (0,0,0)))]), 'invalid history commit rejected')
    check(len(history.get_editor_property('UndoSteps')) == before_steps and find(historydoc, 0, 'p0002') >= 0, 'failed commit changes neither layout nor history')
    check(commit([mutation(entry(0, 'p0002', (10,20,30))), mutation(entry(0, 'p0002', (40,50,60)))], 'Repeated key'), 'repeated-key commit accepted')
    history.call_method('Undo')
    check(xyz(rows(historydoc)[find(historydoc, 0, 'p0002')]) == (4,5,6), 'undo applies repeated-key changes in reverse order')
    history.call_method('Redo')
    check(xyz(rows(historydoc)[find(historydoc, 0, 'p0002')]) == (40,50,60), 'redo applies repeated-key changes in forward order')
    history.call_method('Undo')
    check(commit([mutation(entry(0, 'p0002', (70,80,90)))], 'New branch'), 'commit after undo branches history')
    check(not history.call_method('Redo')[0], 'new branch clears redo')
    history.call_method('Initialize', (historydoc,))
    check(not dirty() and len(history.get_editor_property('UndoSteps')) == 0, 'new session resets history and saved marker')
    for n in range(202):
        assert commit([mutation(entry(0, 'p0002', (n,0,0)))])
    check(len(history.get_editor_property('UndoSteps')) == 200, 'history retains the most recent 200 steps')
    for n in range(200):
        assert history.call_method('Undo')[0]
    check(not history.call_method('Undo')[0] and xyz(rows(historydoc)[find(historydoc, 0, 'p0002')]) == (1,0,0), 'history limit preserves the correct earliest retained state')
    mergedoc = unreal.GameplayStatics.create_save_game_object(cls)
    put(mergedoc, b)
    history.call_method('Initialize', (mergedoc,))
    check(commit([mutation(entry(0, 'p0002', (10,0,0)))], 'Nudge', 'move:p0002', 10) and
          commit([mutation(entry(0, 'p0002', (20,0,0)))], 'Nudge', 'move:p0002', 10.5), 'nearby adjustments commit')
    check(len(history.get_editor_property('UndoSteps')) == 1, 'nearby same-key adjustments merge into one undo step')
    history.call_method('Undo')
    check(xyz(rows(mergedoc)[0]) == (4,5,6), 'merged undo restores original pre-adjustment transform')
    history.call_method('Redo')
    check(xyz(rows(mergedoc)[0]) == (20,0,0), 'merged redo restores latest transform')
    commit([mutation(entry(0, 'p0002', (30,0,0)))], 'Nudge', 'move:p0002', 10.6)
    check(len(history.get_editor_property('UndoSteps')) == 2, 'redone step does not merge with subsequent edit')
    history.call_method('MarkSaved')
    commit([mutation(entry(0, 'p0002', (40,0,0)))], 'Nudge', 'move:p0002', 10.7)
    check(len(history.get_editor_property('UndoSteps')) == 3 and dirty(), 'edit after save keeps saved boundary and becomes dirty')
    history.call_method('Undo')
    check(not dirty() and xyz(rows(mergedoc)[0]) == (30,0,0), 'undo after saved boundary restores exact saved state')
    history.call_method('Redo')
    commit([mutation(entry(0, 'p0002', (50,0,0)))], 'Nudge', 'move:p0002', 20)
    check(len(history.get_editor_property('UndoSteps')) == 4, 'adjustments outside merge window stay separate')
    commit([mutation(a)], 'Different prop', 'move:p0002', 20.1)
    check(len(history.get_editor_property('UndoSteps')) == 5, 'same merge label cannot merge different object identities')
    commit([mutation(entry(0, 'p0001', (2,3,4)))], 'Nudge', 'move:p0002', 19)
    check(len(history.get_editor_property('UndoSteps')) == 6, 'backward clock cannot merge adjustments')
    history.call_method('Initialize', (mergedoc,))
    pair1 = [mutation(entry(0,'p0001',(100,0,0))), mutation(entry(0,'p0002',(200,0,0)))]
    pair2 = [mutation(entry(0,'p0001',(110,0,0))), mutation(entry(0,'p0002',(210,0,0)))]
    commit(pair1, 'Move pair', 'pair', 30)
    commit(pair2, 'Move pair', 'pair', 30.5)
    check(len(history.get_editor_property('UndoSteps')) == 1, 'matching multi-entry adjustments merge')
    history.call_method('Undo')
    check(xyz(rows(mergedoc)[find(mergedoc,0,'p0001')]) == (2,3,4) and
          xyz(rows(mergedoc)[find(mergedoc,0,'p0002')]) == (50,0,0), 'merged group restores each original entry')
    material_row = rows(doc)[0]
    material_row.set_editor_property(field_name('Materials'), ['', '/Game/Test/MI_Override.MI_Override'])
    put(doc, material_row)
    partial = entry(2, '/Game/Hub.Hub:PersistentLevel.Panel.Mesh', (0,0,0))
    partial.set_editor_property(field_name('HasPosition'), False)
    partial.set_editor_property(field_name('HasScale'), False)
    partial.set_editor_property(field_name('Hidden'), True)
    put(doc, partial)
    check(unreal.GameplayStatics.save_game_to_slot(doc, slot, 0), 'native layout saved in nested mod slot')
    fixture_dir=REPO / 'dist/verification/native/migration-fixtures'
    fixture_dir.mkdir(parents=True,exist_ok=True)
    saved_root=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))
    (fixture_dir/'layout.sav').write_bytes((saved_root/'SaveGames'/(slot+'.sav')).read_bytes())
    loaded = unreal.GameplayStatics.load_game_from_slot(slot, 0)
    check(loaded is not None and len(rows(loaded)) == 3, 'layout array reloads')
    check(xyz(rows(loaded)[0]) == (21,22,23) and xyz(rows(loaded)[0], 'Scale') == (1,2,3), 'transform survives SaveGame')
    check(field(rows(loaded)[0], 'CollisionMode') == 2 and field(rows(loaded)[0], 'HasFingerprint'), 'collision and fingerprint flags survive SaveGame')
    check(field(rows(loaded)[1], 'Kind') == 1, 'stored entry survives SaveGame')
    check(list(field(rows(loaded)[0], 'Materials')) == ['', '/Game/Test/MI_Override.MI_Override'], 'material overrides preserve empty default slots')
    partial_loaded = rows(loaded)[2]
    check(not field(partial_loaded, 'HasPosition') and field(partial_loaded, 'HasRotation') and not field(partial_loaded, 'HasScale') and field(partial_loaded, 'Hidden'), 'partial native edits preserve absent transform fields and hidden state')
    sys.path.insert(0, str(REPO / 'tests/unreal'))
    import test_storage
    test_storage.run(unreal, ROOT, LAYOUT, doc, make, check)
    import test_layouts
    test_layouts.run(unreal, ROOT, doc, make, check)
    import test_presets
    test_presets.run(unreal, ROOT, doc, make, field, field_name, check)
    import test_preferences_native
    test_preferences_native.run(unreal, ROOT, make, field, field_name, check)
    import test_input_mappings_native
    test_input_mappings_native.run(unreal, make, field, field_name, check)
    import test_migration
    test_migration.run(unreal, REPO, ROOT, make, check)
    import test_world
    test_world.run(unreal, ROOT, make, field, field_name, check)
    import test_apply
    test_apply.run(unreal, ROOT, make, field, field_name, check)
    import test_session
    test_session.run(unreal, ROOT, make, field, field_name, check)
    import test_pick
    test_pick.run(unreal, ROOT, make, field, field_name, check)
    import test_gizmo_native
    test_gizmo_native.run(unreal, ROOT, check)
    import test_catalog_native
    test_catalog_native.run(unreal, REPO, check)
    import test_prop_packs_native
    test_prop_packs_native.run(unreal, check)
    import test_editor_native
    import test_thumbnails_native
    test_thumbnails_native.run(unreal,check)
    test_editor_native.run(unreal, ROOT, make, field, field_name, check)
    import test_coordinator_native
    test_coordinator_native.run(unreal,check)
    if prior and not failures:
        check(unreal.GameplayStatics.delete_game_in_slot(slot,0), 'test slot removed after rebuild verification')
except Exception:
    failures.append(traceback.format_exc())
    unreal.log_error(failures[-1])
finally:
    unreal.ZComAuthoringLibrary.force_delete_assets(['/Game/DenNativeTests/BP_Fixture'])

unreal.log(f'DENNATIVE_RESULT {"failed" if failures else "ok"} ({checks} checks)')
