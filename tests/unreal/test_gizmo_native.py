"""Actual Blueprint VM gizmo math, including frozen differential reference cases."""
import json
import math
import os
from pathlib import Path


def run(unreal, root, check):
    saved=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())).resolve()
    assert saved==Path(os.environ['DENDESIGNER_TEST_SAVED']).resolve()
    obj=unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenGizmoMath'))
    V=lambda xyz:unreal.Vector(*xyz)
    zero=V((0,0,0));x=V((1,0,0));y=V((0,1,0));z=V((0,0,1))
    def invoke(name,*args):return obj.call_method(name,args)
    def near(a,b,tolerance=1e-5):
        return all(abs(u-v)<tolerance for u,v in zip((a.x,a.y,a.z),b))
    valid,t=invoke('AxisParam',V((50,-100,0)),y,zero,x)
    check(valid and abs(t-50)<1e-6,'gizmo axis projection returns distance along the handle')
    valid,t=invoke('AxisParam',V((50,-100,0)),V((0,5,0)),zero,V((3,0,0)))
    check(valid and abs(t-50)<1e-6,'gizmo projection normalizes ray and axis lengths')
    for axis,direction,label in [(x,x,'parallel'),(zero,y,'zero axis'),(x,zero,'zero ray')]:
        valid,t=invoke('AxisParam',V((50,-100,0)),direction,zero,axis)
        check(not valid and math.isfinite(t),'gizmo safely rejects '+label+' projection')
    valid,distance,along=invoke('SegmentDistance',V((150,-100,0)),y,zero,x,100.)
    check(valid and abs(distance-50)<1e-6 and along==100,'gizmo shaft picking clamps to the endpoint')
    valid,p=invoke('PlanePoint',V((20,30,100)),V((0,0,-2)),zero,z)
    check(valid and near(p,(20,30,0)),'gizmo plane intersection accepts normalized or scaled rays')
    for origin,direction in [((20,30,100),(1,0,0)),((20,30,100),(0,0,1)),((20,30,100),(0,0,0))]:
        check(not invoke('PlanePoint',V(origin),V(direction),zero,z)[0],'gizmo rejects parallel/behind/zero plane rays')
    valid,distance,degrees=invoke('RingDistance',V((80,0,100)),V((0,0,-1)),zero,z,80.)
    check(valid and distance<1e-6 and abs(degrees-90)<1e-5,'gizmo ring distance and angle use the reference orientation')
    for distance,expected in [(0,1),(1,1),(100,16),(1000,160)]:
        check(invoke('SizeFor',float(distance))==expected,'gizmo size stays proportional to distance with a one-cm minimum')
    for value,step,expected in [(7.5,15,15),(-7.5,15,0),(14.9,0,14.9),(-23,15,-30)]:
        check(invoke('SnapValue',float(value),float(step))==expected,'gizmo snapping preserves signed half-step behavior')
    for value,expected in [(180,-180),(-180,-180),(359,-1),(-359,1),(721,1)]:
        check(invoke('WrapAngle',float(value))==expected,'gizmo angle wraps through the shortest signed turn')
    rotation=unreal.Rotator(yaw=90)
    axes=invoke('FrameAxes',3,rotation)
    check(near(axes[0],(0,1,0)) and near(axes[1],(-1,0,0)) and near(axes[2],(0,0,1)),
          'scale gizmo follows the object rotation')
    axes=invoke('FrameAxes',1,rotation)
    check(near(axes[0],(1,0,0)) and near(axes[1],(0,1,0)),'move gizmo remains in world axes')
    def pick(origin,direction,mode=1,rotation=None,size=100):
        return invoke('PickHandle',V(origin),V(direction),zero,float(size),mode,rotation or unreal.Rotator())
    for origin,direction,expected in [
        ((70,-100,0),(0,1,0),(1,1)),((35,35,100),(0,0,-1),(2,3)),
        ((35,100,35),(0,-1,0),(2,2)),((100,35,35),(-1,0,0),(2,1)),
    ]:
        check(pick(origin,direction)==expected,'gizmo picks the expected world axis or plane square')
    check(pick((80,0,100),(0,0,-1),2)==(3,3),'rotate mode picks its Z ring')
    uniform=100/math.sqrt(3)
    check(pick((uniform,uniform,uniform+100),(0,0,-1),3)==(4,0),'uniform scale cube wins within its grab radius')
    check(pick((-35,35,100),(0,0,-1),3,rotation)==(2,3),'rotated scale plane uses local XY')
    for kwargs in [dict(mode=0),dict(mode=99),dict(size=0),dict(size=-1)]:
        check(pick((70,-100,0),(0,1,0),**kwargs)==(0,0),'disabled or invalid gizmo frame is not pickable')
    check(pick((70,-100,0),(0,0,0))==(0,0),'zero ray cannot select a gizmo handle')

    valid,delta=invoke('AxisDelta',V((50,-100,0)),y,V((75,-100,0)),y,zero,x)
    check(valid and abs(delta-25)<1e-6,'axis drag measures signed displacement from the grab')
    valid,offset=invoke('PlaneDelta',V((35,35,100)),V((0,0,-1)),V((50,70,100)),V((0,0,-1)),zero,z)
    check(valid and near(offset,(15,35,0)),'plane drag changes both axes without changing its normal')
    def ring_origin(deg):
        radians=math.radians(deg);return V((80*math.sin(radians),-80*math.cos(radians),100))
    valid,angle=invoke('RingDelta',ring_origin(179),V((0,0,-1)),ring_origin(-179),V((0,0,-1)),zero,z,1.)
    check(valid and angle==2,'ring drag crosses the angle seam without a 358-degree jump')
    check(not invoke('AxisDelta',V((50,-100,0)),y,V((75,-100,0)),x,zero,x)[0],
          'a parallel drag sample is rejected without a bogus displacement')
    for kind,axis,along,expected in [(1,1,50,(3,3,4)),(2,3,50,(3,4.5,4)),(4,0,50,(3,4.5,6)),(4,0,-200,(.1,.15,.2)),(4,0,10000,(20,20,20))]:
        valid,scale=invoke('ScaleFromDrag',V((2,3,4)),kind,axis,float(along),100.)
        check(valid and near(scale,expected),'scale drag preserves untouched axes and clamps changed axes')
    check(not invoke('ScaleFromDrag',V((2,3,4)),0,0,50.,100.)[0],'invalid scale handle cannot mutate the pose')
    rotated=invoke('RotateFromDrag',unreal.Rotator(yaw=30),z,15.)
    check(abs(rotated.yaw-45)<1e-5,'ring rotation composes with the initial pose')
    rotated=invoke('RotateFromDrag',unreal.Rotator(yaw=90),x,90.)
    check(near(invoke('FrameAxes',3,rotated)[0],(0,0,1)),'ring rotation applies around the world axis, not the object axis')

    # Build the actual native procedural mesh, inspect its geometry and verify
    # that mode/hover changes only switch sections rather than rebuilding them.
    from runtime_gizmo_visual import geometry, OVERLAY
    shapes=geometry()['handles']
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    visual=actors.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenGizmoVisual'),
                                        V((20000,20000,20000)),unreal.Rotator(),transient=True)
    try:
        mesh=visual.get_component_by_class(unreal.ProceduralMeshComponent)
        check(mesh is not None and mesh.get_num_sections()==0,'native gizmo starts without mesh work or collision geometry')
        check(not visual.call_method('BeginBuild',(None,)),'native gizmo rejects a missing material')
        material=unreal.load_asset(OVERLAY)
        assert material is not None
        check(visual.call_method('BeginBuild',(material,)),'native gizmo accepts an already loaded overlay material')
        one_per_step=True
        for index in range(32):
            visual.call_method('BuildStep')
            one_per_step &= mesh.get_num_sections()==index+1
        check(one_per_step and visual.get_editor_property('Ready') and not visual.is_actor_tick_enabled(),
              'native gizmo builds one section per tick and stops ticking when all 32 are ready')
        visual.call_method('BuildStep')
        check(not visual.call_method('BeginBuild',(material,)) and mesh.get_num_sections()==32,
              'completed gizmo geometry is never rebuilt by repeated requests')
        check(mesh.get_collision_enabled()==unreal.CollisionEnabled.NO_COLLISION and not mesh.get_editor_property('cast_shadow'),
              'gizmo cannot block picking or cast shadows')
        exact=True
        for index in range(32):
            vertices,triangles,*_=unreal.ProceduralMeshLibrary.get_section_from_procedural_mesh(mesh,index)
            expected=shapes[index//2]['section']
            exact &= len(vertices)==len(expected['v']) and list(triangles)==expected['t'] and mesh.get_material(index)==material
            exact &= all(near(point,[expected['v'][i][axis] for axis in AXES],.001) for i,point in enumerate(vertices))
        check(exact,'all native handle vertices/triangles and overlay materials match the baked geometry')
        center=V((22000,21000,20000))
        def visible():return [i for i in range(32) if mesh.is_mesh_section_visible(i)]
        def show(mode,kind=0,axis=0,size=50):
            visual.call_method('ShowPose',(center,rotation,float(size),mode,kind,axis))
        show(1)
        check(visible()==[0,2,4,6,8,10] and near(visual.get_actor_scale3d(),(.5,.5,.5)) and abs(visual.get_actor_rotation().yaw)<1e-5,
              'move mode shows three arrows and plane squares at the requested size in world axes')
        show(2)
        check(visible()==[18,20,22],'rotate mode shows only its three rings')
        show(3,2,3)
        check(visible()==[12,14,17,24,26,28,30] and abs(visual.get_actor_rotation().yaw-90)<1e-5,
              'scale mode uses local axes and highlights only the hovered XY square')
        show(3,4,0)
        check(visible()==[12,14,16,24,26,28,31],'uniform scale hover switches the diagonal cube')
        check(mesh.get_num_sections()==32 and near(visual.get_actor_location(),(22000,21000,20000)),
              'gizmo pose and hover updates preserve the built geometry')
        show(0)
        check(visual.get_editor_property('hidden'),'off mode hides the entire gizmo')
        show(1)
        check(not visual.get_editor_property('hidden'),'valid show restores visibility after off')
        show(1,size=0)
        check(visual.get_editor_property('hidden'),'invalid display size safely hides the gizmo')
    finally:
        if unreal.SystemLibrary.is_valid(visual):actors.destroy_actor(visual)

    # Frozen independent reference: retain the original 360-ray differential coverage.
    repo=Path(__file__).resolve().parents[2]
    fixture=json.loads((repo/'tests/fixtures/gizmo_pick.json').read_text())
    cases=fixture['cases'];reference=fixture['expected']
    mismatches=[];hits=0
    for i,(case,expected) in enumerate(zip(cases,reference)):
        vec=lambda name:V([case[name][axis] for axis in AXES])
        got=invoke('PickHandle',vec('origin'),vec('direction'),vec('center'),case['size'],case['native_mode'],unreal.Rotator(yaw=case['yaw']))
        if got!=(expected['kind'],expected['axis']):mismatches.append((i,got,expected))
        if expected['kind']:hits+=1
    check(len(reference)==len(cases) and hits>150 and not mismatches,
          f'native gizmo agrees with the frozen reference for {len(cases)} aimed rays ({hits} hits): {mismatches[:4]}')


AXES=['X','Y','Z']
