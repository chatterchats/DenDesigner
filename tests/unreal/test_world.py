"""Exercise native world mutations on disposable actors in the kit's editor world."""
import os
from pathlib import Path


def run(unreal,root,fixture,field,field_name,check):
    saved=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())).resolve()
    assert saved==Path(os.environ['DENDESIGNER_TEST_SAVED']).resolve()
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    owned=[]
    mesh=unreal.EditorAssetLibrary.load_asset('/Engine/BasicShapes/Cube')
    material=unreal.EditorAssetLibrary.load_asset('/Engine/BasicShapes/BasicShapeMaterial')
    assert mesh is not None and material is not None
    prop_class=unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenPlacedProp')
    manager_class=unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenWorld')

    def spawn(cls=prop_class,xyz=(100,200,300)):
        actor=actors.spawn_actor_from_class(cls,unreal.Vector(*xyz),unreal.Rotator(),True)
        assert actor is not None
        owned.append(actor)
        return actor

    def entry(kind=0,key='test_prop',xyz=(101,202,303)):
        value=fixture.call_method('MakeEntry',(kind,key,unreal.Vector(*xyz)))
        value.set_editor_property(field_name('Mesh'),mesh.get_path_name())
        value.set_editor_property(field_name('Materials'),[])
        return value

    def change(value,**fields):
        for name,val in fields.items():value.set_editor_property(field_name(name),val)
        return value

    def xyz(value):return (round(value.x,4),round(value.y,4),round(value.z,4))
    def accepted(result):return result[-1] if isinstance(result,tuple) else result
    def configure(actor,value,mats=None,ghost=False):
        return accepted(actor.call_method('Configure',(value,mesh,mats or [],ghost)))
    def placed(value,mats=None,ghost=False):
        result=manager.call_method('SetPlaced',(value,mesh,mats or [],ghost))
        return result[-2],result[-1]
    def component(actor):return actor.get_component_by_class(unreal.StaticMeshComponent)
    def response(comp):return comp.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN).value
    def vanilla(key,value,present=True):return manager.call_method('SetVanilla',(key,value,present))

    manager=None
    try:
        manager=spawn(manager_class,(0,0,0))
        # Run real engine async loads. The helper only advances editor-world
        # latent callbacks; the cooked job uses Kismet's normal LoadAsset node.
        job_class=unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenAssetJob')
        job=spawn(job_class)
        for path in ['', 'not-an-asset', '/Game/Hub.Hub:PersistentLevel.Test', '/Game/'+('x'*1024)+'.Asset']:
            check(not job.call_method('Request',(path,)), 'async job rejects invalid/subobject request '+repr(path[:70]))
        check(job.call_method('Request',(mesh.get_path_name(),)), 'async job accepts an asset request')
        check(not job.call_method('Request',(material.get_path_name(),)), 'asset jobs cannot be repurposed while a result is pending')
        job.call_method('ReceiveTick',(1/60,))
        check(job.get_editor_property('Started') and not job.get_editor_property('Done'), 'asset load returns before its completion callback')
        check(unreal.ZComAuthoringLibrary.process_test_latent_actions(manager), 'headless test advances actual engine latent actions')
        check(job.get_editor_property('Done') and not job.get_editor_property('Failed') and job.get_editor_property('Result')==mesh, 'real async completion retains the loaded asset')
        job.call_method('FinishRequest',(None,))
        check(job.get_editor_property('Result')==mesh and not job.get_editor_property('Failed'), 'duplicate late completion cannot overwrite a finished job')
        missing_job=spawn(job_class)
        missing_job.call_method('Request',('/DenDesignerGF/Runtime/MissingFixture.MissingFixture',))
        missing_job.call_method('ReceiveTick',(1/60,))
        unreal.ZComAuthoringLibrary.process_test_latent_actions(manager)
        check(missing_job.get_editor_property('Done') and missing_job.get_editor_property('Failed') and missing_job.get_editor_property('Result') is None, 'missing async assets complete with an explicit failure')
        cancelled=spawn(job_class)
        cancelled.call_method('Request',(mesh.get_path_name(),))
        cancelled.call_method('ReceiveTick',(1/60,))
        actors.destroy_actor(cancelled)
        unreal.ZComAuthoringLibrary.process_test_latent_actions(manager)
        check(not unreal.SystemLibrary.is_valid(cancelled) and job.get_editor_property('Result')==mesh, 'destroying a pending job cancels its target without touching another job')
        actor=spawn()
        value=entry()
        check(configure(actor,value),'native placed actor accepts a loaded mesh and entry')
        comp=component(actor)
        check(xyz(actor.get_actor_location())==(101,202,303) and xyz(actor.get_actor_scale3d())==(1,2,3),'placed transform applies after the mesh root exists')
        check(response(comp)==0,'explicit non-solid props remain selectable while pawns pass through')
        change(value,CollisionMode=1)
        check(configure(actor,value) and response(comp)==2,'explicit solid mode blocks pawns')
        change(value,CollisionMode=0,Scale=unreal.Vector(.1,.1,.1))
        check(configure(actor,value) and response(comp)==0,'small automatic props do not block pawns')
        change(value,Scale=unreal.Vector(1,1,1))
        check(configure(actor,value) and response(comp)==2,'large automatic props block pawns')
        check(configure(actor,value,ghost=True) and comp.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION,'placement ghosts disable collision')
        check(configure(actor,value) and comp.get_collision_enabled()!=unreal.CollisionEnabled.NO_COLLISION,'committing a ghost restores its collision profile')
        override=unreal.load_asset('/Engine/EngineDebugMaterials/VertexColorMaterial')
        assert override is not None
        change(value,Materials=[override.get_path_name()])
        check(configure(actor,value,[override]) and comp.get_material(0)==override,'loaded material overrides reach the placed mesh')
        before_material=comp.get_material(0)
        check(not configure(actor,value,[]) and comp.get_material(0)==before_material, 'incomplete material results cannot partially overwrite a prop')
        check(not configure(actor,value,[material]) and comp.get_material(0)==before_material, 'mismatched material results are rejected before mutation')
        change(value,Materials=[])
        check(configure(actor,value,[]) and comp.get_material(0)==mesh.get_material(0),'removing an override restores the mesh default material')
        prior=actor.get_actor_transform()
        bad=entry(xyz=(999,888,777));change(bad,Scale=unreal.Vector(1,0,1))
        check(not configure(actor,bad) and actor.get_actor_transform()==prior,'invalid placed transforms leave the existing actor untouched')
        bad=entry();change(bad,Mesh='/Game/NotTheLoadedMesh.NotTheLoadedMesh')
        check(not configure(actor,bad),'stale asset completion cannot apply a mesh for another entry path')
        check(not accepted(actor.call_method('Configure',(value,None,[],False))),'missing loaded mesh is rejected')
        change(value,Position=unreal.Vector(7,8,9),Scale=unreal.Vector(2,3,4))
        check(actor.call_method('PreviewTransform',(value,)) and xyz(actor.get_actor_location())==(7,8,9),'transform preview operates without asset loading')

        first,status=placed(entry(key='managed'))
        check(status==1 and first is not None,'world manager spawns a placed prop')
        again,status=placed(entry(key='managed',xyz=(400,500,600)))
        check(status==1 and again==first and len(manager.get_editor_property('Placed'))==1,'updating a placed identity reuses its actor')
        check(xyz(first.get_actor_location())==(400,500,600),'world manager updates the reused actor transform')
        manager.call_method('RemovePlaced',('managed',))
        check(len(manager.get_editor_property('Placed'))==0 and not unreal.SystemLibrary.is_valid(first),'storing a placed prop destroys its live actor')
        restored,status=placed(entry(key='managed'))
        check(status==1 and restored!=first,'restoring a stored identity creates its live actor again')
        manager.call_method('RemovePlaced',('missing',))
        check(len(manager.get_editor_property('Placed'))==1,'removing an absent placed identity is a no-op')

        # Snapshot a static native component, then apply partial transforms.
        target=spawn(xyz=(10,20,30));tc=component(target)
        tc.set_static_mesh(mesh)
        tc.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
        tc.set_mobility(unreal.ComponentMobility.STATIC)
        manager.call_method('RefreshActors')
        key=target.get_path_name()
        check(manager.call_method('ResolveKey',(key,))==target and manager.call_method('ResolveKey',(tc.get_path_name(),))==tc,'native resolver finds exact actor and component paths in this world')
        check(manager.call_method('ResolveKey',(key+'_missing',)) is None,'missing paths resolve without loading another level')
        edit=entry(2,key,xyz=(40,50,60));change(edit,HasRotation=False,HasScale=False)
        check(vanilla(key,edit)==1 and xyz(target.get_actor_location())==(40,50,60),'native actor position edit applies')
        check(xyz(target.get_actor_scale3d())==(1,1,1) and tc.get_editor_property('mobility')==unreal.ComponentMobility.MOVABLE,'partial vanilla edit preserves original scale and enables mobility')
        edit2=entry(2,key);change(edit2,HasPosition=False,HasRotation=False,HasScale=True,Scale=unreal.Vector(2,2,2),Hidden=True)
        check(vanilla(key,edit2)==1 and xyz(target.get_actor_location())==(10,20,30),'replacing a partial edit restores omitted fields from the snapshot')
        check(target.get_editor_property('hidden') and not target.get_actor_enable_collision(),'storing a native actor hides it and disables collision')
        check(vanilla(key,edit2,False)==1,'removing a native actor edit restores its snapshot')
        check(xyz(target.get_actor_location())==(10,20,30) and xyz(target.get_actor_scale3d())==(1,1,1),'native actor transform restored exactly')
        check(not target.get_editor_property('hidden') and target.get_actor_enable_collision() and tc.get_editor_property('mobility')==unreal.ComponentMobility.STATIC,'native actor visibility, collision and mobility restored')
        check(len(manager.get_editor_property('Records'))==1,'repeated edits retain one original snapshot')
        missing=entry(2,key+'_missing')
        check(vanilla(key+'_missing',missing)==2,'unloaded native entries are reported as dormant')
        check(vanilla(key+'_missing',missing,False)==1,'removing an unapplied dormant edit is harmless')

        other=spawn(xyz=(-10,-20,-30));oc=component(other);oc.set_static_mesh(mesh)
        oc.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
        manager.call_method('RefreshActors')
        ckey=oc.get_path_name();cedit=entry(2,ckey)
        change(cedit,HasPosition=False,HasRotation=False,HasScale=False,Hidden=True)
        check(vanilla(ckey,cedit)==1 and not oc.is_visible() and oc.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION,'storing a component hides only that component and disables its collision')
        check(vanilla(ckey,cedit,False)==1 and oc.is_visible() and oc.get_collision_enabled()==unreal.CollisionEnabled.QUERY_ONLY,'component restoration preserves its original collision mode')
        hidden=spawn();hc=component(hidden);hc.set_static_mesh(mesh);hidden.set_actor_hidden_in_game(True)
        manager.call_method('RefreshActors')
        hkey=hidden.get_path_name();hedit=entry(2,hkey)
        change(hedit,HasPosition=False,HasRotation=False,HasScale=False,Hidden=True)
        check(vanilla(hkey,hedit)==1 and vanilla(hkey,hedit,False)==1 and hidden.get_editor_property('hidden') and hidden.get_actor_enable_collision(),'restoration keeps pre-hidden actors hidden and restores their collision')
        recovered=spawn(xyz=(31,32,33));recovered.get_component_by_class(unreal.StaticMeshComponent).set_static_mesh(mesh)
        manager.call_method('RefreshActors')
        alias='/Game/OldHub.OldHub:PersistentLevel.RenamedProp'
        check(manager.call_method('BindVanilla',(alias,recovered)), 'recovered layout identity binds a current-world object')
        aliasedit=entry(2,alias,xyz=(41,42,43))
        check(vanilla(alias,aliasedit)==1 and xyz(recovered.get_actor_location())==(41,42,43), 'aliased layout key edits the recovered object while retaining its actual path')
        check(not manager.call_method('BindVanilla',(alias,target)), 'a recovered identity cannot silently rebind to a different live object')
        check(vanilla(alias,aliasedit,False)==1 and xyz(recovered.get_actor_location())==(31,32,33), 'aliased native undo restores the recovered object baseline')
        vanilla(key,edit)
        manager.call_method('Clear')
        check(xyz(target.get_actor_location())==(10,20,30) and not unreal.SystemLibrary.is_valid(restored),'clearing a live layout restores vanilla edits and destroys its placed actors')
        check(len(manager.get_editor_property('Records'))==0 and len(manager.get_editor_property('Placed'))==0,'clear releases transient bindings')
        check(manager.call_method('ResolveKey',(key,)) is None,'world membership is required even if a soft object path resolves')
    finally:
        if manager is not None and unreal.SystemLibrary.is_valid(manager):manager.call_method('Clear')
        for actor in reversed(owned):
            if unreal.SystemLibrary.is_valid(actor):actors.destroy_actor(actor)
