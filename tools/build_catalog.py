#!/usr/bin/env python3
"""Builds the editor's mesh catalog (src/ZComDen/Scripts/catalog_data.lua) from the ZCRE game-data dump.

    tools/build_catalog.py [--zcre ../ZCRE] [--report]

1. Lists every StaticMesh in ZCRE's asset registry (data/registry/asset_registry.tsv).
2. Drops what isn't furniture by path and name: destruction pieces, generated mission geometry, LOD and proxy
   meshes, FX, cinematic and lighting helpers, editor meshes.
3. Dumps the rest with ZCRE's zcparse (cached in ZCRE/out/static_meshes; only new meshes are parsed) and reads
   each mesh's bounds and whether it has collision (the editor picks placed meshes without it by their bounds).
4. Writes a flat Lua table: categories (by folder) and items (path, size, flags), loaded the first time the
   catalog opens. Rerun after a game patch.
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "src/ZComDen/Scripts/catalog_data.lua"
BATCH = 400
MIN_SHELF = 4  # smaller shelves merge into "<group>: Props"

# Folders (Lua-free regexes on the package path) that never hold furniture.
SKIP_PATH = re.compile("|".join([
    r"^/(?!Game/|Engine/BasicShapes/)",       # plugins and engine content, except the basic shapes
    r"/__PendingDelete/", r"/_?GENERATED/", r"/GeometryScript", r"/HLOD", r"/_LevelInstances/", r"DEPRECATED",
    r"Blockout",
    r"/Game/Game/(FX|Cinematics|Lighting|UI|Characters|Animations|Audio)/",
    r"Damaged", r"Destroyed", r"Obliterated", r"Destruct", r"_DES\b", r"_DES/", r"/DS_",
    r"Pieces?\b", r"Pieces?_", r"DentPieces", r"Fracture", r"Chunks?\b",
    r"/BlockIn/", r"/Test/", r"/Testing/", r"/Dev/", r"/Developers/", r"/Sandbox/", r"/Prototype",
]), re.IGNORECASE)

# Asset names that aren't real props.
SKIP_NAME = re.compile("|".join([
    r"_LOD\d", r"Impostor", r"Proxy", r"^Combined_", r"PlaneCut", r"^Box_\d", r"_UCX", r"Collision", r"Collider",
    r"Blocker", r"Blockout", r"^BlockMesh", r"Placeholder", r"_Piece", r"Bypass_Piece", r"_Cutout", r"Shadow_?Caster",
    r"^Plane$", r"^Cube$", r"^Sphere$", r"^Cylinder$", r"^Cone$",   # stray copies of the basic shapes
    r"Decal", r"Footprints",                                         # projected on surfaces, no collision
]), re.IGNORECASE)


def pak_path(package):
    """/Game/X/Y -> SWZeroCompany/Content/X/Y.uasset; /Engine/X -> Engine/Content/X.uasset"""
    if package.startswith("/Game/"):
        return "SWZeroCompany/Content/" + package[len("/Game/"):] + ".uasset"
    root, rest = package[1:].split("/", 1)
    return f"{root}/Content/{rest}.uasset"


def dump(zcre, packages, cache):
    """Parses every package not yet in the cache, in exact-path batches."""
    todo = [p for p in packages if not (cache / (pak_path(p)[:-len(".uasset")] + ".json")).exists()]
    print(f"{len(packages)} candidate meshes, {len(todo)} to parse", file=sys.stderr)
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        selector = "^(" + "|".join(re.escape(pak_path(p)) for p in batch) + ")$"
        result = subprocess.run([str(zcre / "bin/zcparse"), "json", selector, str(cache)],
                                capture_output=True, text=True)
        tail = [l for l in result.stdout.splitlines() + result.stderr.splitlines() if "selected" in l]
        print(f"  batch {i // BATCH + 1}: {tail[-1] if tail else result.returncode}", file=sys.stderr)


def read_mesh(path):
    """Returns (extent [x, y, z], origin z, has collision, material slots) or None."""
    try:
        exports = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    mesh = next((e for e in exports if e.get("Type") == "StaticMesh"), None)
    if not mesh:
        return None
    props = mesh.get("Properties", {})
    bounds = props.get("ExtendedBounds") or (mesh.get("RenderData") or {}).get("Bounds")
    if not bounds:
        return None
    ext, origin = bounds.get("BoxExtent"), bounds.get("Origin") or {"Z": 0.0}
    if not ext:
        return None
    body = next((e for e in exports if e.get("Type") == "BodySetup"), None)
    collision = False
    if body:
        bp = body.get("Properties", {})
        geom = bp.get("AggGeom") or {}
        collision = any(geom.get(k) for k in ("SphereElems", "BoxElems", "SphylElems", "ConvexElems", "TaperedCapsuleElems"))
        collision = collision or bp.get("CollisionTraceFlag") == "CTF_UseComplexAsSimple" or "ComplexCollisionMesh" in str(bp)
        # A BodySetup that says nothing else still cooks complex (triangle) collision by default.
        collision = collision or bp.get("CollisionTraceFlag") in (None, "CTF_UseDefault")
    slots = len(props.get("StaticMaterials") or [])
    return [ext.get("X", 0), ext.get("Y", 0), ext.get("Z", 0)], origin.get("Z", 0.0), collision, slots


FACTIONS = {"Universal": "Universal", "Republic": "Republic", "Separatist": "Separatist", "OuterRim": "Outer Rim",
            "Bespin": "Bespin", "Courtsilius": "Courtsilius", "Kafrene": "Kafrene"}


def category(package):
    """A readable shelf for a mesh, from its folder."""
    parts = package.split("/")[1:-1]
    if parts[:2] == ["Engine", "BasicShapes"]:
        return "Basic shapes"
    if parts[1:2] == ["SWAL"]:
        return "Fixtures"
    p = parts[2:] if parts[:2] == ["Game", "Game"] else parts[1:]
    tidy = lambda s: re.sub(r"^(UNI|REP|SEP|OTR|BES|HQ|HUB)_", "", s).replace("_", " ")
    if p[:2] == ["Environments", "Strategy"]:
        rest = [x for x in p[2:] if x not in ("HQ", "Props", "Structure")]
        return "Den: " + (tidy(rest[0]) if rest else "Misc")
    if p[:2] == ["Environments", "Faction"] and len(p) > 2:
        faction = FACTIONS.get(p[2], tidy(p[2]))
        rest = p[3:]
        if rest[:1] == ["Props"] and len(rest) > 1:
            return f"{faction}: {tidy(rest[1])}"
        return f"{faction}: {tidy(rest[0]) if rest else 'Misc'}"
    if p[:1] == ["Environments"] and len(p) > 1:
        return "Environment: " + tidy(p[1])
    if p[:1] == ["Vehicles"] and len(p) > 1:
        return "Vehicles: " + tidy(p[1])
    if p[:1] == ["Weapons"]:
        return "Weapons"
    if p[:1] == ["Maps"] and len(p) > 2:
        return "Missions: " + tidy(p[2])
    return "Other: " + (tidy(p[0]) if p else "Misc")


def lua_string(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zcre", default=str(REPO.parent.parent / "ZCRE"))
    ap.add_argument("--report", action="store_true", help="print what was dropped and why")
    args = ap.parse_args()
    zcre = Path(args.zcre)
    cache = zcre / "out/static_meshes"

    meshes, dropped = [], Counter()
    with open(zcre / "data/registry/asset_registry.tsv") as f:
        next(f)
        for line in f:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 3 or cols[2] != "StaticMesh":
                continue
            package, name = cols[0], cols[1]
            if SKIP_PATH.search(package):
                dropped["folder"] += 1
            elif SKIP_NAME.search(name):
                dropped["name"] += 1
            else:
                meshes.append((package, name))
    dump(zcre, [p for p, _ in meshes], cache)

    shelves, no_collision = defaultdict(list), []
    for package, name in meshes:
        info = read_mesh(cache / (pak_path(package)[:-len(".uasset")] + ".json"))
        if not info:
            dropped["unreadable"] += 1
            continue
        ext, origin_z, collision, slots = info
        size = [round(2 * e) for e in ext]
        basic = package.startswith("/Engine/BasicShapes/")
        if max(size) < 2:
            dropped["tiny"] += 1
        elif max(size) > 5000:
            dropped["huge"] += 1
        else:
            if not collision and not basic:
                no_collision.append(package)
            shelves[category(package)].append((name, f"{package}.{name}", size, 1 if collision or basic else 0))

    # One-off shelves (a folder per prop, as Bespin's are) merge into their group's "Props" shelf.
    for c in [c for c in shelves if len(shelves[c]) < MIN_SHELF and ": " in c]:
        group = c.split(": ", 1)[0] + ": Props"
        if group != c:
            shelves[group].extend(shelves.pop(c))

    lines = ["-- Generated by tools/build_catalog.py from the ZCRE game-data dump; don't edit by hand.",
             "-- items: flat, six values per mesh: object path, width, depth, height (cm), category index,",
             "-- 1 if it has collision (else the editor picks it by its bounds).",
             "return {", "    categories = {"]
    order = sorted(shelves, key=lambda c: (c.startswith(("Missions", "Other", "Vehicles")), c.lower()))
    for c in order:
        lines.append(f"        {{ {lua_string(c)}, {len(shelves[c])} }},")
    lines += ["    },", "    items = {"]
    total = 0
    for index, c in enumerate(order, 1):
        for name, path, size, solid in sorted(shelves[c], key=lambda x: x[0].lower()):
            lines.append(f"        {lua_string(path)}, {size[0]}, {size[1]}, {size[2]}, {index}, {solid},")
            total += 1
    lines += ["    },", "}", ""]
    OUT.write_text("\n".join(lines))
    print(f"wrote {total} meshes in {len(order)} categories to {OUT.relative_to(REPO)} "
          f"({OUT.stat().st_size // 1024} KB); dropped: {dict(dropped)}", file=sys.stderr)
    if args.report:
        print(f"{len(no_collision)} without collision, e.g.:", *sorted(no_collision)[::40], sep="\n  ")
        for c in order:
            print(f"{len(shelves[c]):5d}  {c}")


if __name__ == "__main__":
    main()
