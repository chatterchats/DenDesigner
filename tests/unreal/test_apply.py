"""Execute the real Blueprint queue and latent loads in a disposable editor world."""
import unreal


def run(unreal,root,fixture,field,field_name,check):
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    owned=[]
    cls=unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenApply')
    layout_cls=unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenLayoutSave')
    mesh=unreal.load_asset('/Engine/BasicShapes/Cube')
    material=unreal.load_asset('/Engine/EngineDebugMaterials/VertexColorMaterial')

    def spawn(klass,xyz=(0,0,0)):
        actor=actors.spawn_actor_from_class(klass,unreal.Vector(*xyz),unreal.Rotator(),transient=True)
        owned.append(actor)
        return actor

    manager=spawn(cls)
    def get(name):return manager.get_editor_property(name)
    def set_(name,value):fixture.call_method('SetApply'+name,(manager,value))
    def accepted(result):return result[-1] if isinstance(result,tuple) else result
    def xyz(value):return tuple(round(getattr(value,k),4) for k in ['x','y','z'])
    def entry(key,kind=0,pos=(10,20,30),**kwargs):
        value=fixture.call_method('MakeEntry',(kind,key,unreal.Vector(*pos)))
        for k,v in dict(Mesh=mesh.get_path_name(),Materials=[],HasFingerprint=False,**kwargs).items():
            value.set_editor_property(field_name(k),v)
        return value
    def mutation(value,present=True):return fixture.call_method('MakeMutation',(value,present))
    def batch(values,replace=False):return accepted(manager.call_method('BeginBatch',(values,replace)))
    def document(values):
        doc=unreal.GameplayStatics.create_save_game_object(layout_cls)
        for value in values:assert doc.call_method('WriteEntry',(value,True))
        return doc
    def begin(values):return manager.call_method('BeginLayout',(document(values),))
    def prop(key):
        i=manager.call_method('FindPlaced',(key,))
        return get('Placed')[i] if i>=0 else None
    def tick(load=True):
        manager.call_method('Pump')
        job=get('PendingJob')
        if load and job is not None and unreal.SystemLibrary.is_valid(job):
            job.call_method('ReceiveTick',(1/60,))
            unreal.ZComAuthoringLibrary.process_test_latent_actions(manager)
    def drain(limit=300):
        for _ in range(limit):
            if not get('Busy'):return
            tick()
        raise AssertionError('apply queue did not complete; phase='+str(get('Phase')))
    try:
        set_('RetryInterval',0.0);set_('MaxRetries',2)
        a=entry('placed-a');b=entry('placed-b')
        b.set_editor_property(field_name('Materials'),['',material.get_path_name()])
        stored=entry('stored-only',1)
        target=spawn(unreal.StaticMeshActor,(100,200,300))
        target.static_mesh_component.set_static_mesh(mesh)
        key=target.get_path_name()
        native=entry(key,2,(110,220,330),Hidden=True)
        check(begin([a,b,stored,native]),'full layout is accepted by the native apply queue')
        check(not batch([mutation(a)]),'incremental edits cannot replace an in-flight apply batch')
        drain()
        check(len(get('Placed'))==2 and prop('stored-only') is None,'queued layout creates placed props and leaves stored entries out of the world')
        check(prop('placed-b').get_component_by_class(unreal.StaticMeshComponent).get_material(1)==material,'queued async material loads preserve empty default slots')
        check(target.get_editor_property('hidden') and xyz(target.get_actor_location())==(110,220,330),'queue applies vanilla visibility and transforms')
        check(get('PlacedCount')==2 and get('HiddenCount')==1 and get('MovedCount')==1 and len(get('Issues'))==0,'queue reports applied native and placed changes')
        check(get('Frames')>0 and get('WorkSeconds')>=get('SlowestStep')>=0 and get('TotalSeconds')>0,'queue measures work and elapsed time using an advancing wall clock')
        first=prop('placed-a')
        moved=entry('placed-a',pos=(70,80,90))
        check(batch([mutation(moved)]) ,'idle queue accepts incremental mutations')
        drain()
        check(prop('placed-a')==first and xyz(first.get_actor_location())==(70,80,90),'incremental transform commit preserves actor identity')
        check(len(get('Records'))==1 and target.get_editor_property('hidden'),'incremental batch preserves unrelated vanilla bindings and visibility')
        check(batch([mutation(moved,False),mutation(entry('placed-a',1))]),'storing a placed prop accepts the paired history mutations')
        drain()
        check(prop('placed-a') is None and len(get('Placed'))==1,'store mutation removes only the selected placed actor')
        check(batch([mutation(entry('placed-a',1),False),mutation(moved)]),'restore accepts the inverse store mutations')
        drain()
        check(prop('placed-a') is not None and xyz(prop('placed-a').get_actor_location())==(70,80,90),'restore recreates the stored prop with its transform')
        check(batch([mutation(native,False)]),'native undo mutation accepted')
        drain()
        check(xyz(target.get_actor_location())==(100,200,300) and not target.get_editor_property('hidden'),'queued native undo restores the original snapshot')

        # Work limit covers cleanup too; replacing a full layout cannot destroy
        # all existing objects inside the UI event that submitted it.
        set_('MaxSteps',1)
        before=list(get('Placed'))
        check(begin([]) and len(get('Placed'))==2,'full replacement defers old-world cleanup until Pump')
        tick()
        check(len(get('Placed'))==1 and get('Busy'),'one-step budget destroys at most one old prop per pump')
        drain()
        check(all(not unreal.SystemLibrary.is_valid(p) for p in before) and len(get('Records'))==0,'full cleanup releases placed actors and native snapshots')
        set_('MaxSteps',32)

        # Cancel an actual outstanding latent load, then consume a different
        # generation. The old callback must not create either old prop.
        set_('MaxSteps',1)
        check(begin([a,b]),'cancellation fixture starts')
        for _ in range(20):
            tick(load=False)
            if get('PendingJob') is not None:break
        abandoned=get('PendingJob');assert abandoned is not None
        abandoned.call_method('ReceiveTick',(1/60,))
        generation=get('Generation')
        check(begin([entry('replacement')]) and get('Generation')>generation,'new full layout supersedes an outstanding asset request')
        check(not unreal.SystemLibrary.is_valid(abandoned),'superseded asset job is destroyed before its callback')
        unreal.ZComAuthoringLibrary.process_test_latent_actions(manager)
        set_('MaxSteps',32);drain()
        check(len(get('Placed'))==1 and prop('replacement') is not None and prop('placed-a') is None,'cancelled async results cannot leak into the new layout')

        bad=entry('bad');bad.set_editor_property(field_name('Mesh'),'/DenDesignerGF/Runtime/AbsentFixture.AbsentFixture')
        wrong=entry('wrong-type');wrong.set_editor_property(field_name('Mesh'),material.get_path_name())
        check(begin([bad,wrong,a]),'mixed asset failure fixture starts');drain()
        check(get('ErrorCount')==2 and get('PlacedCount')==1 and prop('placed-a') is not None,'missing or wrong-class assets are reported and do not stop later entries')
        assert batch([mutation(entry('timeout'))])
        set_('AssetTimeout',0.0)
        for _ in range(30):
            if not get('Busy'):break
            tick(load=False)
        check(not get('Busy') and get('ErrorCount')==1 and get('PendingJob') is None and prop('timeout') is None,'stalled async load times out and releases its job without creating a prop')
        set_('AssetTimeout',30.0)

        late=spawn(unreal.StaticMeshActor,(500,600,700));late.static_mesh_component.set_static_mesh(mesh)
        latekey=late.get_path_name();lateedit=entry(latekey,2,(510,620,730))
        assert batch([mutation(lateedit)])
        # Simulate a component's level not yet being a member of the active world.
        set_('WorldActors',[])
        tick()
        drain()
        check(xyz(late.get_actor_location())==(510,620,730) and get('RetryPass')>=1 and get('DormantCount')==0,'retry refresh discovers a late world member and applies its edit')
        missing=entry(latekey+'_unloaded',2)
        assert begin([missing]);drain()
        check(get('RetryPass')==2 and get('DormantCount')==1 and get('ErrorCount')==0,'unresolved native entries become dormant after the configured retry limit')
        check(field(fixture.call_method('ReadApplyIssue',(manager,0))[0],'Key')==latekey+'_unloaded','dormant report retains the complete original layout entry')
        set_('MaxRetries',0)
        recovered=spawn(unreal.StaticMeshActor,(8000,6000,4000));recovered.static_mesh_component.set_static_mesh(mesh)
        oldkey='/Game/OldHub.OldHub:PersistentLevel.OldFixture'
        recover=entry(oldkey,2,(8010,6020,4030))
        recover.set_editor_property(field_name('HasFingerprint'),True)
        recover.set_editor_property(field_name('FingerprintMesh'),mesh.get_path_name())
        recover.set_editor_property(field_name('FingerprintPosition'),unreal.Vector(8000,6000,4000))
        assert begin([recover]);drain()
        check(get('RefoundCount')==1 and get('DormantCount')==0 and xyz(recovered.get_actor_location())==(8010,6020,4030),'unique mesh and original position recover a stale actor path')
        check(batch([mutation(recover,False)]),'recovered actor can be removed using the saved layout identity');drain()
        check(xyz(recovered.get_actor_location())==(8000,6000,4000),'recovered identity restores the original actor on undo')
        recover_component=entry(oldkey+'.OldComponent',2,(8050,6060,4070))
        for name in ['HasFingerprint','FingerprintMesh','FingerprintPosition']:
            recover_component.set_editor_property(field_name(name),field(recover,name))
        assert begin([recover_component]);drain()
        check(get('RefoundCount')==1 and xyz(recovered.get_actor_location())==(8050,6060,4070),'component identity recovers the matching component rather than its actor')
        assert begin([]);drain()
        invalid_recover=entry(oldkey,2,(9990,9990,9990))
        for name in ['HasFingerprint','FingerprintMesh','FingerprintPosition']:
            invalid_recover.set_editor_property(field_name(name),field(recover,name))
        invalid_recover.set_editor_property(field_name('Scale'),unreal.Vector(0,1,1))
        assert begin([invalid_recover]);drain()
        check(get('ErrorCount')==1 and get('DormantCount')==0 and fixture.call_method('ReadApplyIssue',(manager,0))[1]==3 and xyz(recovered.get_actor_location())==(8000,6000,4000),'recovered object with an invalid edit reports an error without changing its baseline')
        assert begin([]);drain()
        second=spawn(unreal.StaticMeshActor,(8000,6000,4000));second.static_mesh_component.set_static_mesh(mesh)
        assert begin([recover]);drain()
        check(get('DormantCount')==1 and get('RefoundCount')==0 and xyz(recovered.get_actor_location())==(8000,6000,4000) and xyz(second.get_actor_location())==(8000,6000,4000),'ambiguous fingerprint leaves every candidate unchanged and reports the entry dormant')
        recover.set_editor_property(field_name('FingerprintPosition'),unreal.Vector(8003,6000,4000))
        assert begin([recover]);drain()
        check(get('DormantCount')==1 and get('RefoundCount')==0,'fingerprint recovery enforces the two-centimetre positional tolerance')
        check(batch([]),'empty incremental batch accepted');drain()
        check(not get('Busy'),'empty incremental work completes')
        check(batch([mutation(missing),mutation(missing,False)]),'repeated native identity accepts a later removal');drain()
        check(get('DormantCount')==0 and get('RetryPass')==0 and len(get('Issues'))==0,'later removal cancels an earlier unresolved edit in the same batch')
        assert begin([a,b]);drain()
        surviving=prop('placed-a')
        future=document([]);fixture.call_method('SetSchemaVersion',(future,2))
        check(not manager.call_method('BeginLayout',(future,)) and prop('placed-a')==surviving,'future schema is rejected without clearing the active world')
        disabled=document([a]);fixture.call_method('SetEnabled',(disabled,False))
        check(manager.call_method('BeginLayout',(disabled,)),'inactive layout can clear the active world');drain()
        check(len(get('Placed'))==0,'inactive layout never spawns its retained entries')
        assert begin([a,b]);drain()
        set_('BudgetSeconds',0.0)
        assert begin([])
        tick()
        check(len(get('Placed'))==1 and get('Busy'),'elapsed-time budget independently bounds cleanup even with a larger step limit')
        drain();set_('BudgetSeconds',0.004)
        manager.call_method('ConsumeIndexChanges');index_base=get('Generation')
        assert batch([mutation(a)]);drain()
        assert batch([mutation(b)]);drain()
        index_keys=[fixture.call_method('ReadIndexChangeKey',(manager,i)) for i in range(len(get('IndexMutations')))]
        check(get('IndexDeltaValid') and get('IndexFromGeneration')==index_base
              and get('IndexThroughGeneration')==get('Generation') and index_keys==['placed-a','placed-b'],
              'unconsumed consecutive incremental batches retain every changed identity and their generation range')
        manager.call_method('ConsumeIndexChanges')
        check(not get('IndexDeltaValid') and not get('IndexMutations'),'selection consumes completed index changes without retaining old identities')
        assert begin([]);drain()
        check(not get('IndexDeltaValid') and not get('IndexMutations'),'whole-layout replacement invalidates incremental index reuse')
        check(not manager.call_method('BeginLayout',(None,)),'missing layout document rejected')
    finally:
        if unreal.SystemLibrary.is_valid(manager):
            manager.call_method('CancelWork');manager.call_method('Clear')
        for actor in reversed(owned):
            if unreal.SystemLibrary.is_valid(actor):actors.destroy_actor(actor)
