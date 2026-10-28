"""Exercise the actual native picker VM on disposable kit actors."""
import os
from pathlib import Path


def run(unreal, root, fixture, field, field_name, check):
    saved = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())).resolve()
    assert saved == Path(os.environ['DENDESIGNER_TEST_SAVED']).resolve()
    picker = unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenPicker'))
    def rules(**overrides):
        args = dict(MeshPath='/Game/Props/Chair.Chair', LevelPath='/Game/Hub/Environment.Room', Size=100.,
                    Managed=False, Pawn=False, Foreign=False, Interactive=False, Instanced=False,
                    EditStructure=False, SelectFloors=True, SelectWalls=False)
        args.update(overrides)
        return picker.call_method('CheckRules', tuple(args.values()))
    check(rules()[0], 'picker permits an ordinary furniture mesh')
    for key in ['Pawn','Foreign','Interactive','Instanced']:
        allowed, reason = rules(**{key:True})
        check(not allowed and bool(reason), 'picker explains rejection of '+key)
    check(not rules(LevelPath='/Game/Hub/HUB_Gameplay.HUB_Gameplay')[0], 'picker protects gameplay sublevels')
    check(not rules(Size=801.)[0] and rules(Size=801.,EditStructure=True)[0], 'structure toggle gates oversized scenery')
    floor='/Game/Environment/HQ/Structure/Floors/Floor.Floor'
    check(not rules(MeshPath=floor,Managed=True,SelectFloors=False)[0], 'floor toggle also protects managed floor props')
    check(rules(MeshPath=floor,Managed=True)[0], 'managed floor remains selectable when floors are enabled')
    # Each category owns its gate, including meshes over the structure size limit.
    pit='/Game/Game/Environments/Strategy/HQ/Structure/Floors/Pit/SM_HUB_PitPlaneA.SM_HUB_PitPlaneA'
    wallpath='/Game/Game/Environments/Strategy/HQ/Structure/Walls/SM_Hub_Wall_A.SM_Hub_Wall_A'
    ceiling='/Game/Game/Environments/Strategy/HQ/Structure/Ceilings/SM_Ceiling.SM_Ceiling'
    for structure in [False,True]:
        for floors in [False,True]:
            for walls in [False,True]:
                switches=dict(EditStructure=structure,SelectFloors=floors,SelectWalls=walls)
                label=f' (structure={structure}, floors={floors}, walls={walls})'
                check(rules(MeshPath=pit,Size=4953.,**switches)[0]==floors,'Pit Plane A depends only on Floors'+label)
                check(rules(MeshPath=wallpath,Size=2000.,**switches)[0]==walls,'wall depends only on Walls'+label)
                check(rules(MeshPath=ceiling,**switches)[0]==structure,'ceiling depends only on Structure'+label)
                check(rules(**switches)[0],'ordinary prop ignores architecture filters'+label)
    for managed in [False,True]:
        check(not rules(MeshPath=wallpath,Managed=managed,EditStructure=True)[0], 'disabled wall category includes placed copies '+str(managed))
        check(rules(MeshPath=wallpath,Managed=managed,SelectWalls=True)[0], 'enabled wall category includes placed copies '+str(managed))
    for path in [pit,wallpath]:
        for flag in ['Pawn','Foreign','Interactive','Instanced']:
            check(not rules(MeshPath=path,SelectWalls=True,**{flag:True})[0], 'category never bypasses '+flag+' '+path)
        check(not rules(MeshPath=path,SelectWalls=True,LevelPath='/Game/Hub/HUB_Gameplay.HUB_Gameplay')[0], 'category never bypasses gameplay protection '+path)
    check(not picker.call_method('IsWall',('/Game/Props/SM_WallLamp.SM_WallLamp',)), 'wall lamps are not walls by name')
    check(not picker.call_method('IsFloor',('/Game/Props/SM_FloorLamp.SM_FloorLamp',)), 'floor lamps are not floors by name')
    vector=lambda t:unreal.Vector(*t)
    def ray(origin, direction=(1,0,0), limit=100):
        return picker.call_method('RayBox',(vector(origin),vector(direction),vector((0,0,0)),vector((1,1,1)),float(limit)))
    hit,t=ray((-10,0,0));check(hit and abs(t-9)<1e-6,'native slab ray returns entry distance')
    check(not ray((-10,2,0))[0], 'parallel ray outside slab misses')
    check(not ray((0,0,0))[0], 'enclosing volumes do not select from inside')
    check(not ray((-10,0,0),limit=8)[0], 'occlusion/range limit clips bounds candidates')
    hit,t=ray((-10,0,0),(2,0,0));check(hit and abs(t-4.5)<1e-6,'inverse-scaled ray preserves its original parameter')
    check(not ray((10,0,0))[0], 'bounds behind ray origin are rejected')
    check(not ray((-10,0,0),(0,0,0))[0], 'zero direction cannot select a box')
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);owned=[]
    def spawn(cls,location=(15000,15000,15000)):
        actor=actors.spawn_actor_from_class(cls,vector(location),unreal.Rotator(),True)
        assert actor is not None
        owned.append(actor);return actor
    def prop(obj,name):return obj.get_editor_property(name)
    def facts(comp,manager):return picker.call_method('Classify',(manager,comp,True,True,True))
    def f(value,name):return field(value,name,root+'ST_DenPick')
    try:
        manager=spawn(unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenWorld'))
        target=spawn(unreal.StaticMeshActor)
        comp=target.static_mesh_component
        mesh=unreal.load_asset('/Engine/BasicShapes/Cube');comp.set_static_mesh(mesh)
        comp.set_mobility(unreal.ComponentMobility.MOVABLE)
        target.set_actor_scale3d(vector((2,1,1)))
        manager.call_method('RefreshActors')
        result=facts(comp,manager)
        check(f(result,'Allowed') and f(result,'Target')==target and f(result,'Key')==target.get_path_name(), 'native static mesh selects whole actor with exact identity')
        check(not picker.call_method('NeedsBounds',(comp,)), 'cube with usable collision keeps authoritative engine collision')
        hit,t=picker.call_method('ComponentBox',(comp,vector((14700,15000,15000)),vector((1,0,0)),500.))
        check(hit and abs(t-200)<.01, 'component OBB handles nonuniform scale without altering ray distance')
        target.set_actor_hidden_in_game(True)
        check(not f(facts(comp,manager),'Allowed'), 'hidden native objects cannot be selected')
        target.set_actor_hidden_in_game(False)
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        picker.call_method('BeginIndex',(manager,))
        for _ in range(2000):
            picker.call_method('PumpIndex')
            if not prop(picker,'Indexing'):break
        check(not prop(picker,'Indexing') and comp in prop(picker,'SurfaceCandidates'), 'budgeted index discovers visible no-collision props')
        # A no-collision surface sits ten cm in front of a solid wall.
        wall=spawn(unreal.StaticMeshActor,(14960,15000,15000));wallcomp=wall.static_mesh_component
        wallcomp.set_static_mesh(mesh);wallcomp.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
        wallcomp.set_collision_profile_name('BlockAll')
        manager.call_method('RefreshActors')
        def query():
            picker.call_method('RequestPick',(vector((14700,15000,15000)),vector((1,0,0)),500.,True,True,True))
            for _ in range(2000):
                picker.call_method('PumpQuery')
                if prop(picker,'QueryReady'):return prop(picker,'QueryResult')
            raise AssertionError('native query never completed')
        found=query()
        check(f(found,'Target')==target, 'surface-adjacent no-collision mesh takes precedence over backing wall')
        wallcomp.set_mobility(unreal.ComponentMobility.MOVABLE)
        wall.set_actor_location(vector((14800,15000,15000)),False,False)
        found=query()
        check(f(found,'Target')==wall, 'solid foreground wall occludes no-collision surface behind it')
        wallcomp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        picker.call_method('IndexCandidate',(wallcomp,))
        picker.call_method('RemoveIndexedComponent',(comp,))
        check(comp not in prop(picker,'SurfaceCandidates') and comp not in prop(picker,'BoundsCandidates')
              and wallcomp in prop(picker,'SurfaceCandidates'),
              'removing one indexed prop preserves the other selection candidates')
        wallcomp.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
        # Existing recovered identities must not fork into a second layout key.
        alias='/Game/Old.Old:PersistentLevel.MovedFurniture'
        check(manager.call_method('BindVanilla',(alias,target)), 'picker fixture binds a recovered vanilla identity')
        check(f(facts(comp,manager),'Key')==alias, 'selection preserves recovered layout identity after object path changes')
        mutation_factory=unreal.GameplayStatics.create_save_game_object(unreal.EditorAssetLibrary.load_blueprint_class('/Game/DenNativeTests/BP_Fixture'))
        changed=mutation_factory.call_method('MakeEntry',(2,alias,unreal.Vector(15000,15000,15000)))
        delta=[mutation_factory.call_method('MakeMutation',(changed,True))]
        target.set_actor_hidden_in_game(True);picker.call_method('RefreshIndexChanges',(delta,))
        check(comp not in prop(picker,'SurfaceCandidates') and wallcomp in prop(picker,'SurfaceCandidates'),
              'incremental index refresh removes a hidden prop without losing unaffected candidates')
        picker.call_method('RefreshIndexedActor',(wall,))
        target.set_actor_hidden_in_game(False);wall.set_actor_location(vector((14960,15000,15000)),False,False)
        picker.call_method('RequestPick',(vector((14700,15000,15000)),vector((1,0,0)),500.,True,True,True))
        picker.call_method('RefreshIndexChanges',(delta,))
        for _ in range(2000):
            picker.call_method('PumpQuery')
            if prop(picker,'QueryReady'):break
        check(not prop(picker,'Indexing') and comp in prop(picker,'SurfaceCandidates')
              and prop(picker,'QueryReady') and f(prop(picker,'QueryResult'),'Target')==target,
              'restoring a no-collision prop updates fallback candidates and preserves an in-flight pick without reindexing')
        picker.call_method('RequestPick',(vector((14700,15000,15000)),vector((1,0,0)),500.,True,True,True))
        picker.call_method('CancelQuery')
        check(not prop(picker,'QueryPending') and not prop(picker,'QueryReady'), 'cancelling a queued pick discards its result')
        picker.call_method('BeginIndex',(None,))
        check(not prop(picker,'Indexing') and len(prop(picker,'SurfaceCandidates'))==0 and len(prop(picker,'BoundsCandidates'))==0, 'invalid replacement world clears stale index')
    finally:
        picker.call_method('CancelQuery')
        for actor in reversed(owned):
            if unreal.SystemLibrary.is_valid(actor):actors.destroy_actor(actor)
