"""Independent reference model of the bounds-snapping math (unreal/specs/runtime_snap_math.py).

The fixture expectations are derived by hand; this model checks they are coherent, and the native
tests check the Blueprint against the same cases.
"""
import json
import math
from pathlib import Path
import unittest

CASES = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/snap_cases.json').read_text())
FAR = 1e9


def axis_snap(dmin, dmax, tmin, tmax, distance):
    dmid, tmid = (dmin + dmax) / 2, (tmin + tmax) / 2
    options = [(tmax - dmin, 4), (tmin - dmax, 5), (tmin - dmin, 1), (tmax - dmax, 3), (tmid - dmid, 2),
               (tmin - dmid, 6), (tmax - dmid, 7), (tmid - dmin, 8), (tmid - dmax, 9)]
    delta, kind = options[0]
    for candidate, candidate_kind in options[1:]:
        if abs(candidate) < abs(delta):
            delta, kind = candidate, candidate_kind
    return (True, delta, kind) if abs(delta) <= distance else (False, 0, 0)


def frame_box(center, extent, yaw, frame_yaw, origin):
    a = math.radians(frame_yaw)
    rx, ry = center[0] - origin[0], center[1] - origin[1]
    local = (math.cos(a) * rx + math.sin(a) * ry, -math.sin(a) * rx + math.cos(a) * ry, center[2] - origin[2])
    t = math.radians(yaw - frame_yaw)
    c, s = abs(math.cos(t)), abs(math.sin(t))
    return local, (c * extent[0] + s * extent[1], s * extent[0] + c * extent[1], extent[2])


def snap_boxes(dc, de, tc, te, distance, near, allow):
    gaps = [max(abs(dc[i] - tc[i]) - (de[i] + te[i]), 0) for i in range(3)]
    close = math.sqrt(sum(gap * gap for gap in gaps)) <= near
    delta, kinds, strength = [0, 0, 0], [0, 0, 0], FAR
    for i in range(3):
        found, d, kind = axis_snap(dc[i] - de[i], dc[i] + de[i], tc[i] - te[i], tc[i] + te[i], distance)
        if allow[i] and close and found:
            delta[i], kinds[i], strength = d, kind, min(strength, abs(d))
    return any(kinds), delta, kinds, strength


class SnapMathTests(unittest.TestCase):
    def test_axis_cases(self):
        for case in CASES['axis']:
            with self.subTest(case['name']):
                self.assertEqual(axis_snap(*case['in']), (case['found'], case['delta'], case['kind']))

    def test_frame_cases(self):
        for case in CASES['frame']:
            with self.subTest(case['name']):
                center, extent = frame_box(case['center'], case['extent'], case['yaw'], case['frame_yaw'], case['origin'])
                for got, want in zip(center + extent, case['frame_center'] + case['frame_extent']):
                    self.assertAlmostEqual(got, want, places=9)

    def test_box_cases(self):
        for case in CASES['boxes']:
            with self.subTest(case['name']):
                found, delta, kinds, strength = snap_boxes(*case['d'], *case['t'], case['distance'], case['near'], case['allow'])
                self.assertEqual((found, delta, kinds, strength), (case['found'], case['delta'], case['kinds'], case['strength']))


if __name__ == '__main__':
    unittest.main()
