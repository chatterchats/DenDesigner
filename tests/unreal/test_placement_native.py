"""Catalog card validation, actual async load, collisionless preview and transactions."""
def run(unreal,host,bus,get,field,check,settle,command,set_):
    from runtime_catalog_ui import DEFAULT_SHELF
    host.call_method('InitializeEditorGizmo')
    host.call_method('ClearSelection')
    host.call_method('SetEditorPanel',('catalog',))
    provider=get(host,'CatalogProvider');data=get(provider,'Data')
    paths=list(get(data,'Paths'));original_paths=paths[:]
    index=list(get(data,'ShelfStarts'))[DEFAULT_SHELF-1]
    mesh=unreal.load_asset('/Engine/BasicShapes/Cube')
    # Give the provider one actual engine asset to test; never modify cooked CDO data.
    paths[index]=mesh.get_path_name();set_(data,'Paths',paths)
    history=get(host,'History');version=get(history,'Version');next_version=get(history,'NextVersion');undo_count=len(get(history,'UndoSteps'));doc=get(host,'WorkingDocument')
    baseline=list(get(doc,'Entries'))
    def start():
        host.call_method('SetEditorPanel',('catalog',))
        provider.call_method('Browse',(DEFAULT_SHELF,))
        while get(provider,'Active'):provider.call_method('Pump')
        return str(get(provider,'Revision'))+':'+str(index)
    def emit(name,arg='',scalar=0.):
        bus.call_method('Emit',(2,name,arg,scalar,unreal.Vector()))
        host.call_method('ProcessEditorEvents')
    def load():
        for _ in range(1000):
            job=get(host,'PlacementJob')
            if job is not None and unreal.SystemLibrary.is_valid(job):job.call_method('ReceiveTick',(1/60,))
            unreal.ZComAuthoringLibrary.process_test_latent_actions(host)
            host.call_method('PollPlacement')
            if get(host,'PlacementGhost') is not None:return get(host,'PlacementGhost')
            if not get(host,'PlacementActive'):raise AssertionError('placement cancelled while loading')
        raise AssertionError('placement did not load')
    def pose():host.call_method('UpdatePlacementRay',(unreal.Vector(30000,30000,30000),unreal.Vector(1,0,0)))
    def unchanged(label):check(get(get(host,'History'),'Version')==version and len(get(doc,'Entries'))==len(baseline),label)
    try:
        key=start()
        for invalid in ['bad','0:'+str(index),key+'x','0'+key,str(get(provider,'Revision'))+':999999']:
            emit('item',invalid)
        check(not get(host,'PlacementActive'),'malformed stale and undisplayed catalog cards cannot start placement')
        emit('item',key);job=get(host,'PlacementJob')
        check(get(host,'PlacementActive') and job is not None and get(host,'ActivePanel')=='',
              'valid card closes catalog and owns one asynchronous asset job')
        check(get(host,'RailAutoFold') and get(host,'RailLabels'),'placing folds the rail without changing its pin')
        unchanged('choosing a catalog card changes no layout or history')
        check(not host.call_method('CommitPlacement',(False,)), 'click before preview pose cannot create a prop')
        command('back')
        check(not get(host,'PlacementActive') and get(host,'PlacementJob') is None and not unreal.SystemLibrary.is_valid(job),
              'Escape during loading destroys the latent callback target without closing editor')
        check(get(host,'UIOpen'),'cancelling pending placement leaves editor open')
        check(not get(host,'RailAutoFold'),'Escape gives the rail back its pin')
        emit('item',start());ghost=load()
        comp=ghost.get_component_by_class(unreal.StaticMeshComponent)
        check(comp.static_mesh==mesh and comp.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION,
              'completed asynchronous request creates the correct collisionless preview')
        check(get(host,'PlacementJob') is None and get(host,'PlacementMesh')==mesh,
              'preview owns its loaded mesh and releases its completed job')
        check(not get(host,'PlacementPoseValid'),'new preview cannot commit an unpositioned origin prop')
        pose();before=get(host,'PlacementEntry');before_yaw=float(field(before,'Rotation').yaw)
        check(get(host,'PlacementPoseValid') and (field(before,'Position')-unreal.Vector(30300,30000,30050)).length()<.002,
              'no-hit preview is three metres ahead with its bottom at the cursor anchor')
        emit('rotate',scalar=1.);emit('scale',scalar=1.);pose();value=get(host,'PlacementEntry')
        check(abs(field(value,'Rotation').yaw-before_yaw-15)<.002 and abs(field(value,'Scale').x-1.05)<.002,
              f'preview wheel rotation and scale use native input routing without history edits (yaw {before_yaw} -> {field(value,"Rotation").yaw}, scale {field(value,"Scale").x})')
        unchanged('preview transforms remain outside history')
        check(host.call_method('CommitPlacement',(True,)),'Shift-style placement accepts one transaction and retains preview')
        settle();check(get(host,'PlacementActive') and get(host,'PlacementGhost')==ghost,'repeat placement keeps the same ghost after world apply')
        check(get(host,'RailAutoFold'),'the rail stays folded while Shift-click keeps placing')
        rows=[r for r in get(doc,'Entries') if field(r,'Key') not in [field(x,'Key') for x in baseline]]
        check(len(rows)==1 and field(rows[0],'Key')!='preview' and field(rows[0],'Position')==field(value,'Position') and field(rows[0],'Scale')==field(value,'Scale'),
              'placement commits a fresh stable identity and exact preview pose')
        check(index in list(get(provider,'Recent')),'accepted placement remembers the catalog item')
        preferences,status=get(host,'PreferenceService').call_method('OpenPreferences')
        check(status==1 and list(preferences.call_method('RecentMeshes'))[0]==mesh.get_path_name(),
              'accepted placement persists its asset path in isolated preferences')
        check(host.call_method('CommitPlacement',(False,)),'normal placement commits another independent instance')
        settle();check(not get(host,'PlacementActive') and get(host,'PlacementGhost') is None and not unreal.SystemLibrary.is_valid(ghost),
              'normal placement destroys its transient ghost and releases preview ownership')
        check(not get(host,'RailAutoFold'),'a drop gives the rail back its pin')
        check(get(host,'HasSelection') and field(get(host,'Selected'),'Kind',__import__('runtime_pick').FACT)==0,'normal placement selects the newly applied managed prop')
        check(get(history,'Version')==next_version+2 and len(get(history,'UndoSteps'))==undo_count+2,'each placement creates exactly one history step')
        command('undo');settle();check(not get(host,'HasSelection') and get(host,'SelectionMessage')=='','undoing the selected placement quietly clears its selection')
        command('undo');settle();unchanged('undoing both placements restores the prior layout')
        command('redo');settle();check(get(history,'Version')==next_version+1,'placement redo recreates the prop through normal async apply')
        command('undo');settle()
        emit('item',start());pending=get(host,'PlacementJob');host.call_method('SetEditorPanel',('storeroom',))
        check(not get(host,'PlacementActive') and not unreal.SystemLibrary.is_valid(pending),'opening another panel cancels a pending placement load')
        emit('item',start());host.call_method('CancelPlacement');unreal.ZComAuthoringLibrary.process_test_latent_actions(host);host.call_method('PollPlacement')
        check(get(host,'PlacementGhost') is None,'cancelled load cannot publish a late preview')
        unchanged('catalog placement cancellation leaves no layout entries')
    finally:
        host.call_method('CancelPlacement');host.call_method('SetEditorPanel',('',))
        set_(data,'Paths',original_paths)
        host.call_method('DestroyEditorGizmo')
