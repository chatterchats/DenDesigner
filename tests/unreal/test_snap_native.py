"""Bounds snapping: the Blueprint math against fixed hand-derived cases, and snapping during real move drags."""
import json
import os
from pathlib import Path


def run_math(unreal, root, check):
    cases = json.loads((Path(os.environ['DENDESIGNER_REPO']) / 'tests/fixtures/snap_cases.json').read_text())
    obj = unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(root + 'BP_DenSnapMath'))
    V = lambda xyz: unreal.Vector(*xyz)
    near = lambda a, b: all(abs(u - w) < 1e-5 for u, w in zip((a.x, a.y, a.z), b))
    for case in cases['axis']:
        found, delta, kind = obj.call_method('AxisSnap', tuple(float(x) for x in case['in']))
        check((found, kind) == (case['found'], case['kind']) and abs(delta - case['delta']) < 1e-9, 'snap axis: ' + case['name'])
    for case in cases['frame']:
        center, extent = obj.call_method('FrameBox', (V(case['center']), V(case['extent']), float(case['yaw']), float(case['frame_yaw']), V(case['origin'])))
        check(near(center, case['frame_center']) and near(extent, case['frame_extent']), 'snap frame: ' + case['name'])
    for case in cases['boxes']:
        found, delta, kx, ky, kz, strength = obj.call_method('SnapBoxes', (*(V(x) for x in case['d'] + case['t']), float(case['distance']),
                                                                           float(case['near']), *case['allow']))
        check(found == case['found'] and near(delta, case['delta']) and [kx, ky, kz] == case['kinds'] and abs(strength - case['strength']) < 1e-3,
              'snap boxes: ' + case['name'])


def run_drag(unreal, host, picker, spawn, get, set_, check):
    """1 m cubes (pivots at their centres): the moving one 4 cm beside an anchor, a third further along, and a floor
    slab under them, away from other fixtures."""
    cube = unreal.load_asset('/Engine/BasicShapes/Cube')
    ox, oy, oz = -40000, 40000, 20000
    def block(x, y, z, scale=(1, 1, 1)):
        actor = spawn(unreal.StaticMeshActor, unreal.Vector(ox + x, oy + y, oz + z))
        actor.static_mesh_component.set_static_mesh(cube)
        actor.set_actor_scale3d(unreal.Vector(*scale))
        return actor.static_mesh_component
    anchor = block(0, 0, 0)
    floor = block(0, 0, -60, (8, 8, .2))
    moving = block(104, 10, 0)
    beyond = block(130, 160, 0)
    candidates = list(get(picker, 'SurfaceCandidates'))
    rig = get(host, 'EditorRig')
    def preview(x, y, z):
        host.call_method('PreviewSelectionDrag', (unreal.Vector(ox + x, oy + y, oz + z), moving.get_world_rotation(), moving.get_world_scale()))
        at = moving.get_world_location()
        return unreal.Vector(at.x - ox, at.y - oy, at.z - oz)
    try:
        set_(picker, 'SurfaceCandidates', [anchor, floor, moving, beyond])
        host.call_method('RefreshActors')
        host.call_method('AcceptSelection', (picker.call_method('Classify', (host, moving, True, True, True)),))
        for name, value in [('SnapEnabled', True), ('SurfaceDragging', True), ('SurfaceVertical', False), ('GizmoDragKind', 0)]:
            set_(host, name, value)
        check(host.call_method('BeginSelectionDrag', (1,)), 'snapping test drag begins')
        check(list(get(host, 'SnapTargets')) == [anchor, beyond], 'snapping gathers the nearby blocks but neither itself nor a floor-sized slab')
        at = preview(104, 10, 0)
        check(abs(at.x - 100) < 1e-3 and abs(at.y - 10) < 1e-3 and get(host, 'SnapActive') and get(host, 'SnapKindX') == 4,
              'a surface drag 4 cm from a block snaps flush against it; the 10 cm side offset stays')
        at = preview(103, 63, 0)
        check(abs(at.x - 100) < 1e-3 and abs(at.y - 60) < 1e-3 and get(host, 'SnapKindX') == 4 and get(host, 'SnapKindY') == 5,
              'one axis snaps flush to one block while the other snaps flush to a second block')
        set_(rig, 'bAlt', True)
        at = preview(104, 10, 0)
        check(abs(at.x - 104) < 1e-3 and not get(host, 'SnapActive'), 'holding Alt drags freely')
        set_(rig, 'bAlt', False)
        set_(host, 'SnapEnabled', False)
        check(abs(preview(104, 10, 0).x - 104) < 1e-3, 'the SNAP toggle turns neighbour snapping off')
        set_(host, 'SnapEnabled', True)
        set_(host, 'SurfaceVertical', True)
        at = preview(1, 0, 103)
        check(abs(at.z - 100) < 1e-3 and abs(at.x - 1) < 1e-3 and get(host, 'SnapKindZ') == 4 and get(host, 'SnapKindX') == 0,
              'a Shift height drag stacks on top and leaves the sideways position alone')
        for name, value in [('SurfaceDragging', False), ('SurfaceVertical', False), ('GizmoDragKind', 1), ('GizmoDragVector', unreal.Vector(0, 1, 0))]:
            set_(host, name, value)
        check(abs(preview(104, 10, 0).x - 104) < 1e-3, 'a gizmo Y handle never snaps along X')
        host.call_method('EndSelectionDrag', (False,))
        check(not get(host, 'SnapTargets') and not get(host, 'SnapActive'), 'ending the drag releases the snapping neighbours')
    finally:
        for name, value in [('SurfaceDragging', False), ('SurfaceVertical', False), ('GizmoDragKind', 0)]:
            set_(host, name, value)
        set_(rig, 'bAlt', False)
        set_(picker, 'SurfaceCandidates', candidates)
        host.call_method('ClearSelection')
        for component in [anchor, floor, moving, beyond]:
            component.get_owner().destroy_actor()
