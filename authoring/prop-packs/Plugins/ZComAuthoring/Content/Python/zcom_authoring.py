"""Headless builds from ZComAuthoring JSON specs (run inside the editor: -run=pythonscript).

    import zcom_authoring
    ok = zcom_authoring.build(sorted(pathlib.Path("specs").glob("*.json")))

Specs build in the order given, so list an asset after the assets it references. Every target is
force-deleted first (dependents before dependencies) and rebuilt from scratch, so a rerun gives the
same assets. Each message is logged as "ZCOMAUTH <path>: <message>".
"""
from __future__ import annotations

import json
from pathlib import Path

import unreal

MARKER = "ZCOMAUTH"


def load(paths) -> list[tuple[Path, dict]]:
    return [(Path(p), json.loads(Path(p).read_text(encoding="utf-8"))) for p in paths]


def build(paths, delete_first: bool = True) -> bool:
    specs = load(paths)
    library = unreal.ZComAuthoringLibrary
    if delete_first:
        library.force_delete_assets([spec["path"] for _, spec in reversed(specs)])
    ok = True
    for source, spec in specs:
        report = json.loads(library.build_asset_from_json(json.dumps(spec)))
        for message in report["messages"]:
            unreal.log(f"{MARKER} {spec['path']}: {message}")
        if report["ok"] and unreal.EditorAssetLibrary.save_asset(spec["path"], only_if_is_dirty=False):
            unreal.log(f"{MARKER} built {spec['path']} ({source.name})")
        else:
            unreal.log_error(f"{MARKER} FAILED {spec['path']} ({source.name})")
            ok = False
    return ok


def delete(paths) -> int:
    return unreal.ZComAuthoringLibrary.force_delete_assets([spec["path"] for _, spec in reversed(load(paths))])
