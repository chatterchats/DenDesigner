"""Real VM capture, isolated storage, preview, placement and atomic undo/redo."""
import uuid


def run(unreal,host,bus,target,facts,get,field,field_name,check,settle,command,set_,saved):
    from runtime_layout_ui import PRESETS
    from runtime import ROOT,ENTRY
    from runtime_compositions import LIMIT
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    key='test_compositions_'+uuid.uuid4().hex
    set_(host,'CompositionStorageKey',key)
    storage=unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(PRESETS))
    files=[saved/'SaveGames'/(storage.call_method('BankSlot',(key,i,False))+'.sav') for i in range(6)]
    assert all(not p.exists() and p.is_relative_to(saved/'SaveGames/ZComDen/Native/v1') for p in files)
    def emit(name,arg='',scalar=0.):
        bus.call_method('Emit',(2,name,arg,scalar,unreal.Vector()))
        host.call_method('ProcessEditorEvents');host.call_method('PumpEditorMutations')
    def rows(doc):return list(get(doc,'Entries'))
    def mutate(row,**values):
        row=row.copy()
        for name,value in values.items():row.set_editor_property(field_name(name),value)
        return row
    def rowdict(row):
        values={n:field(row,n) for n in ['Kind','Key','Mesh','Position','Rotation','Scale','HasPosition','HasRotation','HasScale','Hidden','CollisionMode','Source','HasFingerprint','FingerprintMesh','FingerprintPosition']}
        values['Materials']=list(field(row,'Materials'))
        return values
    def equal(a,b):return [rowdict(r) for r in a]==[rowdict(r) for r in b]
    def v(x,y,z):return unreal.Vector(x,y,z)
    def near(a,b):return (a-b).length()<.02
    def finish_preview():
        for _ in range(3000):
            preview=get(host,'CompositionPreview')
            if preview is None:return False
            preview.call_method('Pump')
            job=get(preview,'PendingJob')
            if job is not None and unreal.SystemLibrary.is_valid(job):job.call_method('ReceiveTick',(1/60,))
            unreal.ZComAuthoringLibrary.process_test_latent_actions(preview)
            host.call_method('PollCompositionPreview')
            if get(host,'CompositionPreviewReady'):return True
            if not get(host,'CompositionPlacing'):return False
        raise AssertionError('composition load did not finish')
    baseline=rows(get(host,'WorkingDocument'));history=get(host,'History');oldversion=get(history,'Version');oldsteps=len(get(history,'UndoSteps'))
    other=actors.spawn_actor_from_class(unreal.StaticMeshActor,v(30000,30000,30000),unreal.Rotator(),True)
    comp=other.static_mesh_component;comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    comp.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'));other.set_actor_scale3d(v(.5,1.25,2))
    original_target=target.get_actor_transform();other_pose=other.get_actor_transform()
    targetcomp=target.get_component_by_class(unreal.StaticMeshComponent)
    original_outline=(targetcomp.get_editor_property('render_custom_depth'),targetcomp.get_editor_property('custom_depth_stencil_value'))
    try:
        host.call_method('ClearSelection');host.call_method('RefreshActors');picker=get(host,'Picker')
        first=picker.call_method('Classify',(host,targetcomp,True,True,True));second=picker.call_method('Classify',(host,comp,True,True,True))
        emit('compositions');check(get(host,'ActivePanel')=='compositions','composition toolbar opens independent library panel')
        emit('composition_select');check(get(host,'CompositionSelecting'),'Select parts enters composition collection mode')
        for item in [first,second]:host.call_method('ConsumePointerSelection',(item,))
        check(len(get(host,'CompositionParts'))==2 and not get(host,'HasSelection'),'composition clicks collect multiple parts without arming normal drag')
        check(targetcomp.get_editor_property('custom_depth_stencil_value')==32 and comp.get_editor_property('custom_depth_stencil_value')==32,'all composition members receive selection outlines')
        host.call_method('ConsumePointerSelection',(second,));check(len(get(host,'CompositionParts'))==1,'clicking a member again removes it')
        host.call_method('ConsumePointerSelection',(second,))
        host.call_method('PollSelection')
        set_(picker,'QueryPending',False);set_(picker,'QueryResult',second);set_(picker,'QueryReady',True)
        host.call_method('PollSelection');check(len(get(host,'CompositionParts'))==1 and not get(picker,'QueryReady'),'completed group pick is acknowledged exactly once')
        for _ in range(10):host.call_method('PollSelection')
        check(len(get(host,'CompositionParts'))==1,'later frames do not toggle the last composition member again')
        host.call_method('ConsumePointerSelection',(second,))
        ready,document=host.call_method('CaptureComposition');check(ready and len(rows(document))==2,'capture creates a value-only composition document')
        parts=rows(document)
        check(get(document,'HasCompositionAnchor'),'capture retains its bottom-center anchor')
        capture_anchor=get(document,'CompositionAnchor')
        check(all(field(p,'Kind')==0 and not field(p,'HasFingerprint') and field(p,'Source')=='' for p in parts),'native sources become portable copies without level identities')
        check(near(field(parts[1],'Position')-field(parts[0],'Position'),other.get_actor_location()-target.get_actor_location()),'capture preserves relative world spacing')
        check(field(parts[1],'Scale')==other.get_actor_scale3d() and field(parts[0],'Rotation')==target.get_actor_rotation(),'capture preserves individual scale and rotation')
        check(len(field(parts[1],'Materials'))==comp.get_num_materials(),'capture includes the component material slots')
        check(target.get_actor_transform()==original_target and other.get_actor_transform()==other_pose and rows(get(host,'WorkingDocument'))==baseline and get(history,'Version')==oldversion,'capturing changes neither originals nor layout/history')
        # Reject invalid documents without creating a preview or touching the layout.
        cls=unreal.EditorAssetLibrary.load_blueprint_class(ROOT+'BP_DenLayoutSave')
        def doc(values):
            value=unreal.GameplayStatics.create_save_game_object(cls);set_(value,'Entries',values);return value
        for label,bad in [('empty',[]),('duplicate keys',[parts[0],parts[0]]),('vanilla',[mutate(parts[0],Kind=2)]),('hidden',[mutate(parts[0],Hidden=True)]),('negative scale',[mutate(parts[0],Scale=v(-1,1,1))]),('too many',[mutate(parts[0],Key=str(i)) for i in range(LIMIT+1)])]:
            check(not host.call_method('ValidateComposition',(doc(bad),)), 'composition validator rejects '+label)
        origin=v(40000,42000,44000)
        transformed,valid=host.call_method('TransformCompositionPart',(parts[1],origin,90.,2.))
        rel=field(parts[1],'Position');check(valid and near(field(transformed,'Position'),origin+v(-rel.y*2,rel.x*2,rel.z*2)) and near(field(transformed,'Scale'),field(parts[1],'Scale')*2),'group yaw and uniform scale transform every offset around its anchor')
        emit('save_composition','Test arrangement');service=get(host,'CompositionService')
        loaded,status=service.call_method('LoadPreset',('Test arrangement',));check(status==1 and equal(rows(loaded),parts),'named composition survives native storage round trip')
        check(get(loaded,'HasCompositionAnchor') and near(get(loaded,'CompositionAnchor'),capture_anchor),'composition anchor survives library save and reload')
        check(any(p.exists() for p in files),'compositions use their own isolated rotating save banks')
        import test_composition_thumbnails_native
        thumbnail_key=test_composition_thumbnails_native.run(unreal,host,document,get,field,check)
        check(get(get(host,'PresetService'),'LibraryKey')!=get(service,'LibraryKey') if get(host,'PresetService') else True,'composition storage does not share the preset library key')
        emit('save_composition','Test arrangement');check(get(host,'ConfirmMode')==5 and get(host,'PendingLayoutAction')=='replace_composition','saving an existing name requires explicit replacement')
        emit('confirm_cancel');check(equal(rows(service.call_method('LoadPreset',('Test arrangement',))[0]),parts),'cancelled replacement leaves saved composition intact')
        emit('save_composition','Test arrangement');emit('confirm_save');check(equal(rows(service.call_method('LoadPreset',('Test arrangement',))[0]),parts),'confirmed replacement preserves captured part values')
        check(get(list(get(host,'CompositionRows'))[0],'AssetPath')!=thumbnail_key,'replacing a composition invalidates its thumbnail cache key')
        emit('composition_clear');check(len(get(host,'CompositionParts'))==0 and not get(host,'CompositionSelecting'),'clear exits multi-selection')
        check(targetcomp.get_editor_property('render_custom_depth')==original_outline[0] and targetcomp.get_editor_property('custom_depth_stencil_value')==original_outline[1],'clearing members restores their previous outline state')
        host.call_method('RefreshCompositionLibrary');rev=get(host,'CompositionListRevision');emit('composition_card',str(rev)+':0');emit('load_composition')
        check(get(host,'CompositionPlacing') and not get(host,'CompositionPoseValid'),'choosing a saved composition starts a noncommittable loading preview')
        check(get(host,'RailAutoFold'),'placing a composition folds the rail')
        check(not host.call_method('CommitComposition',(False,)),'composition cannot be placed before all assets and a pose are ready')
        check(finish_preview(),'all composition assets load asynchronously')
        preview=get(host,'CompositionPreview');ghosts=list(get(preview,'Placed'));check(len(ghosts)==2 and all(p.get_component_by_class(unreal.StaticMeshComponent).get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION for p in ghosts),'every preview part has collision disabled')
        host.call_method('SetCompositionPreviewOrigin',(origin,));check(get(host,'CompositionPoseValid'),'complete composition preview accepts an anchor')
        emit('rotate',scalar=1.);emit('scale',scalar=1.);check(abs(get(host,'CompositionYaw')-15)<.001 and abs(get(host,'CompositionScale')-1.05)<.001,'existing rotate and scale input adjusts the whole composition')
        check(rows(get(host,'WorkingDocument'))==baseline and get(history,'Version')==oldversion,'moving the group preview does not write layout or history')
        command('back');check(not get(host,'CompositionPlacing') and all(not unreal.SystemLibrary.is_valid(p) for p in ghosts),'Escape removes every preview part')
        check(not get(host,'RailAutoFold'),'Escape gives the rail back its pin after a composition')
        check(host.call_method('StartCompositionPreview',(loaded,)) and finish_preview(),'saved composition can start another preview after cancellation')
        host.call_method('SetCompositionPreviewOrigin',(origin,));check(host.call_method('CommitComposition',(True,)),'a complete composition commits as one transaction')
        settle();firstplaced=rows(get(host,'WorkingDocument'));added=[row for row in firstplaced if row not in baseline]
        check(len(added)==2 and len(get(history,'UndoSteps'))==oldsteps+1,'all composition parts enter one undo step')
        check(get(host,'CompositionPlacing') and get(host,'RailAutoFold'),'repeat placement keeps the composition preview alive and the rail folded')
        host.call_method('SetCompositionPreviewOrigin',(origin+v(500,0,0),));check(host.call_method('CommitComposition',(False,)),'second composition copy can be placed independently')
        check(not get(host,'RailAutoFold'),'dropping a composition gives the rail back its pin')
        settle();check(len(rows(get(host,'WorkingDocument')))==len(baseline)+4 and len({field(row,'Key') for row in rows(get(host,'WorkingDocument')) if field(row,'Kind')==0})==len([row for row in rows(get(host,'WorkingDocument')) if field(row,'Kind')==0]),'repeated copies have distinct placed identities')
        command('undo');settle();check(equal(rows(get(host,'WorkingDocument')),firstplaced),'one undo removes the entire second composition only')
        command('redo');settle();check(len(rows(get(host,'WorkingDocument')))==len(baseline)+4,'one redo restores every part of the composition')
        command('undo');settle();command('undo');settle();check(rows(get(host,'WorkingDocument'))==baseline,'undo restores the exact pre-composition layout')
        missing=doc([parts[0],mutate(parts[1],Mesh='/Game/NoSuchCompositionMesh.NoSuchCompositionMesh')]);check(host.call_method('StartCompositionPreview',(missing,)),'missing asset is resolved asynchronously')
        check(not finish_preview() and rows(get(host,'WorkingDocument'))==baseline,'missing asset cancels composition without a partial layout write')
        check(not get(host,'RailAutoFold'),'a composition that fails to load unfolds the rail')
        host.call_method('SetEditorPanel',('compositions',));host.call_method('RefreshCompositionLibrary');rev=get(host,'CompositionListRevision');emit('composition_card',str(rev)+':0');emit('delete_composition');check(get(host,'ConfirmMode')==5,'composition deletion requires confirmation')
        emit('confirm_save');check(len(service.call_method('ListPresets')[0])==0,'confirmed delete removes only the named composition')
        import test_community_native
        test_community_native.run(unreal,host,document,get,field,check,saved,finish_preview,settle,command)
    finally:
        host.call_method('SetEditorConfirm',(0,));host.call_method('CancelCompositionPreview');host.call_method('ClearCompositionSelection');host.call_method('SetEditorPanel',('',))
        actors.destroy_actor(other)
        for path in files:
            if path.exists():path.unlink()
