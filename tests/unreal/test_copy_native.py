"""Native copy/focus regression on vanilla components and managed placed props."""
import math


def run(unreal,host,actor,facts,other_facts,get,field,check,settle,command):
    from runtime_pick import FACT
    comp=actor.get_component_by_class(unreal.StaticMeshComponent)
    host.call_method('AcceptSelection',(facts,))
    rig=get(host,'EditorRig');rig_pose=rig.get_actor_transform()
    baseline=actor.get_actor_transform();history=get(host,'History')
    version=get(history,'Version');count=len(get(history,'UndoSteps'))
    doc=get(host,'WorkingDocument');source_kind=field(facts,'Kind',FACT)
    before=list(get(doc,'Entries'))
    def near(a,b):return (a-b).length()<.002
    def undo():command('undo');settle()
    def copied(key):return next(row for row in get(doc,'Entries') if field(row,'Key')==key)
    try:
        if source_kind==2:
            original_material=comp.get_material(0)
            try:
                dynamic=comp.create_dynamic_material_instance(0)
                ready,paths=host.call_method('ReadCopyMaterials')
                check(dynamic is not None and ready and paths[0]=='',
                      'copy excludes transient dynamic materials instead of persisting invalid asset paths')
            finally:
                comp.set_material(0,original_material)
        rotation=unreal.Rotator(pitch=-20,yaw=90,roll=0)
        rig.set_actor_rotation(rotation,False)
        rotation=rig.get_actor_rotation()
        origin,extent,radius=unreal.SystemLibrary.get_component_bounds(comp)
        # Frame the box diagonal rather than its sphere radius.
        distance=max(150,math.sqrt(extent.x**2+extent.y**2+extent.z**2)*2.5)
        expected=origin-rig.get_actor_forward_vector()*distance
        host.call_method('PrepareSurfacePress',(unreal.Vector(),unreal.Vector(1,0,0)))
        host.call_method('ConsumePointerSelection',(facts,))
        command('focus');settle()
        check(not get(host,'SurfaceArmed') and not get(host,'SurfaceButtonDown'),
              'Focus disarms held selection so camera movement cannot accidentally start dragging')
        check(near(rig.get_actor_location(),expected) and rig.get_actor_rotation()==rotation,
              'Focus frames selected bounds while preserving camera orientation')
        check(get(history,'Version')==version and actor.get_actor_transform()==baseline,
              'Focus changes neither the prop nor layout history')
        command('duplicate')
        key=get(host,'PendingCopyKey');check(bool(key),'Copy commits a fresh identity before asynchronous placement')
        host.call_method('DuplicateSelection')
        check(get(host,'PendingCopyKey')==key,'a busy copy cannot overwrite pending placement ownership')
        settle()
        value=copied(key);selected=get(host,'Selected')
        check(get(host,'HasSelection') and field(selected,'Kind',FACT)==0 and field(selected,'Key',FACT)==key,
              'completed copy becomes the selected managed prop')
        check(get(host,'PendingCopyKey')=='','completed copy releases pending selection state')
        gap=2*max(extent.x,extent.y)+10
        check(near(field(value,'Position'),comp.get_world_location()+unreal.Vector(-gap,0,0)),
              'copy is spaced beside the original along camera yaw right')
        check(field(value,'Rotation')==comp.get_world_rotation() and field(value,'Scale')==comp.get_world_scale(),
              'copy preserves exact rotation and nonuniform scale')
        check(field(value,'Mesh')==comp.static_mesh.get_path_name() and not field(value,'Hidden') and actor.get_actor_transform()==baseline,
              'copy owns the same mesh without moving or hiding its source')
        if source_kind==2:
            check(field(value,'Source')==field(facts,'Key',FACT), 'native copy retains source object identity')
            check(list(field(value,'Materials'))==[comp.get_material(i).get_path_name() if comp.get_material(i) else '' for i in range(comp.get_num_materials())],
                  'native copy captures stable material overrides in slot order')
        else:
            original=next(row for row in before if field(row,'Kind')==0 and field(row,'Key')==field(facts,'Key',FACT))
            check(all(field(value,n)==field(original,n) for n in ['CollisionMode','Materials','Source','HasFingerprint','FingerprintMesh','FingerprintPosition']),
                  'placed copy preserves collision materials source and fingerprint metadata')
        check(len(get(history,'UndoSteps'))==count+1,'copy is exactly one undoable operation')
        undo();check(len(get(doc,'Entries'))==len(before) and actor.get_actor_transform()==baseline,'Undo removes only the copy')
        command('redo');settle();check(field(copied(key),'Position')==field(value,'Position'),'Redo restores the copy with the same identity and pose')
        undo()
        host.call_method('AcceptSelection',(facts,));command('duplicate');second=get(host,'PendingCopyKey')
        check(second and second!=key,'a new copy after Undo receives a distinct identity')
        host.call_method('AcceptSelection',(other_facts,));settle()
        check(field(get(host,'Selected'),'Key',FACT)==field(other_facts,'Key',FACT) and get(host,'PendingCopyKey')=='',
              'asynchronous copy cannot steal a newer selection')
        check(copied(second) is not None,'changing selection does not discard the accepted copy')
        undo()
        host.call_method('AcceptSelection',(facts,))
        check(host.call_method('BeginSelectionDrag',(1,)),'begin preview before queued Focus')
        command('focus');check(len(get(host,'EditEvents'))==1,'Focus waits for active drag completion')
        host.call_method('EndSelectionDrag',(False,));settle()
        check(len(get(host,'EditEvents'))==0 and actor.get_actor_transform()==baseline,'queued Focus completes after cancellation without editing geometry')
    finally:
        rig.set_actor_transform(rig_pose,False,False)
    host.call_method('AcceptSelection',(facts,))
