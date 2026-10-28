"""Bounds-based edit anchors and origin compensation for rotation and scaling.

The component transform stays the stored pose. An edit anchor is a point in mesh
space; moving the origin by the old/new rotated offset keeps that point fixed.
"""
from graph import Graph, variable as v, KML
from runtime_store import call, branch, STR
from runtime_world import SMC, validity, set_value

PIVOTS = [('centre', 'Centre'), ('bottom', 'Bottom'), ('top', 'Top'), ('origin', 'Original')]


def bounds_pivot():
    g = Graph()
    middle = call(g, 'middle', KML + ':Multiply_VectorFloat', {'A': call(g, 'sum', KML + ':Add_VectorVector', {'A': 'entry.Minimum', 'B': 'entry.Maximum'})}, B=.5)
    for name, source in [('low', 'entry.Minimum'), ('high', 'entry.Maximum'), ('middleparts', middle)]:
        call(g, name, KML + ':BreakVector', {'InVec': source})
    lower = call(g, 'bottom', STR + 'EqualEqual_StrStr', {'A': 'entry.Anchor'}, B='bottom')
    upper = call(g, 'top', STR + 'EqualEqual_StrStr', {'A': 'entry.Anchor'}, B='top')
    z = call(g, 'upperz', KML + ':SelectFloat', {'A': 'high.Z', 'B': 'middleparts.Z', 'bPickA': upper})
    z = call(g, 'height', KML + ':SelectFloat', {'A': 'low.Z', 'B': z, 'bPickA': lower})
    point = call(g, 'point', KML + ':MakeVector', {'X': 'middleparts.X', 'Y': 'middleparts.Y', 'Z': z})
    original = call(g, 'original', STR + 'EqualEqual_StrStr', {'A': 'entry.Anchor'}, B='origin')
    point = call(g, 'choose', KML + ':SelectVector', {'B': point, 'bPickA': original}, A='0,0,0')
    g.wire((point, 'result.Point')); g.chain('entry', 'result')
    return g.function('BoundsEditPivot', inputs=[v('Minimum', 'vector'), v('Maximum', 'vector'), v('Anchor', 'string')], outputs=[v('Point', 'vector')])


def component_pivot():
    g = Graph(); branch(g, 'valid', validity(g, 'exists', 'entry.Component'))
    call(g, 'bounds', SMC + ':GetLocalBounds', {'self': 'entry.Component'})
    g.call('point', 'self:BoundsEditPivot')
    g.wire(('bounds.Min', 'point.Minimum'), ('bounds.Max', 'point.Maximum'), ('entry.Anchor', 'point.Anchor'))
    set_value(g, 'keep', 'local:AnchorPoint', 'point.Point')
    g.get('out', 'local:AnchorPoint'); g.wire(('out.AnchorPoint', 'result.Point'))
    g.chain('entry', 'valid', 'point', 'keep', 'result'); g.chain('valid.else', 'result')
    return g.function('GetComponentEditPivot', inputs=[v('Component', 'object:' + SMC), v('Anchor', 'string')],
                      outputs=[v('Point', 'vector')], locals=[v('AnchorPoint', 'vector', '0,0,0')])


def world_offset(g, name, point, rotation, scale):
    scaled = call(g, name + 'scaled', KML + ':Multiply_VectorVector', {'A': point, 'B': scale})
    return call(g, name + 'rotated', KML + ':GreaterGreater_VectorRotator', {'A': scaled, 'B': rotation})


def anchored_position(g, name, position, rotation, scale, new_rotation, new_scale, point):
    old = world_offset(g, name + 'old', point, rotation, scale)
    new = world_offset(g, name + 'new', point, new_rotation, new_scale)
    delta = call(g, name + 'delta', KML + ':Subtract_VectorVector', {'A': old, 'B': new})
    return call(g, name + 'position', KML + ':Add_VectorVector', {'A': position, 'B': delta})


def functions():
    return [bounds_pivot(), component_pivot()]
