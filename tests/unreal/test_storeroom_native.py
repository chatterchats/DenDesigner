"""Exercise native Storeroom providers and real world/history restore transactions."""
def run(unreal,host,bus,fixture,actor,facts,get,field,field_name,check,settle,command):
    history=get(host,'History');doc=get(host,'WorkingDocument')
    baseline_version=get(history,'Version');baseline_count=len(get(history,'UndoSteps'))
    original_pose=actor.get_actor_transform();max_retries=get(host,'MaxRetries')
    fixture.call_method('SetApplyMaxRetries',(host,0))
    mesh=unreal.load_asset('/Engine/BasicShapes/Cube').get_path_name()
    material=unreal.load_asset('/Engine/EngineDebugMaterials/VertexColorMaterial').get_path_name()
    def emit(name,arg=''):
        bus.call_method('Emit',(2,name,arg,0.,unreal.Vector()))
        host.call_method('ProcessEditorEvents');host.call_method('PumpEditorMutations');settle()
    def restore_without_selection_stall(name,arg=''):
        picker=get(host,'Picker');host.call_method('PollSelection')
        for _ in range(2000):
            if not get(picker,'Indexing'):break
            picker.call_method('PumpIndex')
        assert not get(picker,'Indexing')
        old_steps=get(picker,'MaxSteps')
        assert not unreal.ZComAuthoringLibrary.set_property_from_text(picker,'MaxSteps','1')
        try:
            emit(name,arg)
            check(not get(picker,'Indexing'),name+' refreshes restored props without scanning the entire Den')
        finally:
            assert not unreal.ZComAuthoringLibrary.set_property_from_text(picker,'MaxSteps',str(old_steps))
    def listing(query=None):
        if query is not None:emit('stored_search',query)
        for _ in range(1000):
            host.call_method('PollStoreroomUI')
            if not get(host,'StoreBuilding') and get(host,'StoreSeenVersion')==get(history,'Version'):return
        raise AssertionError('Storeroom listing did not finish')
    def rows():return list(get(doc,'Entries'))
    def lookup(key,kind):return next((x for x in rows() if field(x,'Key')==key and field(x,'Kind')==kind),None)
    def card(key,dormant=False):
        for index,item in zip(get(host,'DormantIndexes' if dormant else 'StoredIndexes'),get(host,'DormantRows' if dormant else 'StoredRows')):
            if field(rows()[index],'Key')==key:return get(item,'Key')
        raise AssertionError('Storeroom card missing: '+key)
    def commit(values):
        check(host.call_method('CommitEdit',([fixture.call_method('MakeMutation',(v,True)) for v in values],'Storeroom test','')),'Storeroom test fixture transaction accepted')
        settle()
    try:
        host.call_method('AcceptSelection',(facts,))
        host.call_method('SetSelectionField',('X','15080'));settle();command('store');settle()
        check(actor.get_editor_property('hidden'),'native Storeroom fixture is hidden in the actual world')
        stored=fixture.call_method('MakeEntry',(1,'storeroom_added',unreal.Vector(15020,15040,15060)))
        stored.set_editor_property(field_name('Mesh'),mesh)
        stored.set_editor_property(field_name('Materials'),[material])
        stored.set_editor_property(field_name('Scale'),unreal.Vector(2,3,4))
        missing=fixture.call_method('MakeEntry',(2,'/Game/DenNativeTests/MissingLevel.MissingLevel:PersistentLevel.MissingActor',unreal.Vector()))
        missing.set_editor_property(field_name('HasFingerprint'),False)
        missing.set_editor_property(field_name('Hidden'),True)
        commit([stored,missing]);host.call_method('SetEditorPanel',('storeroom',));listing()
        check(get(host,'StoreTotal')==2 and len(get(host,'StoredRows'))==2 and len(get(host,'DormantRows'))==1,
              'native listing distinguishes stored additions, bound hidden props, and unavailable edits')
        added_key=card('storeroom_added');native_key=card(actor.get_path_name());missing_key=field(missing,'Key')
        check(all(get(x,'AssetPath')==mesh for x in get(host,'StoredRows')),'real stored rows supply mesh paths for the shared thumbnail provider')
        before=get(history,'Version');listing('unmatchable_storeroom_query')
        check(len(get(host,'StoredRows'))==0 and get(host,'StoreTotal')==2 and len(get(host,'DormantRows'))==1,
              'search filters stored cards without hiding unavailable edits or changing restore-all scope')
        emit('restore',added_key)
        check(get(history,'Version')==before and lookup('storeroom_added',1) is not None,'obsolete card revision cannot restore a different layout entry')
        listing('');restore_without_selection_stall('restore',card('storeroom_added'));listing()
        value=lookup('storeroom_added',0)
        check(value is not None and lookup('storeroom_added',1) is None and get(host,'StoreTotal')==1,
              'restore atomically transfers an added prop from stored to placed')
        check(all(field(value,k)==field(stored,k) for k in ['Key','Mesh','Position','Rotation','Scale','CollisionMode','Source','FingerprintMesh']) and list(field(value,'Materials'))==[material],
              'restoration preserves exact pose, collision, materials, source, and identity')
        live=next(x for x in get(host,'Placed') if field(get(x,'Current'),'Key')=='storeroom_added')
        check(live.get_actor_location()==field(stored,'Position') and live.get_actor_scale3d()==field(stored,'Scale'),
              'restored prop is actually spawned at its stored transform')
        command('undo');settle();listing()
        check(lookup('storeroom_added',1) is not None and not unreal.SystemLibrary.is_valid(live),'undo restore returns the prop to storage and removes its actor')
        restore_without_selection_stall('restore',card(actor.get_path_name()));listing();native=lookup(actor.get_path_name(),2)
        check(not actor.get_editor_property('hidden') and native is not None and not field(native,'Hidden') and abs(actor.get_actor_location().x-15080)<.001,
              'restoring a hidden Den prop preserves its moved position override')
        command('undo');settle();listing();check(actor.get_editor_property('hidden'),'undo native restore hides the same prop again')
        listing('unmatchable_storeroom_query');undo_count=len(get(history,'UndoSteps'))
        restore_without_selection_stall('restore_all');listing()
        check(get(host,'StoreTotal')==0 and lookup('storeroom_added',0) is not None and not actor.get_editor_property('hidden') and lookup(missing_key,2) is not None,
              'Restore All restores filtered-out stored props while preserving unavailable entries')
        check(len(get(history,'UndoSteps'))==undo_count+1,'Restore All is one atomic history step')
        command('undo');settle();listing('');check(get(host,'StoreTotal')==2 and actor.get_editor_property('hidden'),'one undo reverses all restorations')
        emit('forget',card(missing_key,True));listing()
        check(lookup(missing_key,2) is None and get(host,'StoreTotal')==2 and len(get(host,'DormantRows'))==0,'forget removes only the chosen unavailable edit')
        command('undo');settle();listing();check(lookup(missing_key,2) is not None and len(get(host,'DormantRows'))==1,'undo forget recovers the unavailable entry')
        # Native data permits kind-specific identities. Restoring must not overwrite
        # an independently placed prop which happens to share a stored identity.
        conflict=fixture.call_method('MakeEntry',(0,'storeroom_added',unreal.Vector(16000,16000,16000)))
        conflict.set_editor_property(field_name('Mesh'),mesh);commit([conflict]);listing();before=get(history,'Version')
        emit('restore',card('storeroom_added'));listing()
        check(get(history,'Version')==before and lookup('storeroom_added',1) is not None and field(lookup('storeroom_added',0),'Position')==field(conflict,'Position'),
              'identity collision refuses restore without replacing either prop')
        emit('restore_all');listing()
        check(get(history,'Version')==before and actor.get_editor_property('hidden'),'Restore All aborts atomically on an identity conflict')
        command('undo');settle();listing()
        old_key=card('storeroom_added');host.call_method('SetEditorPanel',('',));before=get(history,'Version');emit('restore',old_key)
        check(get(history,'Version')==before and len(get(host,'StoredRows'))==0,'closed Storeroom clears rows and ignores late actions')
    finally:
        host.call_method('SetEditorPanel',('',))
        while len(get(history,'UndoSteps'))>baseline_count:command('undo');settle()
        fixture.call_method('SetApplyMaxRetries',(host,max_retries))
        host.call_method('ClearSelection')
    check(get(history,'Version')==baseline_version and actor.get_actor_transform()==original_pose and not actor.get_editor_property('hidden'),
          'Storeroom tests restore the original session and world without saving test edits')
