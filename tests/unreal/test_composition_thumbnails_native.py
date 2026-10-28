"""Composition card snapshots, queue isolation, complete geometry and teardown."""
def run(unreal,host,document,get,field,check,name='Test arrangement'):
    from runtime_thumbnail_queue import QUEUE
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    expected_count=len(get(document,'Entries'))
    cards=list(get(host,'CompositionRows'));check(len(cards)==1,'composition browser creates one thumbnail card per saved arrangement')
    card=cards[0];key=get(card,'AssetPath');snapshot=get(card,'ThumbnailDocument')
    check(key.startswith('/ZComDen/CompositionThumbs/v1_') and key.endswith('.Composition') and snapshot is not None,'composition card owns a snapshot and a revision-specific cache key')
    detail=str(expected_count)+(' part' if expected_count==1 else ' parts')
    check(get(card,'Detail')==detail and get(card,'Title')==name,'composition cards show the saved name and part count')
    original=get(host,'WorkingDocument');version=get(get(host,'History'),'Version')
    worker=actors.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class(QUEUE),unreal.Vector(),unreal.Rotator(),transient=True)
    try:
        for _ in range(2):texture,status=worker.call_method('RequestComposition',(key,snapshot))
        check(texture is None and status==0 and list(get(worker,'PendingPaths'))==[key] and len(get(worker,'CacheDocuments'))==1,'visible composition requests deduplicate and retain their document')
        worker.call_method('BeginNext');renderer=get(worker,'CompositionRenderer');studio=get(worker,'Studio')
        check(renderer is not None and get(worker,'Phase')==4 and get(worker,'Job') is None,'composition thumbnail uses its own asynchronous group loader, not the synthetic path as an asset')
        for _ in range(3000):
            renderer.call_method('Pump');job=get(renderer,'PendingJob')
            if job is not None and unreal.SystemLibrary.is_valid(job):job.call_method('ReceiveTick',(1/60,))
            unreal.ZComAuthoringLibrary.process_test_latent_actions(renderer)
            if not get(renderer,'Busy'):break
        props=list(get(renderer,'Placed'));entries=list(get(snapshot,'Entries'))
        check(len(props)==len(entries)==expected_count and get(renderer,'ErrorCount')==0,'thumbnail loader completes every part and material before capture')
        check(all(get(p,'hidden') for p in props),'thumbnail parts remain hidden while awaiting studio staging')
        check(studio.call_method('StageComposition',(props,key)),'complete composition geometry stages without rendering in headless tests')
        origin=studio.get_actor_location()
        for actor,entry in zip(props,entries):
            pose=actor.get_actor_transform();mesh=get(actor,'Mesh')
            check((pose.translation-origin-field(entry,'Position')).length()<.02 and pose.scale3d==field(entry,'Scale'),'thumbnail staging preserves each part relative position and scale')
            check(mesh.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION and not mesh.get_editor_property('render_custom_depth'),'thumbnail actors have no collision or editor outlines')
            slots=list(field(entry,'Materials'))
            check(not slots or len(mesh.get_materials())==len(slots),'thumbnail retains declared material slots or the mesh defaults')
        bounds=[unreal.SystemLibrary.get_component_bounds(get(p,'Mesh')) for p in props]
        lo=[min(getattr(c,a)-getattr(e,a) for c,e,r in bounds) for a in ('x','y','z')]
        hi=[max(getattr(c,a)+getattr(e,a) for c,e,r in bounds) for a in ('x','y','z')]
        center=unreal.Vector(*[(a+b)/2 for a,b in zip(lo,hi)])-origin
        extent=unreal.Vector(*[(b-a)/2 for a,b in zip(lo,hi)])
        check((get(studio,'CompositionCenter')-center).length()<.02 and (get(studio,'CompositionExtent')-extent).length()<.02,'thumbnail camera frames union of all transformed part bounds')
        check(get(host,'WorkingDocument')==original and get(get(host,'History'),'Version')==version,'thumbnail work does not edit the layout or history')
        texture=unreal.new_object(unreal.Texture2D);worker.call_method('FinishThumbnail',(texture,))
        check(get(worker,'CompositionRenderer') is None and all(not unreal.SystemLibrary.is_valid(p) for p in props),'completed thumbnail destroys temporary group actors')
        result,status=worker.call_method('RequestComposition',(key,snapshot))
        check(result==texture and status==1 and not list(get(worker,'PendingPaths')),'composition thumbnail reuses the completed texture')
        worker.call_method('RequestComposition',(key.replace('v1_','v1_new_'),snapshot));worker.call_method('CancelPending')
        check(list(get(worker,'CachePaths'))==[key] and len(get(worker,'CacheDocuments'))==1 and not list(get(worker,'PendingPaths')),'cancel removes pending snapshot and key together without losing completed cache')
    finally:actors.destroy_actor(worker)
    return key
