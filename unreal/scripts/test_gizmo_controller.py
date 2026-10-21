"""Real Blueprint controller drags driven by deterministic world-space rays."""
import math
import time


def run(unreal,host,actor,facts,get,field,check,settle,command):
    comp=actor.get_component_by_class(unreal.StaticMeshComponent)
    host.call_method('AcceptSelection',(facts,))
    origin_pose=actor.get_actor_transform()
    center=comp.get_world_location()
    rig=get(host,'EditorRig')
    rig.set_actor_location(center+unreal.Vector(300,300,300),False,False)
    rig.set_actor_rotation(unreal.Rotator(),False)
    host.call_method('InitializeEditorGizmo')
    visual=get(host,'GizmoVisual');math_=get(host,'GizmoMath')
    check(visual is not None and math_ is not None and get(host,'GizmoJob') is not None,
          'controller owns separate native visual math and asynchronous material job')
    for _ in range(1000):
        job=get(host,'GizmoJob')
        if job is not None and unreal.SystemLibrary.is_valid(job):job.call_method('ReceiveTick',(1/60,))
        unreal.ZComAuthoringLibrary.process_test_latent_actions(host)
        host.call_method('PollGizmoMaterial')
        if get(visual,'BuildRequested'):visual.call_method('BuildStep')
        if get(visual,'Ready'):break
        time.sleep(.001)
    check(get(visual,'Ready') and get(host,'GizmoJob') is None,
          'controller loads the overlay asynchronously and releases its completed job')
    ready,pivot,rotation,size=host.call_method('GetGizmoFrame')
    check(ready and pivot==center and abs(size-math.sqrt(3*300**2)*.16)<.001,
          'controller frame uses selection pivot and a fixed apparent size')
    basis=[unreal.Vector(1,0,0),unreal.Vector(0,1,0),unreal.Vector(0,0,1)]
    def unit(v):
        length=math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
        return unreal.Vector(v.x/length,v.y/length,v.z/length)
    def near(a,b,tolerance=.001):return abs(a.x-b.x)<tolerance and abs(a.y-b.y)<tolerance and abs(a.z-b.z)<tolerance
    def ray(o,target):return unit(target-o)
    def point(c,axes,coeff):
        for axis,amount in zip(axes,coeff):c=c+axis*amount
        return c
    def begin(mode,o,target,kind,axis):
        host.call_method('SetGizmoMode',(mode,))
        ok=host.call_method('BeginGizmoDrag',(o,ray(o,target)))
        check(ok and get(host,'DragActive') and get(host,'GizmoDragKind')==kind and get(host,'GizmoDragAxis')==axis,
              f'controller picks mode {mode} kind {kind} axis {axis}')
        assert ok
    def update(o,target):host.call_method('UpdateGizmoDrag',(o,ray(o,target)))
    def finish():
        version=get(get(host,'History'),'Version')
        host.call_method('GizmoPointerButton',(0.,))
        check(not get(host,'DragActive') and get(get(host,'History'),'Version')!=version,'pointer release commits the ray preview transaction')
        settle();command('undo');settle()
        check(actor.get_actor_transform()==origin_pose,'controller Undo restores original geometry')
    try:
        for index,axis in enumerate(basis,1):
            others=[a for a in basis if a!=axis]
            o=center+(others[0]+others[1])*size*3
            target=center+axis*size*.7
            begin(1,o,target,1,index);update(o,target+axis*25)
            check(near(comp.get_world_location(),center+axis*25),f'world axis {index} move follows ray by 25 cm')
            # The handle must not change size while its object moves nearer/farther.
            check(abs(host.call_method('GetGizmoFrame')[3]-size)<.001,'grabbed handle size remains fixed during preview')
            finish()
        for normal in range(3):
            j,k=[i for i in range(3) if i!=normal]
            target=center+(basis[j]+basis[k])*size*.35;o=target+basis[normal]*size*3
            delta=basis[j]*20+basis[k]*30
            begin(1,o,target,2,normal+1);update(o,target+delta)
            check(near(comp.get_world_location(),center+delta),f'move plane excludes axis {normal+1}')
            finish()
        # Local scale axes follow the selected object's rotation, including the
        # plane diagonals. These are not world-axis-only fixtures.
        axes=list(math_.call_method('FrameAxes',(3,rotation)))
        start_scale=comp.get_world_scale()
        for index,axis in enumerate(axes,1):
            j,k=[i for i in range(3) if i!=index-1]
            o=center+(axes[j]-axes[k])*size*3;target=center+axis*size*.7
            begin(3,o,target,1,index);update(o,target+axis*size*.25)
            expected=[start_scale.x,start_scale.y,start_scale.z];expected[index-1]*=1.25
            check(near(comp.get_world_scale(),unreal.Vector(*expected)),f'local scale axis {index} preserves other axes')
            finish()
        for normal in range(3):
            j,k=[i for i in range(3) if i!=normal]
            diagonal=unit(axes[j]+axes[k]);target=center+(axes[j]+axes[k])*size*.35;o=target+axes[normal]*size*3
            begin(3,o,target,2,normal+1);update(o,target+diagonal*size*.25)
            expected=[start_scale.x,start_scale.y,start_scale.z]
            expected[j]*=1.25;expected[k]*=1.25
            check(near(comp.get_world_scale(),unreal.Vector(*expected)),f'local scale plane preserves axis {normal+1}')
            finish()
        target=center+unit(axes[0]+axes[1]+axes[2])*size
        o=center+unreal.Vector(3,3,3)*size
        begin(3,o,target,4,0)
        diagonal=unit(unreal.Vector(0,1,1));update(o,target+diagonal*size*.25)
        scaled=comp.get_world_scale();ratios=[scaled.x/start_scale.x,scaled.y/start_scale.y,scaled.z/start_scale.z]
        check(ratios[0]>1 and max(ratios)-min(ratios)<.0001,'uniform cube grows all axes proportionally along the camera diagonal')
        finish()
        # Rotation about world Z, away from ring intersections with X/Y.
        def circle(angle):
            a=math.radians(angle)
            return center+unreal.Vector(math.sin(a),-math.cos(a),0)*size*.8
        o=center+unreal.Vector(0,0,size*3)
        begin(2,o,circle(30),3,3);update(o,circle(50))
        check(abs(comp.get_world_rotation().yaw-rotation.yaw-20)<.001,
              'ring drag rotates in the cursor direction with world-axis composition')
        finish()
        begin(1,center+unreal.Vector(0,3,3)*size,center+unreal.Vector(.7,0,0)*size,1,1)
        update(center+unreal.Vector(0,3,3)*size,center+unreal.Vector(.7,0,0)*size+unreal.Vector(20,0,0))
        command('mode_scale')
        check(not get(host,'DragActive') and get(host,'GizmoMode')==3 and actor.get_actor_transform()==origin_pose,
              'mode button cancels the preview before selecting the new gizmo')
        command('gimbal');check(get(host,'GizmoMode')==0,'gizmo cycle can turn handles off')
        check(not host.call_method('BeginGizmoDrag',(o,ray(o,circle(30)))),'off mode cannot begin a handle drag')
        command('gimbal');check(get(host,'GizmoMode')==1,'gizmo cycle returns to move')
        command('mode_rotate');check(get(host,'GizmoMode')==2,'rotation button selects native rotation mode')
        command('mode_move');check(get(host,'GizmoMode')==1,'move button selects native move mode')
    finally:
        host.call_method('DestroyEditorGizmo')
        check(get(host,'GizmoVisual') is None and get(host,'GizmoMath') is None and get(host,'GizmoJob') is None
              and not unreal.SystemLibrary.is_valid(visual),'gizmo teardown releases visual material work and math references')
