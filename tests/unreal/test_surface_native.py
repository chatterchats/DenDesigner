"""Exercise surface traces, drag rebasing and delayed pointer selection in the VM."""
import math


def run(unreal,host,actor,facts,get,check,settle,command,set_):
    comp=actor.static_mesh_component
    baseline=actor.get_actor_transform();center=comp.get_world_location()
    history=get(host,'History');count=len(get(history,'UndoSteps'))
    response=comp.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    floor=actors.spawn_actor_from_class(unreal.StaticMeshActor,center+unreal.Vector(0,0,-300),unreal.Rotator(),transient=True)
    floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
    floor.set_actor_scale3d(unreal.Vector(20,20,1))
    floor.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    floor.static_mesh_component.set_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_BLOCK)
    def unit(v):
        length=math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
        return v/length
    def ray(o,p):return unit(p-o)
    def near(a,b):return (a-b).length()<.002
    def select():host.call_method('AcceptSelection',(facts,))
    def begin(o,p,vertical=False):return host.call_method('BeginSurfaceDrag',(o,ray(o,p),vertical))
    def update(o,p,vertical=False):host.call_method('UpdateSurfaceDrag',(o,ray(o,p),vertical))
    def end(commit=False):return host.call_method('EndSelectionDrag',(commit,))
    def restored(label):
        check(actor.get_actor_transform()==baseline and comp.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY)==response,label)
    o=center+unreal.Vector(0,-400,600);p=center+unreal.Vector(20,0,-250)
    try:
        select();host.call_method('InitializeEditorGizmo')
        # Separate ray capture from asynchronous completion to exercise the same
        # boundary that PollSelection crosses while a real button is held.
        host.call_method('PrepareSurfacePress',(o,ray(o,p)))
        host.call_method('GizmoPointerButton',(0.,))
        host.call_method('ConsumePointerSelection',(facts,))
        check(get(host,'HasSelection') and not get(host,'SurfaceArmed') and not get(host,'DragActive'),
              'release before pick completion selects without arming a late drag')
        host.call_method('PrepareSurfacePress',(o,ray(o,p)))
        host.call_method('ConsumePointerSelection',(facts,))
        check(get(host,'SurfaceArmed') and get(host,'SurfaceButtonDown'),
              'held pointer selection arms the accepted component after clearing old selection')
        host.call_method('ConsiderSurfaceDrag',(o,ray(o,p),False))
        check(not get(host,'DragActive'),'unmoved click stays below the surface drag threshold')
        host.call_method('ConsiderSurfaceDrag',(o,ray(o,p+unreal.Vector(30,0,0)),False))
        check(get(host,'SurfaceDragging') and get(host,'DragActive'),'pointer motion starts a native surface transaction')
        end();restored('cancelled armed drag restores pose and visibility response')
        host.call_method('PrepareSurfacePress',(o,ray(o,p)))
        host.call_method('ConsumePointerSelection',(facts,))
        host.call_method('ClearSelection')
        check(not get(host,'SurfaceArmed') and not get(host,'SurfaceButtonDown'),'selection clearing disarms pending pointer work')
        select()
        check(begin(o,p),'surface drag begins on a real collision floor')
        check(comp.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY)==unreal.CollisionResponseType.ECR_IGNORE,
              'drag temporarily ignores only the selected component in visibility traces')
        hit,point=host.call_method('TraceDragSurface',(o,ray(o,p)))
        check(hit and near(point,p),'surface trace finds the real floor beneath the selected object')
        delta=unreal.Vector(40,30,0);update(o,p+delta)
        check(near(comp.get_world_location(),center+delta) and len(get(history,'UndoSteps'))==count,
              'surface preview preserves the initial grab offset without changing history')
        check(end(True),'surface release commits movement');settle()
        check(len(get(history,'UndoSteps'))==count+1 and comp.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY)==response,
              'surface release creates one undo step and restores collision')
        command('undo');settle();restored('one Undo restores original surface-drag geometry')
        select();check(begin(o,p),'begin modifier-switch drag');update(o,p+delta)
        before=comp.get_world_location();update(o,p+delta,True)
        check(near(comp.get_world_location(),before),'pressing Shift rebases without a position jump')
        grab=get(host,'SurfaceGrab');update(o,grab+unreal.Vector(0,0,45),True)
        lifted=comp.get_world_location()
        check(near(lifted,before+unreal.Vector(0,0,45)),'height drag changes only Z')
        update(o,grab+unreal.Vector(0,0,45),False)
        check(near(comp.get_world_location(),lifted),'releasing Shift rebases back to the surface without a jump')
        command('back');restored('Escape restores both pose and collision after modifier changes')
        check(get(host,'HasSelection') and len(get(history,'UndoSteps'))==count,'Escape keeps selection and makes no history')
        select();set_(host,'GridStep',10.)
        check(begin(o,p),'begin snapped surface drag');update(o,p+delta)
        expected=unreal.Vector(round((center.x+40)/10)*10,round((center.y+30)/10)*10,center.z)
        check(near(comp.get_world_location(),expected),'surface grid snaps absolute X and Y while preserving height')
        end();set_(host,'GridStep',0.);restored('snapped cancellation restores exact non-grid original pose')
        # Remove the floor: the horizontal plane remains usable over empty space.
        floor.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        select();q=center+unreal.Vector(20,0,0);check(begin(o,q),'surface drag can begin over empty space')
        update(o,q+delta)
        check(near(comp.get_world_location(),center+delta),'missing floor uses the captured horizontal plane')
        end();restored('fallback drag cancellation restores original state')
        select();check(begin(o,center,True),'height drag can begin without a floor')
        update(o,center+unreal.Vector(0,0,25),True)
        check(near(comp.get_world_location(),center+unreal.Vector(0,0,25)),'direct Shift drag uses a camera-facing vertical plane')
        host.call_method('ClearSelection');restored('selection replacement restores active surface collision and preview')
        check(not get(host,'SurfaceDragging') and not get(host,'SurfaceArmed'),'selection replacement clears all surface ownership')
    finally:
        end();set_(host,'GridStep',0.)
        host.call_method('DestroyEditorGizmo')
        actors.destroy_actor(floor)
    select()
