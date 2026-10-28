"""Bounds snapping for move drags: neighbours gathered once per drag, snapped every preview.

BeginSnapDrag caches props near the dragged one from the picker's index (their world centre,
half extent and yaw). SnapDragPosition snaps a proposed position to the closest of them, on the
axes the drag allows: X/Y for surface drags, Z for Shift height drags, and for gizmo handles
only the target axes along the handle's line or inside its plane. Alt skips snapping.
Floor-sized pieces (both horizontal half extents over FLOOR) are ignored; walls are kept so
props can be pushed flush against them. Guides are overlay geometry, never debug lines,
which shipping builds strip.
"""
from graph import Graph, variable as v, KML, KSL, GS
from runtime import ROOT, arr
from runtime_store import call, branch, combine, STR
from runtime_world import ACTOR, SCENE, SMC, set_value, validity
from runtime_apply import get
from runtime_session import prop, method
from runtime_pick import PICKER
from runtime_editor_assets import RIG
from runtime_editor_host import PC, CAM, text, widget, visibility
from runtime_snap_math import MATH, FAR
import ui_templates as editor

GUIDES = ROOT + 'BP_DenSnapGuides'
PMC = '/Script/ProceduralMeshComponent.ProceduralMeshComponent'
RANGE, LIMIT, FLOOR, NEAR, MARGIN = 300, 64, 300, 100, 12
SNAP_PIXELS = 10  # the snap range on screen; Snap distance is its minimum close up
LINE = editor.rgba(*editor.ACCENT)


def op(g, name, fn, a=None, b=None, **defaults):
    return call(g, name, KML + ':' + fn, {**({'A': a} if a else {}), **({'B': b} if b else {})}, **defaults)


def snap_math(g, name, fn, inputs=None, **defaults):
    return method(g, name, MATH, fn, get(g, 'SnapMath'), inputs, **defaults)


def each(g, name, array, cursor):
    """Loop header: returns (item pin, loop node, next node). Chain the body from the loop node's then
    to the next node; the loop node's else continues after the loop."""
    g.get(name + 'i', 'local:' + cursor)
    arr(g, name + 'len', 'Length', array)
    branch(g, name + 'loop', call(g, name + 'within', KML + ':Less_IntInt', {'A': name + 'i.' + cursor, 'B': name + 'len.ReturnValue'}))
    arr(g, name + 'item', 'Get', array)
    g.wire((name + 'i.' + cursor, name + 'item.Index'))
    set_value(g, name + 'next', 'local:' + cursor, call(g, name + 'inc', KML + ':Add_IntInt', {'A': name + 'i.' + cursor}, B=1))
    g.chain(name + 'next', name + 'loop')
    return name + 'item.Item', name + 'loop', name + 'next'


def begin_snap():
    g = Graph()
    g.node('self', 'self')
    g.call('clear', 'self:EndSnapDrag')
    move = call(g, 'move', KML + ':EqualEqual_IntInt', {'A': get(g, 'DragMode')}, B=1)
    branch(g, 'valid', combine(g, 'ready', [move, validity(g, 'component', get(g, 'DragComponent')), validity(g, 'picker', get(g, 'Picker'))]))
    branch(g, 'hasmath', validity(g, 'mathvalid', get(g, 'SnapMath')))
    call(g, 'create', GS + ':SpawnObject', {'Outer': 'self.self'}, ObjectClass=MATH)
    g.node('cast', 'cast', **{'class': MATH})
    g.wire(('create.ReturnValue', 'cast.Object'))
    set_value(g, 'math', 'SnapMath', 'cast.AsBP Den Snap Math')
    call(g, 'own', SMC + ':GetLocalBounds', {'self': get(g, 'DragComponent')})
    set_value(g, 'center', 'SnapLocalCenter', op(g, 'mid', 'Multiply_VectorFloat', op(g, 'sum', 'Add_VectorVector', 'own.Min', 'own.Max'), B=.5))
    set_value(g, 'extent', 'SnapLocalExtent', op(g, 'half', 'Multiply_VectorFloat', op(g, 'span', 'Subtract_VectorVector', 'own.Max', 'own.Min'), B=.5))
    call(g, 'bounds', KSL + ':GetComponentBounds', {'Component': get(g, 'DragComponent')})
    # GetLocalBounds is const, so a pure node: it is not part of the execution chain.
    g.chain('entry', 'clear', 'valid', 'hasmath', 'center', 'extent')
    g.chain('hasmath.else', 'create', 'cast', 'math', 'center')
    previous = 'extent'
    locals_ = []
    for source in ['Surface', 'Bounds']:
        name = source.lower()
        locals_.append(v(source + 'Cursor', 'int', '0'))
        item, loop, nxt = each(g, name, prop(g, name + 'list', PICKER, source + 'Candidates', get(g, 'Picker')), source + 'Cursor')
        arr(g, name + 'count', 'Length', get(g, 'SnapTargets'))
        call(g, name + 'b', KSL + ':GetComponentBounds', {'Component': item})
        gap = op(g, name + 'gap', 'Subtract_DoubleDouble', op(g, name + 'distance', 'VSize', op(g, name + 'apart', 'Subtract_VectorVector', name + 'b.Origin', 'bounds.Origin')),
                 op(g, name + 'radii', 'Add_DoubleDouble', name + 'b.SphereRadius', 'bounds.SphereRadius'))
        branch(g, name + 'valid', validity(g, name + 'itemvalid', item))
        branch(g, name + 'near', combine(g, name + 'usable', [
            call(g, name + 'other', KML + ':NotEqual_ObjectObject', {'A': item, 'B': get(g, 'DragComponent')}),
            call(g, name + 'room', KML + ':Less_IntInt', {'A': name + 'count.ReturnValue'}, B=LIMIT),
            op(g, name + 'inrange', 'LessEqual_DoubleDouble', gap, B=RANGE)]))
        call(g, name + 'lb', SMC + ':GetLocalBounds', {'self': item})
        scale = call(g, name + 'scale', SCENE + ':K2_GetComponentScale', {'self': item})
        extent = op(g, name + 'extent', 'Multiply_VectorVector', op(g, name + 'halfspan', 'Multiply_VectorFloat', op(g, name + 'span', 'Subtract_VectorVector', name + 'lb.Max', name + 'lb.Min'), B=.5),
                    op(g, name + 'abs', 'Vector_GetAbs', scale))
        call(g, name + 'size', KML + ':BreakVector', {'InVec': extent})
        floorlike = combine(g, name + 'floorlike', [op(g, name + 'wide', 'Greater_DoubleDouble', name + 'size.X', B=FLOOR), op(g, name + 'deep', 'Greater_DoubleDouble', name + 'size.Y', B=FLOOR)])
        branch(g, name + 'floor', floorlike)
        call(g, name + 'rotation', KML + ':BreakRotator', {'InRot': call(g, name + 'rot', SCENE + ':K2_GetComponentRotation', {'self': item})})
        steps = []
        for array, value in [('SnapTargets', item), ('SnapCenters', name + 'b.Origin'), ('SnapExtents', extent), ('SnapYaws', name + 'rotation.Yaw')]:
            arr(g, name + 'add' + array, 'Add', get(g, array))
            g.wire((value, name + 'add' + array + '.NewItem'))
            steps.append(name + 'add' + array)
        g.chain(previous, loop)
        g.chain(loop, name + 'valid', name + 'near', name + 'floor')
        g.chain(name + 'valid.else', nxt)
        g.chain(name + 'floor.else', *steps, nxt)
        g.chain(name + 'floor', nxt)
        g.chain(name + 'near.else', nxt)
        previous = loop + '.else'
    return g.function('BeginSnapDrag', locals=locals_)


def end_snap():
    g = Graph()
    previous = 'entry'
    for array in ['SnapTargets', 'SnapCenters', 'SnapExtents', 'SnapYaws']:
        arr(g, 'clear' + array, 'Clear', get(g, array))
        g.chain(previous, 'clear' + array)
        previous = 'clear' + array
    g.set('inactive', 'SnapActive', 'false')
    g.call('hide', 'self:RefreshSnapGuides')
    g.chain(previous, 'inactive', 'hide')
    return g.function('EndSnapDrag')


def allowed(g, name, base, line, plane, dot):
    """An axis may snap on its own drag kind, or along a gizmo line/plane it lies on."""
    along = op(g, name + 'along', 'GreaterEqual_DoubleDouble', dot, B=.999)
    inside = op(g, name + 'inside', 'LessEqual_DoubleDouble', dot, B=.02)
    return combine(g, name + 'allowed', [base, op(g, name + 'online', 'BooleanAND', line, along), op(g, name + 'onplane', 'BooleanAND', plane, inside)], True)


def frame_axes(g, name, yaw, kinds):
    """Which axes of the yaw frame may snap for the current drag (kinds: surface slide, surface lift, gizmo line, gizmo plane)."""
    horizontal, lift, line, plane = kinds
    cos, sin = op(g, name + 'cos', 'DegCos', yaw), op(g, name + 'sin', 'DegSin', yaw)
    axisx = call(g, name + 'axisx', KML + ':MakeVector', {'X': cos, 'Y': sin}, Z=0)
    axisy = call(g, name + 'axisy', KML + ':MakeVector', {'X': op(g, name + 'negsin', 'Multiply_DoubleDouble', sin, B=-1), 'Y': cos}, Z=0)
    dots = {a: op(g, name + 'dot' + a, 'Abs', op(g, name + 'raw' + a, 'Dot_VectorVector', axis, get(g, 'GizmoDragVector')))
            for a, axis in [('X', axisx), ('Y', axisy)]}
    call(g, name + 'handle', KML + ':BreakVector', {'InVec': get(g, 'GizmoDragVector')})
    dots['Z'] = op(g, name + 'dotZ', 'Abs', name + 'handle.Z')
    return {'X': allowed(g, name + 'x', horizontal, line, plane, dots['X']), 'Y': allowed(g, name + 'y', horizontal, line, plane, dots['Y']),
            'Z': allowed(g, name + 'z', lift, line, plane, dots['Z'])}


def square_to(g, name, yaw, frame_yaw):
    """True when two yaws differ by a multiple of 90 degrees, so their boxes share the frame's axes."""
    turn = op(g, name + 'turn', 'Subtract_DoubleDouble', yaw, frame_yaw)
    c = op(g, name + 'c', 'Abs', op(g, name + 'cos', 'DegCos', turn))
    s = op(g, name + 's', 'Abs', op(g, name + 'sin', 'DegSin', turn))
    return op(g, name + 'square', 'GreaterEqual_DoubleDouble', op(g, name + 'most', 'FMax', c, s), B=.9999)


def snap_range():
    """Snap distance close up; further away, SNAP_PIXELS on screen at the dragged box's depth."""
    g = Graph()
    g.node('self', 'self')
    set_value(g, 'minimum', 'local:Reach', get(g, 'SnapDistance'))
    branch(g, 'pc', validity(g, 'pcvalid', get(g, 'EditorController')))
    manager = prop(g, 'manager', PC, 'PlayerCameraManager', get(g, 'EditorController'))
    branch(g, 'camera', validity(g, 'cameravalid', manager))
    viewport = call(g, 'viewport', '/Script/UMG.WidgetLayoutLibrary:GetViewportSize', {'WorldContextObject': 'self.self'})
    call(g, 'size', KML + ':BreakVector2D', {'InVec': viewport})
    branch(g, 'wide', op(g, 'haswidth', 'Greater_DoubleDouble', 'size.X', B=1))
    depth = op(g, 'depth', 'VSize', op(g, 'apart', 'Subtract_VectorVector', 'entry.Center', call(g, 'eye', CAM + ':GetCameraLocation', {'self': manager})))
    half = op(g, 'halffov', 'Multiply_DoubleDouble', call(g, 'fov', CAM + ':GetFOVAngle', {'self': manager}), B=.5)
    across = op(g, 'across', 'Multiply_DoubleDouble', op(g, 'twice', 'Multiply_DoubleDouble', depth, B=2), op(g, 'tan', 'DegTan', half))
    pixels = op(g, 'pixels', 'Multiply_DoubleDouble', op(g, 'perpixel', 'Divide_DoubleDouble', across, 'size.X'), B=SNAP_PIXELS)
    g.get('current', 'local:Reach')
    set_value(g, 'screen', 'local:Reach', op(g, 'larger', 'FMax', 'current.Reach', pixels))
    g.get('out', 'local:Reach')
    g.wire(('out.Reach', 'result.Range'))
    g.chain('entry', 'minimum', 'pc', 'camera', 'wide', 'screen', 'result')
    for pin in ['pc.else', 'camera.else', 'wide.else']:
        g.chain(pin, 'result')
    return g.function('SnapRange', inputs=[v('Center', 'vector')], outputs=[v('Range', 'double')], locals=[v('Reach', 'double', '8')])


def snap_position():
    """Pass 1: the closest snapping neighbour fixes the frame (its yaw and centre). Pass 2: every neighbour square to
    that frame competes axis by axis, so a prop can sit flush against one and line up with another."""
    g = Graph()
    set_value(g, 'passthrough', 'local:Out', 'entry.Position')
    steps = ['passthrough']
    g.set('inactive', 'SnapActive', 'false')
    steps.append('inactive')
    for var, value in [('local:Best', str(FAR)), *[('local:Best' + a, str(FAR)) for a in 'XYZ'], *[('local:Delta' + a, '0') for a in 'XYZ'],
                       *[('SnapKind' + a, '0') for a in 'XYZ']]:
        name = 'reset' + var.replace('local:', '')
        g.set(name, var, value)
        steps.append(name)
    move = call(g, 'move', KML + ':EqualEqual_IntInt', {'A': get(g, 'DragMode')}, B=1)
    arr(g, 'targets', 'Length', get(g, 'SnapTargets'))
    any_ = call(g, 'any', KML + ':Greater_IntInt', {'A': 'targets.ReturnValue'}, B=0)
    branch(g, 'enabled', combine(g, 'ready', [get(g, 'SnapEnabled'), move, any_, validity(g, 'mathvalid', get(g, 'SnapMath'))]))
    branch(g, 'rig', validity(g, 'rigvalid', get(g, 'EditorRig')))
    branch(g, 'alt', prop(g, 'altheld', RIG, 'bAlt', get(g, 'EditorRig')))
    # Which axes may move: a surface drag slides (X/Y) or lifts (Z); a gizmo handle keeps its line or plane.
    surface, vertical = get(g, 'SurfaceDragging'), get(g, 'SurfaceVertical')
    handle = op(g, 'handle', 'Not_PreBool', surface)
    kinds = (op(g, 'horizontal', 'BooleanAND', surface, op(g, 'flat', 'Not_PreBool', vertical)),
             op(g, 'lift', 'BooleanAND', surface, vertical),
             op(g, 'line', 'BooleanAND', handle, call(g, 'axiskind', KML + ':EqualEqual_IntInt', {'A': get(g, 'GizmoDragKind')}, B=1)),
             op(g, 'plane', 'BooleanAND', handle, call(g, 'planekind', KML + ':EqualEqual_IntInt', {'A': get(g, 'GizmoDragKind')}, B=2)))
    rotation, scale = get(g, 'DragStartRotation'), get(g, 'DragStartScale')
    offset = call(g, 'pivot', KML + ':GreaterGreater_VectorRotator', {'A': op(g, 'scaledcenter', 'Multiply_VectorVector', get(g, 'SnapLocalCenter'), scale), 'B': rotation})
    center = op(g, 'center', 'Add_VectorVector', 'entry.Position', offset)
    extent = op(g, 'extent', 'Multiply_VectorVector', get(g, 'SnapLocalExtent'), op(g, 'scaleabs', 'Vector_GetAbs', scale))
    call(g, 'turn', KML + ':BreakRotator', {'InRot': rotation})
    g.call('range', 'self:SnapRange')
    g.wire((center, 'range.Center'))
    near = op(g, 'near', 'FMax', op(g, 'rangenear', 'Multiply_DoubleDouble', 'range.Range', B=6), B=NEAR)

    # Pass 1: the frame.
    item, loop, nxt = each(g, 'target', get(g, 'SnapTargets'), 'Cursor')
    for array, pin in [('SnapYaws', 'yaw'), ('SnapCenters', 'origin'), ('SnapExtents', 'size')]:
        arr(g, pin, 'Get', get(g, array))
        g.wire(('targeti.Cursor', pin + '.Index'))
    branch(g, 'valid', validity(g, 'targetvalid', item))
    snap_math(g, 'frame', 'FrameBox', {'Center': center, 'Extent': extent, 'Yaw': 'turn.Yaw', 'FrameYaw': 'yaw.Item', 'FrameOrigin': 'origin.Item'})
    allow = frame_axes(g, 'own', 'yaw.Item', kinds)
    snap_math(g, 'boxes', 'SnapBoxes', {'DCenter': 'frame.FrameCenter', 'DExtent': 'frame.FrameExtent', 'TExtent': 'size.Item',
                                         'Distance': 'range.Range', 'Near': near, **{'Allow' + a: allow[a] for a in 'XYZ'}}, TCenter='0,0,0')
    g.get('best', 'local:Best')
    branch(g, 'better', combine(g, 'closer', ['boxes.Found', op(g, 'stronger', 'Less_DoubleDouble', 'boxes.Strength', 'best.Best')]))
    picks = []
    for var, value in [('local:Best', 'boxes.Strength'), ('SnapTarget', item), ('SnapFrameYaw', 'yaw.Item'), ('SnapFrameOrigin', 'origin.Item')]:
        name = 'keep' + var.replace('local:', '')
        set_value(g, name, var, value)
        picks.append(name)
    g.set('active', 'SnapActive', 'true')
    g.chain(loop, 'valid', 'frame', 'boxes', 'better', *picks, 'active', nxt)
    g.chain('better.else', nxt)
    g.chain('valid.else', nxt)
    branch(g, 'framed', get(g, 'SnapActive'))

    # Pass 2: each axis from the closest neighbour square to the frame.
    frame_yaw, frame_origin = get(g, 'SnapFrameYaw'), get(g, 'SnapFrameOrigin')
    snap_math(g, 'dragged', 'FrameBox', {'Center': center, 'Extent': extent, 'Yaw': 'turn.Yaw', 'FrameYaw': frame_yaw, 'FrameOrigin': frame_origin})
    framed = frame_axes(g, 'frame', frame_yaw, kinds)
    item2, loop2, nxt2 = each(g, 'axis', get(g, 'SnapTargets'), 'Cursor2')
    for array, pin in [('SnapYaws', 'yaw2'), ('SnapCenters', 'origin2'), ('SnapExtents', 'size2')]:
        arr(g, pin, 'Get', get(g, array))
        g.wire(('axisi.Cursor2', pin + '.Index'))
    branch(g, 'valid2', combine(g, 'usable2', [validity(g, 'targetvalid2', item2), square_to(g, 'square', 'yaw2.Item', frame_yaw)]))
    snap_math(g, 'target2', 'FrameBox', {'Center': 'origin2.Item', 'Extent': 'size2.Item', 'Yaw': 'yaw2.Item', 'FrameYaw': frame_yaw, 'FrameOrigin': frame_origin})
    snap_math(g, 'boxes2', 'SnapBoxes', {'DCenter': 'dragged.FrameCenter', 'DExtent': 'dragged.FrameExtent', 'TCenter': 'target2.FrameCenter',
                                          'TExtent': 'target2.FrameExtent', 'Distance': 'range.Range', 'Near': near,
                                          **{'Allow' + a: framed[a] for a in 'XYZ'}})
    call(g, 'delta2', KML + ':BreakVector', {'InVec': 'boxes2.Delta'})
    g.chain(loop2, 'valid2', 'target2', 'boxes2')
    previous = 'boxes2'
    for a in 'XYZ':
        g.get('best' + a, 'local:Best' + a)
        size = op(g, 'size' + a, 'Abs', 'delta2.' + a)
        found = call(g, 'found' + a, KML + ':Greater_IntInt', {'A': 'boxes2.Kind' + a}, B=0)
        branch(g, 'better' + a, combine(g, 'closer' + a, [found, op(g, 'smaller' + a, 'Less_DoubleDouble', size, 'best' + a + '.Best' + a)]))
        keeps = []
        for var, value in [('local:Best' + a, size), ('local:Delta' + a, 'delta2.' + a), ('SnapKind' + a, 'boxes2.Kind' + a),
                           ('SnapAxisCenter' + a, 'target2.FrameCenter'), ('SnapAxisExtent' + a, 'target2.FrameExtent')]:
            name = 'keep2' + var.replace('local:', '')
            set_value(g, name, var, value)
            keeps.append(name)
        g.node(a + 'done', 'sequence', outputs=1)
        g.chain(previous, 'better' + a, *keeps, a + 'done')
        g.chain('better' + a + '.else', a + 'done')
        previous = a + 'done.then_0'
    g.chain(previous, nxt2)
    g.chain('valid2.else', nxt2)
    deltas = {}
    for a in 'XYZ':
        g.get('final' + a, 'local:Delta' + a)
        deltas[a] = 'final' + a + '.Delta' + a
    delta = call(g, 'delta', KML + ':MakeVector', deltas)
    world = call(g, 'world', KML + ':GreaterGreater_VectorRotator', {'A': delta, 'B': call(g, 'framerot', KML + ':MakeRotator', {'Yaw': frame_yaw}, Roll=0, Pitch=0)})
    set_value(g, 'keepout', 'local:Out', op(g, 'snapped', 'Add_VectorVector', 'entry.Position', world))
    set_value(g, 'keepcenter', 'SnapDraggedCenter', op(g, 'moved', 'Add_VectorVector', 'dragged.FrameCenter', delta))
    set_value(g, 'keepextent', 'SnapDraggedExtent', 'dragged.FrameExtent')

    g.call('guides', 'self:RefreshSnapGuides')
    g.get('out', 'local:Out')
    g.wire(('out.Out', 'result.Snapped'))
    g.chain('entry', *steps, 'enabled', 'rig', 'alt')
    for pin in ['rig.else', 'alt.else']:
        g.chain(pin, 'range')
    g.chain('range', loop)
    g.chain(loop + '.else', 'framed', 'dragged', loop2)
    g.chain(loop2 + '.else', 'keepout', 'keepcenter', 'keepextent', 'guides')
    g.chain('framed.else', 'guides')
    g.chain('guides', 'result')
    for pin in ['enabled.else', 'alt']:
        g.chain(pin, 'guides')
    return g.function('SnapDragPosition', inputs=[v('Position', 'vector')], outputs=[v('Snapped', 'vector')],
                      locals=[v('Out', 'vector'), v('Best', 'double', str(FAR)), v('Cursor', 'int', '0'), v('Cursor2', 'int', '0'),
                              *[v('Best' + a, 'double', str(FAR)) for a in 'XYZ'], *[v('Delta' + a, 'double', '0') for a in 'XYZ']])


def edge(g, name, kind, low, middle, high):
    """The target coordinate a snap kind lines up with: its minimum (kinds 1, 5, 6), centre (2, 8, 9) or maximum (3, 4, 7)."""
    def any_of(tag, values):
        return combine(g, name + tag, [call(g, name + tag + 'is' + str(k), KML + ':EqualEqual_IntInt', {'A': kind}, B=k) for k in values], True)
    centred = call(g, name + 'midmax', KML + ':SelectFloat', {'A': middle, 'B': high, 'bPickA': any_of('mid', (2, 8, 9))})
    return call(g, name + 'edge', KML + ':SelectFloat', {'A': low, 'B': centred, 'bPickA': any_of('min', (1, 5, 6))})


def refresh_guides():
    g = Graph()
    g.node('self', 'self')
    material = prop(g, 'material', '/DenDesignerGF/Runtime/BP_DenGizmoVisual', 'GizmoMaterial', get(g, 'GizmoVisual'))
    branch(g, 'actor', validity(g, 'actorvalid', get(g, 'SnapGuideActor')))
    method(g, 'hide', GUIDES, 'HideGuides', get(g, 'SnapGuideActor'))
    branch(g, 'show', combine(g, 'showing', [get(g, 'SnapActive'), get(g, 'SnapGuidesEnabled'), validity(g, 'visualvalid', get(g, 'GizmoVisual'))]))
    branch(g, 'materialready', validity(g, 'materialvalid', material))
    method(g, 'clear', GUIDES, 'ClearGuides', get(g, 'SnapGuideActor'))
    # Thicker lines further away keep them visible.
    camera = call(g, 'camera', ACTOR + ':K2_GetActorLocation', {'self': get(g, 'EditorRig')})
    distance = op(g, 'distance', 'VSize', op(g, 'apart', 'Subtract_VectorVector', get(g, 'SnapFrameOrigin'), camera))
    thickness = call(g, 'thickness', KML + ':FClamp', {'Value': op(g, 'scaled', 'Multiply_DoubleDouble', distance, B=.0015)}, Min=.4, Max=4)
    frame = call(g, 'framerot', KML + ':MakeRotator', {'Yaw': get(g, 'SnapFrameYaw')}, Roll=0, Pitch=0)
    call(g, 'dc', KML + ':BreakVector', {'InVec': get(g, 'SnapDraggedCenter')})
    call(g, 'de', KML + ':BreakVector', {'InVec': get(g, 'SnapDraggedExtent')})
    dlo = {a: op(g, 'dmin' + a, 'Subtract_DoubleDouble', 'dc.' + a, 'de.' + a) for a in 'XYZ'}
    dhi = {a: op(g, 'dmax' + a, 'Add_DoubleDouble', 'dc.' + a, 'de.' + a) for a in 'XYZ'}

    def box(axis):
        """Minimum, centre and maximum per axis of the neighbour that snapped `axis`."""
        name = 't' + axis
        call(g, name + 'c', KML + ':BreakVector', {'InVec': get(g, 'SnapAxisCenter' + axis)})
        call(g, name + 'e', KML + ':BreakVector', {'InVec': get(g, 'SnapAxisExtent' + axis)})
        return {a: (op(g, name + 'min' + a, 'Subtract_DoubleDouble', name + 'c.' + a, name + 'e.' + a), name + 'c.' + a,
                    op(g, name + 'max' + a, 'Add_DoubleDouble', name + 'c.' + a, name + 'e.' + a)) for a in 'XYZ'}

    def point(name, x, y, z):
        local = call(g, name, KML + ':MakeVector', {'X': x, 'Y': y, 'Z': z})
        return op(g, name + 'world', 'Add_VectorVector', get(g, 'SnapFrameOrigin'), call(g, name + 'rot', KML + ':GreaterGreater_VectorRotator', {'A': local, 'B': frame}))

    lines = []
    for axis, other in [('X', 'Y'), ('Y', 'X')]:
        t = box(axis)
        # Along the other horizontal axis, across both boxes, at the higher of their bottoms.
        at = edge(g, axis.lower(), get(g, 'SnapKind' + axis), *t[axis])
        start = op(g, axis + 'from', 'Subtract_DoubleDouble', op(g, axis + 'low', 'FMin', t[other][0], dlo[other]), B=MARGIN)
        end = op(g, axis + 'to', 'Add_DoubleDouble', op(g, axis + 'high', 'FMax', t[other][2], dhi[other]), B=MARGIN)
        floor = op(g, axis + 'floor', 'Add_DoubleDouble', op(g, axis + 'bottom', 'FMax', t['Z'][0], dlo['Z']), B=1)
        ends = [(at, start), (at, end)] if axis == 'X' else [(start, at), (end, at)]
        lines.append((axis, [(point(axis.lower() + 'a', *ends[0], floor), point(axis.lower() + 'b', *ends[1], floor))]))
    t = box('Z')
    at = edge(g, 'z', get(g, 'SnapKindZ'), *t['Z'])
    corners = [(t['X'][0], t['Y'][0]), (t['X'][2], t['Y'][0]), (t['X'][2], t['Y'][2]), (t['X'][0], t['Y'][2])]
    lines.append(('Z', [(point('za%d' % i, *corners[i], at), point('zb%d' % i, *corners[(i + 1) % 4], at)) for i in range(4)]))
    previous = 'clear'
    for axis, segments in lines:
        branch(g, 'has' + axis, call(g, 'kind' + axis, KML + ':Greater_IntInt', {'A': get(g, 'SnapKind' + axis)}, B=0))
        g.chain(previous, 'has' + axis)
        node = 'has' + axis
        for i, (start, end) in enumerate(segments):
            name = 'line' + axis + str(i)
            method(g, name, GUIDES, 'AddLine', get(g, 'SnapGuideActor'), {'Start': start, 'End': end, 'Thickness': thickness}, Color=LINE)
            g.chain(node, name)
            node = name
        g.node(axis + 'done', 'sequence', outputs=1)
        g.chain(node, axis + 'done')
        g.chain('has' + axis + '.else', axis + 'done')
        previous = axis + 'done.then_0'
    method(g, 'commit', GUIDES, 'CommitGuides', get(g, 'SnapGuideActor'), {'Material': material})
    g.call('badge', 'self:RefreshSnapBadge')
    g.chain('entry', 'actor', 'show', 'materialready', 'clear')
    g.chain(previous, 'commit', 'badge')
    g.chain('actor.else', 'badge')
    for pin in ['show.else', 'materialready.else']:
        g.chain(pin, 'hide', 'badge')
    return g.function('RefreshSnapGuides')


def refresh_badge():
    """'Flush · <mesh>' (or Aligned / Stacked) beside the cursor while a snap holds."""
    g = Graph()
    g.node('self', 'self')
    branch(g, 'toolbar', validity(g, 'toolbarvalid', get(g, 'Toolbar')))
    badge = widget(g, 'badge', 'Toolbar', 'SnapBadge')
    branch(g, 'show', combine(g, 'showing', [get(g, 'SnapActive'), get(g, 'SnapGuidesEnabled'), validity(g, 'targetvalid', get(g, 'SnapTarget'))]))
    flush = combine(g, 'flush', [call(g, 'flush' + a + str(k), KML + ':EqualEqual_IntInt', {'A': get(g, 'SnapKind' + a)}, B=k) for a in 'XY' for k in (4, 5)], True)
    stacked = call(g, 'stacked', KML + ':Greater_IntInt', {'A': get(g, 'SnapKindZ')}, B=0)
    word = call(g, 'word', KML + ':SelectString', {'B': call(g, 'sideword', KML + ':SelectString', {'bPickA': flush}, A='Flush', B='Aligned'), 'bPickA': stacked}, A='Stacked')
    mesh = prop(g, 'mesh', SMC, 'StaticMesh', get(g, 'SnapTarget'))
    name = call(g, 'name', KSL + ':GetDisplayName', {'Object': mesh})
    caption = call(g, 'caption', STR + 'Concat_StrStr', {'A': call(g, 'prefix', STR + 'Concat_StrStr', {'A': word}, B=' · '), 'B': name})
    text(g, 'label', 'Toolbar', 'SnapBadgeText', value=caption)
    mouse = call(g, 'mouse', '/Script/UMG.WidgetLayoutLibrary:GetMousePositionOnViewport', {'WorldContextObject': 'self.self'})
    slot = call(g, 'slot', '/Script/UMG.WidgetLayoutLibrary:SlotAsCanvasSlot', {'Widget': widget(g, 'slotwidget', 'Toolbar', 'SnapBadge')})
    call(g, 'place', '/Script/UMG.CanvasPanelSlot:SetPosition', {'self': slot, 'InPosition': op(g, 'beside', 'Add_Vector2DVector2D', mouse, B='(X=18,Y=22)')})
    visibility(g, 'visible', badge, 'HitTestInvisible')
    visibility(g, 'hidden', widget(g, 'hidewidget', 'Toolbar', 'SnapBadge'), 'Collapsed')
    g.chain('entry', 'toolbar', 'show', 'label', 'mouse', 'place', 'visible')
    g.chain('show.else', 'hidden')
    return g.function('RefreshSnapBadge')


# Each guide segment is a thin box: corners at the start (0-3) and end (4-7), every face in both windings
# so the overlay material shows it whichever side faces the camera.
FACES = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
PATTERN = [i for a, b, c, d in FACES for i in (a, b, c, a, c, d, a, c, b, a, d, c)]


def add_line():
    g = Graph()
    direction = op(g, 'direction', 'Normal', op(g, 'along', 'Subtract_VectorVector', 'entry.End', 'entry.Start'), Tolerance=1e-6)
    across = op(g, 'across', 'Normal', call(g, 'cross', KML + ':Cross_VectorVector', {'A': direction}, B='0,0,1'), Tolerance=1e-6)
    upright = op(g, 'upright', 'Less_DoubleDouble', op(g, 'acrosslength', 'VSize', across), B=.5)
    u = call(g, 'u', KML + ':SelectVector', {'B': across, 'bPickA': upright}, A='1,0,0')
    w = call(g, 'w', KML + ':Cross_VectorVector', {'A': direction, 'B': u})
    tu = op(g, 'tu', 'Multiply_VectorFloat', u, 'entry.Thickness')
    tw = op(g, 'tw', 'Multiply_VectorFloat', w, 'entry.Thickness')
    arr(g, 'count', 'Length', get(g, 'Vertices'))
    set_value(g, 'base', 'local:Base', 'count.ReturnValue')
    g.get('first', 'local:Base')
    previous = 'base'
    g.chain('entry', 'base')
    signs = [(1, 1), (1, -1), (-1, -1), (-1, 1)]
    for i in range(8):
        su, sw = signs[i % 4]
        point = op(g, 'p%d' % i, 'Add_VectorVector', 'entry.' + ('Start' if i < 4 else 'End'),
                   op(g, 'o%d' % i, 'Add_VectorVector', op(g, 'ou%d' % i, 'Multiply_VectorFloat', tu, B=su), op(g, 'ow%d' % i, 'Multiply_VectorFloat', tw, B=sw)))
        arr(g, 'v%d' % i, 'Add', get(g, 'Vertices'))
        g.wire((point, 'v%d.NewItem' % i))
        arr(g, 'c%d' % i, 'Add', get(g, 'Colors'))
        g.wire(('entry.Color', 'c%d.NewItem' % i))
        g.chain(previous, 'v%d' % i, 'c%d' % i)
        previous = 'c%d' % i
    for i, index in enumerate(PATTERN):
        arr(g, 't%d' % i, 'Add', get(g, 'Triangles'))
        g.wire((call(g, 'i%d' % i, KML + ':Add_IntInt', {'A': 'first.Base'}, B=index), 't%d.NewItem' % i))
        g.chain(previous, 't%d' % i)
        previous = 't%d' % i
    return g.function('AddLine', inputs=[v('Start', 'vector'), v('End', 'vector'), v('Thickness', 'double'), v('Color', 'color')],
                      locals=[v('Base', 'int', '0')])


def guides_spec():
    clear = Graph()
    previous = 'entry'
    for array in ['Vertices', 'Triangles', 'Colors']:
        arr(clear, 'clear' + array, 'Clear', get(clear, array))
        clear.chain(previous, 'clear' + array)
        previous = 'clear' + array
    commit = Graph()
    call(commit, 'section', PMC + ':CreateMeshSection_LinearColor', {'self': get(commit, 'Mesh'), 'Vertices': get(commit, 'Vertices'),
         'Triangles': get(commit, 'Triangles'), 'VertexColors': get(commit, 'Colors')}, SectionIndex=0, bCreateCollision='false', bSRGBConversion='false')
    call(commit, 'material', '/Script/Engine.MeshComponent:SetMaterial', {'self': get(commit, 'Mesh'), 'Material': 'entry.Material'}, ElementIndex=0)
    call(commit, 'show', ACTOR + ':SetActorHiddenInGame', bNewHidden='false')
    commit.chain('entry', 'section', 'material', 'show')
    hide = Graph()
    call(hide, 'wipe', PMC + ':ClearAllMeshSections', {'self': get(hide, 'Mesh')})
    call(hide, 'hide', ACTOR + ':SetActorHiddenInGame', bNewHidden='true')
    hide.chain('entry', 'wipe', 'hide')
    return dict(kind='blueprint', path=GUIDES, parent=ACTOR, defaults={'bHidden': 'true'},
                components=[dict(name='Mesh', **{'class': PMC}, props={'Mobility': 'Movable', 'BodyInstance.CollisionEnabled': 'NoCollision',
                                                                       'CastShadow': 'false', 'bReceivesDecals': 'false'})],
                variables=[v('Vertices', 'vector[]'), v('Triangles', 'int[]'), v('Colors', 'color[]')],
                functions=[clear.function('ClearGuides'), add_line(),
                           commit.function('CommitGuides', inputs=[v('Material', 'object:/Script/Engine.MaterialInterface')]),
                           hide.function('HideGuides')])


def variables():
    return [v('SnapMath', 'object:' + MATH), v('SnapGuideActor', 'object:' + GUIDES), v('SnapEnabled', 'bool', 'true'), v('SnapGuidesEnabled', 'bool', 'true'),
            v('SnapDistance', 'double', '8'), v('SnapActive', 'bool'), v('SnapTarget', 'object:' + SMC),
            v('SnapTargets', 'object:' + SMC + '[]'), v('SnapCenters', 'vector[]'), v('SnapExtents', 'vector[]'), v('SnapYaws', 'double[]'),
            v('SnapLocalCenter', 'vector'), v('SnapLocalExtent', 'vector'), v('SnapFrameYaw', 'double'), v('SnapFrameOrigin', 'vector'),
            v('SnapDraggedCenter', 'vector'), v('SnapDraggedExtent', 'vector'),
            *[v('SnapAxis' + part + a, 'vector') for part in ['Center', 'Extent'] for a in 'XYZ'],
            *[v('SnapKind' + a, 'int') for a in 'XYZ']]


def functions():
    return [begin_snap(), end_snap(), snap_range(), snap_position(), refresh_guides(), refresh_badge()]
