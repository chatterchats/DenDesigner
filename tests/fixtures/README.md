# Reference fixtures

`gizmo_pick.json` freezes 360 deterministic aimed rays (seed 4136) and their expected handle results
from the verified earlier gizmo implementation. It covers move, rotation, local scaling, planes,
uniform scaling and near misses. There are 161 hits. Native Blueprint tests load these values directly;
no Lua runtime or old mod source is needed. Do not regenerate the expected values from code under test.
