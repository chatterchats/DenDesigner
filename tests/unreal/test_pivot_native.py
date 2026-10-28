"""Bounds anchors and fixed-point transformations executed by the Blueprint VM."""
import math


def run(unreal, host, picker, spawn, get, set_, check, settle, command):
    V = lambda xyz: unreal.Vector(*xyz)
    def near(a, b, tolerance=.001):
        return (a-b).length() < tolerance
    def worldpoint(component, point):
        return component.get_world_transform().transform_location(point)

    # Asymmetric bounds reproduce meshes whose authored origin is beside the visible geometry.
    lo, hi = V((-240, 30, -20)), V((-80, 90, 180))
    for anchor, xyz in [('centre', (-160, 60, 80)), ('bottom', (-160, 60, -20)),
                        ('top', (-160, 60, 180)), ('origin', (0, 0, 0))]:
        got = host.call_method('BoundsEditPivot', (lo, hi, anchor))
        check(near(got, V(xyz)), 'offset mesh bounds give the correct '+anchor+' edit anchor')
    check(near(host.call_method('GetComponentEditPivot', (None, 'centre')), V((0,0,0))),
          'missing pivot component safely returns zero')

    obj = spawn(unreal.StaticMeshActor, V((46000,-42000,11000)))
    comp = obj.static_mesh_component
    comp.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
    obj.set_actor_scale3d(V((2,1,3)))
    host.call_method('RefreshActors')
    facts = picker.call_method('Classify', (host, comp, True, True, True))
    host.call_method('AcceptSelection', (facts,))
    original = obj.get_actor_transform()
    oldpivot = get(host, 'RotationPivot'); oldmode = get(host, 'GizmoMode')
    oldsnap = get(host, 'SnapEnabled'); rig = get(host, 'EditorRig'); rigpose = rig.get_actor_transform()
    locals_ = {'centre': V((0,0,0)), 'bottom': V((0,0,-50)), 'top': V((0,0,50)), 'origin': V((0,0,0))}
    rig.set_actor_location(obj.get_actor_location()+V((400,400,400)), False, False)
    def undo():
        command('undo'); settle()
    host.call_method('InitializeEditorGizmo')
    try:
        set_(host, 'SnapEnabled', False)
        for anchor in locals_:
            set_(host, 'RotationPivot', anchor)
            for mode in [1, 2, 3]:
                host.call_method('SetGizmoMode', (mode,))
                ok, at, _, _ = host.call_method('GetGizmoFrame')
                expected = worldpoint(comp, locals_[anchor] if mode == 2 else V((0,0,0)))
                check(ok and near(at, expected), f'gizmo mode {mode} uses the correct bounds anchor with {anchor} selected')
            history = get(host, 'History'); count = len(get(history, 'UndoSteps'))
            fixed = worldpoint(comp, locals_[anchor])
            check(host.call_method('BeginSelectionDrag', (2,)), 'pivot rotation drag begins: '+anchor)
            targetrot = unreal.Rotator(pitch=90, yaw=0, roll=0)
            check(host.call_method('PreviewSelectionDrag', (V((0,0,0)), targetrot, V((1,1,1)))), 'pivot rotation preview accepted: '+anchor)
            check(near(worldpoint(comp, locals_[anchor]), fixed), 'rotation keeps the chosen anchor fixed: '+anchor)
            check(len(get(history,'UndoSteps')) == count, 'pivot rotation preview leaves history untouched: '+anchor)
            check(host.call_method('EndSelectionDrag', (True,)), 'pivot rotation commits once: '+anchor)
            settle()
            final = obj.get_actor_transform()
            check(near(worldpoint(comp, locals_[anchor]), fixed) and len(get(history,'UndoSteps')) == count+1,
                  'rotation and origin compensation form one history step: '+anchor)
            undo()
            check(obj.get_actor_transform() == original, 'undo restores full pose after pivot rotation: '+anchor)
            command('redo'); settle()
            check(obj.get_actor_transform() == final, 'redo restores both position and rotation: '+anchor)
            undo()

        # Numeric angles and wheel/Q/E turning must use the same anchor as the rings.
        set_(host,'RotationPivot','top')
        fixed = worldpoint(comp,locals_['top'])
        host.call_method('SetSelectionField', ('Pitch','90')); settle()
        check(near(worldpoint(comp,locals_['top']),fixed), 'numeric pitch rotates around the selected top anchor')
        undo()
        host.call_method('SetSelectionField', ('Pitch','45')); settle()
        fixed = worldpoint(comp,locals_['top'])
        host.call_method('RotateSelection', (1.,15.)); settle()
        check(near(worldpoint(comp,locals_['top']),fixed), 'wheel/key yaw preserves the top anchor of an already tilted prop')
        undo(); undo()

        # Capture once: changing the option externally during a drag cannot move its fixed point.
        set_(host,'RotationPivot','bottom'); fixed=worldpoint(comp,locals_['bottom'])
        host.call_method('BeginSelectionDrag',(2,))
        set_(host,'RotationPivot','top')
        host.call_method('PreviewSelectionDrag',(V((0,0,0)),unreal.Rotator(pitch=35,yaw=25,roll=15),V((1,1,1))))
        check(near(worldpoint(comp,locals_['bottom']),fixed),'rotation drag retains the anchor captured at press')
        host.call_method('EndSelectionDrag',(False,))
        check(obj.get_actor_transform()==original,'cancelled pivot rotation restores the exact original pose')

        host.call_method('SetGizmoMode',(3,)); host.call_method('BeginSelectionDrag',(3,))
        fixed=worldpoint(comp,V((0,0,0)))
        host.call_method('PreviewSelectionDrag',(V((0,0,0)),unreal.Rotator(),V((4,2,6))))
        check(near(worldpoint(comp,V((0,0,0))),fixed),'scale preview keeps the bounds centre under its gizmo')
        host.call_method('EndSelectionDrag',(False,))
        check(obj.get_actor_transform()==original,'cancelled bounds-centred scale restores the exact pose')

        # Drive the actual Y rotation ring with rays around the top anchor.
        set_(host,'RotationPivot','top'); host.call_method('SetGizmoMode',(2,))
        ready, fixed, _, size = host.call_method('GetGizmoFrame')
        def circle(degrees):
            angle=math.radians(degrees)
            return fixed+V((math.cos(angle),0,math.sin(angle)))*size*.8
        eye=fixed+V((0,size*3,0))
        def ray(target):
            delta=target-eye
            return delta/delta.length()
        began=host.call_method('BeginGizmoDrag',(eye,ray(circle(30))))
        check(ready and began and get(host,'GizmoDragKind')==3 and get(host,'GizmoDragAxis')==2,
              'rotation ring is picked around the top anchor')
        host.call_method('UpdateGizmoDrag',(eye,ray(circle(50))))
        check(near(worldpoint(comp,locals_['top']),fixed) and abs(obj.get_actor_rotation().pitch)>1,
              'real ring drag rotates around the top point without moving that point')
        check(near(host.call_method('GetGizmoFrame')[1],fixed),'rotation gizmo stays on its anchor throughout a ring drag')
        host.call_method('EndSelectionDrag',(True,)); settle(); undo()
        check(obj.get_actor_transform()==original,'undo restores the whole pose after anchored ring input')
    finally:
        host.call_method('EndSelectionDrag',(False,))
        for key,value in [('RotationPivot',oldpivot),('SnapEnabled',oldsnap)]:set_(host,key,value)
        host.call_method('SetGizmoMode',(oldmode,))
        rig.set_actor_transform(rigpose,False,True)
        host.call_method('DestroyEditorGizmo')
        host.call_method('ClearSelection')
        obj.destroy_actor()
