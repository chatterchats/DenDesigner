"""Blueprint bounds-snapping math; no loads or world mutation.

Boxes are compared in a target's yaw frame: centre and half extent per axis.
Axis kinds: 0 none, 1 align minimums, 2 align centres, 3 align maximums,
4 flush after (dragged minimum on the target's maximum), 5 flush before
(dragged maximum on the target's minimum), 6/7 dragged centre on the target's
minimum/maximum, 8/9 dragged minimum/maximum on the target's centre. The nearest offset within the snap
distance wins; on equal distance the earlier kind in KINDS wins.
tests/python/snap_math_test.py holds an independent reference model and the fixed cases.
"""
from graph import Graph, variable as v, KML
from runtime import ROOT
from runtime_store import call
from runtime_gizmo_math import op, output

MATH = ROOT + 'BP_DenSnapMath'
AXES = ['X', 'Y', 'Z']
KINDS = [4, 5, 1, 3, 2, 6, 7, 8, 9]
FAR = 1e9  # strength of an axis that found nothing


def axis_snap():
    g = Graph()
    dmid = op(g, 'dmid', 'Multiply_DoubleDouble', op(g, 'dsum', 'Add_DoubleDouble', 'entry.DMin', 'entry.DMax'), B=.5)
    tmid = op(g, 'tmid', 'Multiply_DoubleDouble', op(g, 'tsum', 'Add_DoubleDouble', 'entry.TMin', 'entry.TMax'), B=.5)
    deltas = {4: ('entry.TMax', 'entry.DMin'), 5: ('entry.TMin', 'entry.DMax'), 1: ('entry.TMin', 'entry.DMin'),
              3: ('entry.TMax', 'entry.DMax'), 2: (tmid, dmid), 6: ('entry.TMin', dmid), 7: ('entry.TMax', dmid),
              8: (tmid, 'entry.DMin'), 9: (tmid, 'entry.DMax')}
    best = kind = None
    for k in KINDS:
        delta = op(g, 'delta%d' % k, 'Subtract_DoubleDouble', *deltas[k])
        if best is None:
            best, kind = delta, call(g, 'kind%d' % k, KML + ':SelectInt', A=k, B=0, bPickA='true')
            continue
        closer = op(g, 'closer%d' % k, 'Less_DoubleDouble', op(g, 'abs%d' % k, 'Abs', delta), op(g, 'bestabs%d' % k, 'Abs', best))
        best = call(g, 'best%d' % k, KML + ':SelectFloat', {'A': delta, 'B': best, 'bPickA': closer})
        kind = call(g, 'pick%d' % k, KML + ':SelectInt', {'B': kind, 'bPickA': closer}, A=k)
    found = op(g, 'within', 'LessEqual_DoubleDouble', op(g, 'distance', 'Abs', best), 'entry.Distance')
    output(g, 'Found', found)
    output(g, 'Delta', call(g, 'delta', KML + ':SelectFloat', {'A': best, 'bPickA': found}, B=0))
    output(g, 'Kind', call(g, 'kind', KML + ':SelectInt', {'A': kind, 'bPickA': found}, B=0))
    g.chain('entry', 'result')
    return g.function('AxisSnap', inputs=[v(n, 'double') for n in ['DMin', 'DMax', 'TMin', 'TMax', 'Distance']],
                      outputs=[v('Found', 'bool'), v('Delta', 'double'), v('Kind', 'int')])


def frame_box():
    """A box (world centre, half extent in its own axes, yaw) as centre/extent in another box's yaw frame."""
    g = Graph()
    frame = call(g, 'frame', KML + ':MakeRotator', {'Yaw': 'entry.FrameYaw'}, Roll=0, Pitch=0)
    relative = op(g, 'relative', 'Subtract_VectorVector', 'entry.Center', 'entry.FrameOrigin')
    output(g, 'FrameCenter', call(g, 'unrotate', KML + ':LessLess_VectorRotator', {'A': relative, 'B': frame}))
    turn = op(g, 'turn', 'Subtract_DoubleDouble', 'entry.Yaw', 'entry.FrameYaw')
    c = op(g, 'c', 'Abs', op(g, 'cos', 'DegCos', turn))
    s = op(g, 's', 'Abs', op(g, 'sin', 'DegSin', turn))
    call(g, 'extent', KML + ':BreakVector', {'InVec': 'entry.Extent'})
    def mix(name, a, b):
        return op(g, name, 'Add_DoubleDouble', op(g, name + 'a', 'Multiply_DoubleDouble', a, 'extent.X'), op(g, name + 'b', 'Multiply_DoubleDouble', b, 'extent.Y'))
    output(g, 'FrameExtent', call(g, 'framed', KML + ':MakeVector', {'X': mix('x', c, s), 'Y': mix('y', s, c), 'Z': 'extent.Z'}))
    g.chain('entry', 'result')
    return g.function('FrameBox', inputs=[v('Center', 'vector'), v('Extent', 'vector'), v('Yaw', 'double'),
                                          v('FrameYaw', 'double'), v('FrameOrigin', 'vector')],
                      outputs=[v('FrameCenter', 'vector'), v('FrameExtent', 'vector')])


def snap_boxes():
    """Snap a dragged box to a target box in the same frame, on the allowed axes, if the boxes are near."""
    g = Graph()
    for box in ['D', 'T']:
        call(g, box.lower() + 'c', KML + ':BreakVector', {'InVec': 'entry.' + box + 'Center'})
        call(g, box.lower() + 'e', KML + ':BreakVector', {'InVec': 'entry.' + box + 'Extent'})
    gaps, deltas, strengths, kinds = {}, {}, [], {}
    previous = 'entry'
    for axis in AXES:
        dc, de, tc, te = 'dc.' + axis, 'de.' + axis, 'tc.' + axis, 'te.' + axis
        apart = op(g, 'apart' + axis, 'Abs', op(g, 'offset' + axis, 'Subtract_DoubleDouble', dc, tc))
        gaps[axis] = op(g, 'gap' + axis, 'FMax', op(g, 'clear' + axis, 'Subtract_DoubleDouble', apart, op(g, 'reach' + axis, 'Add_DoubleDouble', de, te)), B=0)
        g.call('snap' + axis, 'self:AxisSnap')
        g.wire((op(g, 'dmin' + axis, 'Subtract_DoubleDouble', dc, de), 'snap' + axis + '.DMin'),
               (op(g, 'dmax' + axis, 'Add_DoubleDouble', dc, de), 'snap' + axis + '.DMax'),
               (op(g, 'tmin' + axis, 'Subtract_DoubleDouble', tc, te), 'snap' + axis + '.TMin'),
               (op(g, 'tmax' + axis, 'Add_DoubleDouble', tc, te), 'snap' + axis + '.TMax'),
               ('entry.Distance', 'snap' + axis + '.Distance'))
        g.chain(previous, 'snap' + axis)
        previous = 'snap' + axis
    near = op(g, 'near', 'LessEqual_DoubleDouble', op(g, 'separation', 'VSize', call(g, 'gaps', KML + ':MakeVector', gaps)), 'entry.Near')
    any_found = None
    for axis in AXES:
        found = op(g, 'found' + axis, 'BooleanAND', 'entry.Allow' + axis, op(g, 'nearfound' + axis, 'BooleanAND', near, 'snap' + axis + '.Found'))
        deltas[axis] = call(g, 'use' + axis, KML + ':SelectFloat', {'A': 'snap' + axis + '.Delta', 'bPickA': found}, B=0)
        strengths.append(call(g, 'strength' + axis, KML + ':SelectFloat', {'A': op(g, 'size' + axis, 'Abs', 'snap' + axis + '.Delta'), 'bPickA': found}, B=FAR))
        output(g, 'Kind' + axis, call(g, 'kind' + axis, KML + ':SelectInt', {'A': 'snap' + axis + '.Kind', 'bPickA': found}, B=0))
        any_found = found if any_found is None else op(g, 'any' + axis, 'BooleanOR', any_found, found)
    output(g, 'Found', any_found)
    output(g, 'Delta', call(g, 'delta', KML + ':MakeVector', deltas))
    output(g, 'Strength', op(g, 'strength', 'FMin', op(g, 'strengthXY', 'FMin', strengths[0], strengths[1]), strengths[2]))
    g.chain(previous, 'result')
    return g.function('SnapBoxes', inputs=[v('DCenter', 'vector'), v('DExtent', 'vector'), v('TCenter', 'vector'), v('TExtent', 'vector'),
                                           v('Distance', 'double'), v('Near', 'double'), v('AllowX', 'bool'), v('AllowY', 'bool'), v('AllowZ', 'bool')],
                      outputs=[v('Found', 'bool'), v('Delta', 'vector'), v('KindX', 'int'), v('KindY', 'int'), v('KindZ', 'int'), v('Strength', 'double')])


def spec():
    return dict(kind='blueprint', path=MATH, parent='/Script/CoreUObject.Object',
                functions=[axis_snap(), frame_box(), snap_boxes()])
