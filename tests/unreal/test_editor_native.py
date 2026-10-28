"""Execute native UI routing without claiming headless UMG/camera validation."""
import json
import os
import uuid
from pathlib import Path


def fixture_spec():
    from graph import Graph, variable as v
    from runtime_editor_assets import BUS, EVENT, RIG, UIROOT
    from runtime_editor_host import HOST, PC

    from runtime import LAYOUT,ENTRY
    from runtime_catalog import DATA
    from runtime_pick import PICKER,FACT
    functions = []
    # PlayerControllers are runtime actors; the editor placement factory cannot place one in a level.
    g=Graph()
    g.call('transform','/Script/Engine.KismetMathLibrary:MakeTransform',Scale='1,1,1')
    g.call('spawn','/Script/Engine.GameplayStatics:BeginDeferredActorSpawnFromClass',ActorClass=PC,
           CollisionHandlingOverride='AlwaysSpawn')
    g.wire(('entry.World','spawn.WorldContextObject'),('transform.ReturnValue','spawn.SpawnTransform'))
    g.call('finish','/Script/Engine.GameplayStatics:FinishSpawningActor')
    g.wire(('spawn.ReturnValue','finish.Actor'),('transform.ReturnValue','finish.SpawnTransform'),('finish.ReturnValue','result.Actor'))
    g.chain('entry','spawn','finish','result')
    functions.append(g.function('SpawnPointerController',inputs=[v('World','object:/Script/CoreUObject.Object')],
                                outputs=[v('Actor','object:/Script/Engine.Actor')]))
    for owner, fields in [
        (HOST, [('InputBus', 'object:'+BUS), ('UIOpen', 'bool'), ('EditorController','object:'+PC),
                ('PointerRestoreFrame','int64'), ('Looking','bool'),
                ('EditorRig', 'object:'+RIG), ('LastStatus', 'int'),
                ('LastDraftStatus', 'int'), ('GridStep', 'double'), ('PresetStorageKey','string'),('CompositionStorageKey','string'), ('ActiveCampaignID','string'), ('HomeStorageKey','string'), ('PreferencesStorageKey','string'), ('PreferencesStatus','int'),
                ('Toolbar','object:'+UIROOT+'WBP_DenToolbar'), ('Inspector','object:'+UIROOT+'WBP_DenTransform'),
                ('SettingsPanel','object:'+UIROOT+'WBP_DenSettings'), ('HasSelection','bool'),
                ('RotationPivot','string'), ('SnapEnabled','bool'), ('SurfaceDragging','bool'), ('SurfaceVertical','bool'), ('GizmoDragKind','int'), ('GizmoDragVector','vector')]),
        (PC, [('bShowMouseCursor','bool')]),
        (RIG, [('EditorBus', 'object:'+BUS), ('OpeningInputBlocked', 'bool'), ('bAlt', 'bool')]),
        (DATA, [('Paths', 'string[]')]),
        (LAYOUT, [('Entries','struct:'+ENTRY+'[]')]),
        (PICKER, [('QueryReady','bool'),('QueryPending','bool'),('QueryResult','struct:'+FACT),('SurfaceCandidates','object:/Script/Engine.StaticMeshComponent[]')]),
    ]:
        for field, kind in fields:
            g = Graph()
            g.set('write', owner+':'+field)
            g.wire(('entry.Owner', 'write.self'), ('entry.Value', 'write.'+field))
            g.chain('entry', 'write')
            functions.append(g.function('Set'+field, inputs=[
                v('Owner', 'object:'+owner), v('Value', kind)]))
    from runtime_settings_widget import PATH as SETTINGS
    for name,field_,kind in [('SetSettingsBus','EditorBus','object:'+BUS),('SetSettingsRefreshing','Refreshing','bool')]:
        g=Graph();g.set('write',SETTINGS+':'+field_)
        g.wire(('entry.Owner','write.self'),('entry.Value','write.'+field_));g.chain('entry','write')
        functions.append(g.function(name,inputs=[v('Owner','object:'+SETTINGS),v('Value',kind)]))
    g = Graph()
    g.node('event', 'make_struct', struct=EVENT)
    g.wire(('entry.Name', 'event.EventName'),
           ('event.ST_DenEditorEvent', 'result.Value'))
    g.chain('entry', 'result')
    functions.append(g.function('MakeEvent', inputs=[v('Name', 'string')],
                                outputs=[v('Value', 'struct:'+EVENT)]))
    return dict(kind='blueprint', path='/Game/DenNativeTests/BP_EditorFixture',
                parent='/Script/Engine.SaveGame', functions=functions)


def run(unreal, root, fixture, field, field_name, check):
    from runtime_editor_assets import BUS, EVENT, RIG
    from runtime_editor_host import HOST

    saved = Path(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_saved_dir())).resolve()
    assert saved == Path(os.environ['DENDESIGNER_TEST_SAVED']).resolve()
    spec = fixture_spec()
    result = json.loads(unreal.ZComAuthoringLibrary.build_asset_from_json(json.dumps(spec)))
    check(result['ok'], 'native UI fixture compiles: '+str(result.get('messages', [])))
    assert result['ok']
    helper = unreal.GameplayStatics.create_save_game_object(
        unreal.EditorAssetLibrary.load_blueprint_class(spec['path']))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    host = None
    key = 'test_editor_'+uuid.uuid4().hex
    paths = []

    def get(obj, name):
        return obj.get_editor_property(name)

    def set_(obj, name, value):
        helper.call_method('Set'+name, (obj, value))

    def spawn(path):
        obj = actors.spawn_actor_from_class(
            unreal.EditorAssetLibrary.load_blueprint_class(path),
            unreal.Vector(), unreal.Rotator(), transient=True)
        spawned.append(obj)
        return obj

    def drain(host):
        for _ in range(200):
            if not get(host, 'Busy'):
                return
            host.call_method('Pump')
        raise AssertionError('native UI session did not finish applying')

    bus = unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(BUS))

    def emit(name, number=0, direction=None):
        return bus.call_method('Emit', (
            0, name, 'argument:'+name, float(number), direction or unreal.Vector()))

    def take():
        found, value = bus.call_method('Take')
        return found, value

    def name(value):
        return field(value, 'EventName', EVENT)

    try:
        check(not emit('ignored') and not take()[0], 'closed UI drops commands before startup')
        bus.call_method('Start')
        emit('first', 1, unreal.Vector(1, 2, 3))
        emit('second', 2)
        ok, first = take()
        ok2, second = take()
        check(ok and ok2 and name(first) == 'first' and name(second) == 'second'
              and field(first, 'Scalar', EVENT) == 1
              and field(first, 'Argument', EVENT) == 'argument:first'
              and field(first, 'Direction', EVENT).z == 3,
              'UI queue preserves FIFO order and copies payloads before removal')
        check(not take()[0], 'drained UI queue reports no command')
        for i in range(256):
            emit('event'+str(i))
        emit('look_hold', 0)
        events = [take()[1] for _ in range(256)]
        check(get(bus, 'Dropped') == 1 and name(events[0]) == 'event1'
              and name(events[-1]) == 'look_hold' and not take()[0],
              'bounded UI queue retains the newest release after overflow')
        emit('stale')
        bus.call_method('Stop')
        check(not take()[0] and not emit('late'), 'UI teardown clears queued and late commands')
        bus.call_method('Start')
        check(not take()[0], 'UI reopening cannot replay an old command')

        rig = spawn(RIG)
        rig.call_method('Native_Action', ('click', 1.0))
        check(not take()[0], 'unbound camera input is harmless')
        set_(rig, 'EditorBus', bus)
        rig.call_method('Native_Action', ('store', 1.0))
        rig.call_method('Native_Vector', ('nudge', unreal.Vector(0, 1, 0)))
        check(not take()[0] and get(rig, 'OpeningInputBlocked'),
              'opening latch rejects edit commands until a player can confirm key release')
        # Headless tests have no local player/key state. Exercise the released
        # branch explicitly; physical held/released keys are checked in game.
        set_(rig, 'OpeningInputBlocked', False)
        check(rig.call_method('OpeningInputReady'),
              'released opening latch stays ready without querying a player')
        rig.call_method('Native_Action', ('look_hold', 1.0))
        rig.call_method('Native_Vector', ('nudge', unreal.Vector(0, 1, 0)))
        _, press = take()
        _, vector = take()
        check(name(press) == 'look_hold' and field(press, 'Scalar', EVENT) == 1
              and name(vector) == 'nudge' and field(vector, 'Kind', EVENT) == 1
              and field(vector, 'Direction', EVENT).y == 1,
              'native rig sends scalar and vector input through the editor bus')

        pointer_host=spawn(HOST)
        pointer_controller=helper.call_method('SpawnPointerController',(pointer_host,))
        spawned.append(pointer_controller)
        import test_editor_pointer_native
        pointer_bus=unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(BUS))
        try:
            test_editor_pointer_native.run(unreal,pointer_host,pointer_controller,pointer_bus,get,set_,check)
        finally:
            # Other headless fixtures expect no player controller in the editor world.
            pointer_host.call_method('DetachEditor',(False,))
            actors.destroy_actor(pointer_controller)
            actors.destroy_actor(pointer_host)

        host = spawn(HOST)
        store = unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenLayouts'))
        for draft, count in [(False, 6), (True, 2)]:
            for bank in range(count):
                slot = store.call_method('BankSlot', (key, bank, draft))
                path = saved/'SaveGames'/(slot+'.sav')
                assert path.is_relative_to(saved/'SaveGames/ZComDen/Native/v1')
                assert path.name.startswith(key)
                paths.append(path)
        doc, status, _ = store.call_method('LoadLayout', (key, False, 0))
        check(host.call_method('OpenSession', (key, doc, status)), 'native UI host opens an isolated editing session')
        drain(host)
        check(not host.call_method('MountEditor', (None,)) and not get(host, 'UIOpen')
              and get(host, 'EditorController') is None,
              'mount without a player leaves controller and viewport untouched')
        set_(host, 'InputBus', bus)
        set_(host, 'UIOpen', True)
        set_(host, 'EditorRig', rig)
        set_(host, 'PresetStorageKey', key+'_presets')
        set_(host, 'HomeStorageKey', key)
        set_(host, 'PreferencesStorageKey', key+'_preferences')
        for bank in range(6):
            path=saved/'SaveGames'/(store.call_method('BankSlot',(key+'_preferences',bank,False))+'.sav')
            assert not path.exists()
            paths.append(path)

        import test_input_ui_native
        test_input_ui_native.run(unreal,host,rig,get,check)
        import test_settings_native
        test_settings_native.run(unreal,host,rig,bus,get,check,helper,field)

        def command(name_,number=0):
            emit(name_,number)
            host.call_method('ProcessEditorEvents')
            host.call_method('PumpEditorMutations')

        command('catalog')
        check(get(host, 'ActivePanel') == 'catalog', 'catalog button routes through native UI queue')
        command('storeroom')
        check(get(host, 'ActivePanel') == 'storeroom', 'changing panels selects only the new panel')
        command('storeroom')
        check(get(host, 'ActivePanel') == '', 'repeating a panel button closes it')
        command('layouts')
        command('help')
        command('back')
        check(not get(host, 'HelpOpen') and get(host, 'ActivePanel') == 'layouts',
              'back closes help before the current panel')
        command('back')
        check(get(host, 'ActivePanel') == '' and get(host, 'Editing'),
              'back closes the side panel before exiting the editor')
        for value in [5, 10, 25, 50, 0]:
            command('snap')
            assert get(host, 'GridStep') == value
        check(get(host, 'GridIndex') == 0, 'grid cycles through supported increments and returns to off')
        for value in [4000, 10000, 1000, 2000]:
            command('reach')
            assert get(host, 'ReachCm') == value
        check(get(host, 'ReachIndex') == 1, 'range cycles and returns to the 20 metre default')
        command('lock')
        command('floors')
        check(get(host, 'StructureEnabled') and not get(host, 'FloorsEnabled'),
              'quick toggles use structure-on and selectable-floors semantics')
        command('walls')
        check(get(host,'WallsEnabled') and get(host,'StructureEnabled') and not get(host,'FloorsEnabled'),
              'Walls toolbar command toggles only wall selection')
        command('walls')
        check(not get(host,'WallsEnabled'), 'Walls toolbar command turns wall selection off again')
        import test_editor_ui_native
        test_editor_ui_native.run(unreal,host,get,set_,command,check)
        host.call_method('SetEditorConfirm', (1,))
        command('snap')
        command('catalog')
        check(get(host, 'GridStep') == 0 and get(host, 'ActivePanel') == ''
              and not get(rig, 'ControlsEnabled'),
              'confirmation blocks ordinary UI commands and camera motion')
        command('back')
        check(get(host, 'ConfirmMode') == 0 and get(rig, 'ControlsEnabled')
              and get(host, 'Editing'), 'back cancels the exit dialog and restores camera controls')
        command('confirm_save')
        command('confirm_discard')
        check(get(host, 'Editing') and get(host, 'UIOpen'),
              'stale confirmation clicks cannot close an editor without a dialog')

        from test_catalog_ui_native import run as test_catalog_ui
        test_catalog_ui(unreal,host,bus,get,check)

        # Selection uses native UObject references and restores the exact preexisting
        # outline state; Escape must deselect without leaving the session.
        target=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(15000,15000,15000),unreal.Rotator(),transient=True)
        spawned.append(target)
        comp=target.static_mesh_component
        comp.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
        comp.set_render_custom_depth(True)
        comp.set_custom_depth_stencil_value(7)
        host.call_method('InitializeSelection')
        picker=get(host,'Picker')
        facts=picker.call_method('Classify',(host,comp,True,True,True))
        host.call_method('AcceptSelection',(facts,))
        check(get(host,'HasSelection') and comp.get_editor_property('custom_depth_stencil_value')==32,
              'native selection applies the selected outline')
        check(len(get(host,'Records'))==1, 'native selection captures vanilla baseline before editing')
        def settle_edits():
            for _ in range(1000):
                host.call_method('Pump')
                job=get(host,'PendingJob')
                if job is not None and unreal.SystemLibrary.is_valid(job):job.call_method('ReceiveTick',(1/60,))
                unreal.ZComAuthoringLibrary.process_test_latent_actions(host)
                host.call_method('PollSelection')
                host.call_method('PollCopiedSelection')
                host.call_method('PumpEditorMutations')
                if not get(host,'Busy') and len(get(host,'EditEvents'))==0:return
            raise AssertionError('native edit queue did not settle')
        neighbor=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(25000,25000,25000),unreal.Rotator(),transient=True)
        spawned.append(neighbor)
        neighbor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
        neighbor.static_mesh_component.set_collision_profile_name('BlockAll')
        def edit_without_selection_stall(label,action):
            host.call_method('PollSelection')
            for _ in range(2000):
                if not get(picker,'Indexing'):break
                picker.call_method('PumpIndex')
            assert not get(picker,'Indexing')
            old_steps=get(picker,'MaxSteps')
            assert not unreal.ZComAuthoringLibrary.set_property_from_text(picker,'MaxSteps','1')
            try:
                action();settle_edits()
                check(not get(picker,'Indexing'),label+' updates changed props without restarting a Den selection scan')
            finally:
                assert not unreal.ZComAuthoringLibrary.set_property_from_text(picker,'MaxSteps',str(old_steps))
        def store_without_selection_stall(label):
            picker.call_method('BeginIndex',(host,))
            for _ in range(2000):
                picker.call_method('PumpIndex')
                if not get(picker,'Indexing'):break
            assert not get(picker,'Indexing')
            old_steps=get(picker,'MaxSteps')
            assert not unreal.ZComAuthoringLibrary.set_property_from_text(picker,'MaxSteps','1')
            try:
                command('store');settle_edits()
                check(not get(picker,'Indexing'),label+' Store keeps the completed selection index instead of restarting a Den scan')
            finally:
                assert not unreal.ZComAuthoringLibrary.set_property_from_text(picker,'MaxSteps',str(old_steps))
            # Do not pump the index: the next click must work without waiting for it.
            picker.call_method('RequestPick',(unreal.Vector(24700,25000,25000),unreal.Vector(1,0,0),500.,True,True,True))
            for _ in range(2000):
                picker.call_method('PumpQuery')
                if get(picker,'QueryReady'):break
            picked=get(picker,'QueryResult')
            check(get(picker,'QueryReady') and field(picked,'Allowed',root+'ST_DenPick')
                  and field(picked,'Target',root+'ST_DenPick')==neighbor,
                  label+' Store allows the next prop pick without a background reindex')
            picker.call_method('CancelQuery')
        def current_entry():
            values=get(get(host,'WorkingDocument'),'Entries')
            return next(row for row in values if field(row,'Key')==target.get_path_name())
        def location(actor):
            at=actor.get_actor_location();return (round(at.x,4),round(at.y,4),round(at.z,4))
        for source,expected in [(' 12,5 ',12.5),('-2.75',-2.75),('0',0.),('1e3',1000.),('-2.5E-2',-.025)]:
            valid,value=host.call_method('ParseTransformNumber',(source,))
            check(valid and value==expected,'numeric transform accepts '+repr(source))
        for source in ['', '+', '-', '.', '-.', '1e', 'e3', '1e2.5', 'nan', 'inf', '12garbage', '1,2,3', '10000001', '1e309']:
            check(not host.call_method('ParseTransformNumber',(source,))[0], 'numeric transform rejects '+repr(source))
        host.call_method('SetSelectionField',('X','15025.5'));settle_edits()
        row=current_entry()
        check(location(target)==(15025.5,15000.,15000.) and get(host,'HasSelection'),
              'numeric position applies and keeps the same object selected')
        check(field(row,'HasPosition') and not field(row,'HasRotation') and not field(row,'HasScale'),
              'numeric change preserves absent vanilla transform groups')
        check(field(row,'HasFingerprint') and field(row,'FingerprintPosition')==unreal.Vector(15000,15000,15000),
              'first numeric edit fingerprints the original pose')
        count=len(get(get(host,'History'),'UndoSteps'))
        host.call_method('SetSelectionField',('X','15025.5000'));settle_edits()
        host.call_method('SetSelectionField',('X','not a number'));settle_edits()
        check(len(get(get(host,'History'),'UndoSteps'))==count and location(target)[0]==15025.5,
              'unchanged and invalid numeric fields add no history and move nothing')
        host.call_method('SetSelectionField',('X','15025.5'));settle_edits()
        check(get(host,'SelectionMessage')=='' and len(get(get(host,'History'),'UndoSteps'))==count,
              'valid unchanged input clears the previous validation error without an edit')
        host.call_method('RotateSelection',(1.,15.));settle_edits()
        check(abs(target.get_actor_rotation().yaw-15)<.001, 'keyboard rotation uses the configured angular step')
        host.call_method('NudgeSelection',(unreal.Vector(1,0,0),));settle_edits()
        check(location(target)[0]==15030.5, 'keyboard nudge follows camera-aligned world axes')
        host.call_method('ScaleSelection',(1.,));settle_edits()
        check(abs(target.get_actor_scale3d().x-1.05)<.0001, 'keyboard scaling applies proportional factor')
        command('undo');settle_edits()
        check(abs(target.get_actor_scale3d().x-1)<.0001 and get(host,'HasSelection'), 'native undo restores scale without losing selection')
        command('redo');settle_edits()
        check(abs(target.get_actor_scale3d().x-1.05)<.0001, 'native redo reapplies scale')
        # The queue must preserve all inputs and save only after their application.
        for name_ in ['rotate','rotate','save']:emit(name_,1)
        host.call_method('ProcessEditorEvents')
        check(len(get(host,'EditEvents'))==3, 'rapid rotations and save remain in arrival order')
        settle_edits()
        disk,loadstatus,_=store.call_method('LoadLayout',(key,False,0))
        saved_row=next(row for row in get(disk,'Entries') if field(row,'Key')==target.get_path_name())
        check(loadstatus==1 and abs(field(saved_row,'Rotation').yaw-45)<.001 and not get(host,'History').call_method('IsDirty'),
              'queued Save waits for both rotations and verifies their final transform')
        emit('rotate',1);host.call_method('ProcessEditorEvents')
        other=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(16000,15000,15000),unreal.Rotator(),transient=True)
        spawned.append(other);other.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
        host.call_method('RefreshActors');otherfacts=picker.call_method('Classify',(host,other.static_mesh_component,True,True,True))
        host.call_method('AcceptSelection',(otherfacts,));settle_edits()
        check(abs(other.get_actor_rotation().yaw)<.001 and abs(target.get_actor_rotation().yaw-45)<.001,
              'queued edit cannot change a newly selected object')
        facts=picker.call_method('Classify',(host,comp,True,True,True));host.call_method('AcceptSelection',(facts,))
        while len(get(get(host,'History'),'UndoSteps')):
            command('undo');settle_edits()
        command('save');settle_edits()
        check(len(get(get(host,'WorkingDocument'),'Entries'))==0 and location(target)==(15000.,15000.,15000.),
              'undoing the complete native edit sequence restores untouched vanilla state')
        precise=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(15000.1234,-15000.5678,15000.9876),unreal.Rotator(pitch=1.1234,yaw=2.5678,roll=3.9876),transient=True)
        spawned.append(precise);precise.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
        precise.set_actor_scale3d(unreal.Vector(1.2344,2.3456,3.4567))
        host.call_method('RefreshActors')
        precise_facts=picker.call_method('Classify',(host,precise.static_mesh_component,True,True,True))
        host.call_method('AcceptSelection',(precise_facts,))
        original_pose=precise.get_actor_transform()
        count=len(get(get(host,'History'),'UndoSteps'))
        # Headless hosts have no Slate widgets. These values match the native
        # formatter's two-decimal display; none are rounding tie cases.
        for name_,shown in [('X','15000.12'),('Y','-15000.57'),('Z','15000.99'),
                            ('Pitch','1.12'),('Yaw','2.57'),('Roll','3.99'),('Scale','1.23')]:
            host.call_method('SetSelectionField',(name_,shown));settle_edits()
            check(len(get(get(host,'History'),'UndoSteps'))==count and precise.get_actor_transform()==original_pose,
                  'submitting rounded '+name_+' preserves exact pose and creates no history')
        host.call_method('SetSelectionField',('X','15000.1236'));settle_edits()
        check(abs(precise.get_actor_location().x-15000.1236)<1e-8,
              'explicit sub-display precision input remains supported')
        command('undo');settle_edits()
        check(precise.get_actor_transform()==original_pose, 'undo precision edit restores the unrounded original')
        from test_drag_native import run as test_drag
        test_drag(unreal,host,precise,precise_facts,get,field,check,settle_edits,command)
        def spawn_at(cls, location):
            obj = actors.spawn_actor_from_class(cls, location, unreal.Rotator(), transient=True)
            spawned.append(obj)
            return obj
        from test_snap_native import run_drag as test_snap_drag
        test_snap_drag(unreal, host, picker, spawn_at, get, set_, check)
        from test_pivot_native import run as test_pivot
        test_pivot(unreal, host, picker, spawn_at, get, set_, check, settle_edits, command)
        from test_gizmo_controller import run as test_gizmo_controller
        test_gizmo_controller(unreal,host,precise,precise_facts,get,field,check,settle_edits,command)
        from test_surface_native import run as test_surface
        test_surface(unreal,host,precise,precise_facts,get,check,settle_edits,command,set_)
        from test_copy_native import run as test_copy
        test_copy(unreal,host,precise,precise_facts,facts,get,field,check,settle_edits,command)
        host.call_method('ClearSelection')
        from test_placement_native import run as test_placement
        test_placement(unreal,host,bus,get,field,check,settle_edits,command,set_)
        from test_compositions_native import run as test_compositions
        test_compositions(unreal,host,bus,precise,precise_facts,get,field,field_name,check,settle_edits,command,set_,saved)
        from test_storeroom_native import run as test_storeroom
        test_storeroom(unreal,host,bus,fixture,precise,precise_facts,get,field,field_name,check,settle_edits,command)
        from test_layout_ui_native import run as test_layout_ui
        test_layout_ui(unreal,host,bus,fixture,get,field,field_name,check,settle_edits,command,set_,saved)
        # Exercise the same commands on placed data, including metadata that a
        # transform command must not accidentally reconstruct or discard.
        placed_value=fixture.call_method('MakeEntry',(0,'transform_placed',unreal.Vector(15500,15000,15000)))
        mesh=unreal.load_asset('/Engine/BasicShapes/Cube')
        material=unreal.load_asset('/Engine/EngineDebugMaterials/VertexColorMaterial')
        placed_value.set_editor_property(field_name('Mesh'),mesh.get_path_name())
        placed_value.set_editor_property(field_name('Materials'),[material.get_path_name()])
        placed_value.set_editor_property(field_name('Scale'),unreal.Vector(2,3,4))
        mutation=fixture.call_method('MakeMutation',(placed_value,True))
        edit_without_selection_stall('Adding a prop',lambda:host.call_method('CommitEdit',([mutation],'Add fixture','')))
        placed_actor=next(actor for actor in get(host,'Placed') if field(get(actor,'Current'),'Key')=='transform_placed')
        placed_component=placed_actor.get_component_by_class(unreal.StaticMeshComponent)
        placedfacts=picker.call_method('Classify',(host,placed_component,True,True,True));host.call_method('AcceptSelection',(placedfacts,))
        test_drag(unreal,host,placed_actor,placedfacts,get,field,check,settle_edits,command)
        test_copy(unreal,host,placed_actor,placedfacts,facts,get,field,check,settle_edits,command)
        host.call_method('ScaleSelection',(1.,));settle_edits()
        sc=placed_actor.get_actor_scale3d()
        check(abs(sc.x-2.1)<.0001 and abs(sc.y-3.15)<.0001 and abs(sc.z-4.2)<.0001,
              'placed proportional scale preserves nonuniform proportions')
        row=next(row for row in get(get(host,'WorkingDocument'),'Entries') if field(row,'Key')=='transform_placed')
        check(list(field(row,'Materials'))==[material.get_path_name()] and field(row,'CollisionMode')==2 and field(row,'Source')==field(placed_value,'Source')
              and field(row,'FingerprintMesh')==field(placed_value,'FingerprintMesh'),
              'placed transforms preserve material collision source and fingerprint metadata')
        command('reset');settle_edits()
        sc=placed_actor.get_actor_scale3d();rot=placed_actor.get_actor_rotation()
        check(sc==unreal.Vector(1,1,1) and abs(rot.pitch)<.001 and abs(rot.roll)<.001 and abs(rot.yaw-20)<.001,
              'placed reset straightens pitch and roll, keeps yaw, and restores unit scale')
        command('undo');settle_edits()
        check(abs(placed_actor.get_actor_scale3d().z-4.2)<.0001, 'placed reset is undoable')
        store_without_selection_stall('Placed prop')
        stored=next(row for row in get(get(host,'WorkingDocument'),'Entries') if field(row,'Key')=='transform_placed')
        check(field(stored,'Kind')==1 and not unreal.SystemLibrary.is_valid(placed_actor) and not get(host,'HasSelection'),
              'Store atomically moves a placed prop into stored data and destroys its live actor')
        # An older hint cannot replace the completed batch's actual membership delta.
        host.call_method('ReuseSelectionIndex')
        edit_without_selection_stall('Undo Store',lambda:command('undo'))
        restored=next(actor for actor in get(host,'Placed') if field(get(actor,'Current'),'Key')=='transform_placed')
        check(restored!=placed_actor and abs(restored.get_actor_scale3d().z-4.2)<.0001,
              'Undo Store respawns the prop with its exact prior transform')
        while len(get(get(host,'History'),'UndoSteps')):
            command('undo');settle_edits()
        command('save');settle_edits()
        facts=picker.call_method('Classify',(host,comp,True,True,True));host.call_method('AcceptSelection',(facts,))
        store_without_selection_stall('Existing scenery')
        check(target.get_editor_property('hidden') and field(current_entry(),'Hidden'),
              'Store hides native objects through separate layout data')
        command('undo');settle_edits()
        check(not target.get_editor_property('hidden'), 'Undo Store restores native visibility')
        facts=picker.call_method('Classify',(host,comp,True,True,True));host.call_method('AcceptSelection',(facts,))
        bus.call_method('Emit',(2,'set_z','15020',0.,unreal.Vector()))
        emit('exit');host.call_method('ProcessEditorEvents');settle_edits()
        check(location(target)[2]==15020 and get(host,'ConfirmMode')==1 and get(host,'Editing'),
              'Done waits for a preceding numeric commit and then offers to save it')
        command('confirm_cancel');command('undo');settle_edits();command('save');settle_edits()
        command('back')
        check(not get(host,'HasSelection') and get(host,'Editing') and get(host,'UIOpen')
              and comp.get_editor_property('render_custom_depth')
              and comp.get_editor_property('custom_depth_stencil_value')==7,
              'Escape deselects and restores existing outline without exiting')
        target.set_actor_hidden_in_game(True)
        rejected=picker.call_method('Classify',(host,comp,True,True,True))
        host.call_method('AcceptSelection',(rejected,))
        check(not get(host,'HasSelection') and 'visible static-mesh' in host.call_method('EditorFeedback'),
              'selection rejection explains why the object cannot be edited')
        target.set_actor_hidden_in_game(False)
        host.call_method('AcceptSelection',(facts,))
        host.call_method('DetachEditor',(False,))
        check(not get(host,'HasSelection') and comp.get_editor_property('custom_depth_stencil_value')==7,
              'editor teardown releases selection and restores stencil')
        # Reattach only the fixture bus/rig for the remaining headless routing tests.
        bus.call_method('Start');set_(host,'InputBus',bus);set_(host,'UIOpen',True)
        rig=spawn(RIG);set_(host,'EditorRig',rig)

        # Stored data has no world/async dependency, isolating command routing
        # through the real Session/History/Store implementations.
        row = fixture.call_method('MakeEntry', (1, 'stored1', unreal.Vector(1, 2, 3)))
        mutation = fixture.call_method('MakeMutation', (row, True))
        accepted = host.call_method('CommitEdit', ([mutation], 'Store fixture', ''))
        assert accepted[-1] if isinstance(accepted, tuple) else accepted
        drain(host)
        command('undo')
        drain(host)
        check(len(get(get(host, 'WorkingDocument'), 'Entries')) == 0,
              'native Undo button routes into session history')
        command('redo')
        drain(host)
        check(len(get(get(host, 'WorkingDocument'), 'Entries')) == 1,
              'native Redo button restores stored data')
        command('save')
        check(not get(host, 'History').call_method('IsDirty')
              and store.call_method('LoadLayout', (key, False, 0))[1] == 1,
              'native Save button writes the isolated layout and marks history clean')
        set_(host, 'LastStatus', 8)
        check('changed outside' in host.call_method('EditorFeedback'),
              'external-save conflict has visible, actionable feedback')
        set_(host, 'LastStatus', 1)
        set_(host, 'LastDraftStatus', 6)
        check('Draft autosave' in host.call_method('EditorFeedback'),
              'draft failure feedback remains visible after canonical success')
        set_(host, 'LastDraftStatus', 1)
        set_(host, 'PreferencesStatus', 6)
        check('Preferences' in host.call_method('EditorFeedback'), 'preference write failure has visible feedback without discarding layout edits')
        set_(host, 'PreferencesStatus', 1)
        command('back')
        check(not get(host, 'Editing') and not get(host, 'UIOpen')
              and not get(bus, 'Accepting') and get(host, 'EditorRig') is None,
              'clean exit stops input and releases native UI ownership')
    finally:
        for actor in reversed(spawned):
            if unreal.SystemLibrary.is_valid(actor):
                if actor == host:
                    fixture.call_method('SetSessionEditing', (actor, False))
                    actor.call_method('DetachEditor', (False,))
                    actor.call_method('CancelWork')
                    actor.call_method('Clear')
                actors.destroy_actor(actor)
        for path in paths:
            if path.exists():
                path.unlink()
        unreal.ZComAuthoringLibrary.force_delete_assets([spec['path']])
