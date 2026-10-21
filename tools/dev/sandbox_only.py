#!/usr/bin/env python3
"""Temporarily expose only ZC Sandbox to UE4SS; preserve the normal Mods tree.

Development helper, never shipped. Both switches require the game closed.
No enabled markers, mod settings, user INIs or original load lists are edited.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import dd

MODS = dd.UE4SS / "Mods"
PARKED = dd.UE4SS / "Mods.DenDesigner.original"
STATE = dd.REPO / "dist/state/sandbox-only-state.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def status():
    return {"active": PARKED.is_dir(), "game_pids": dd.game_pids(),
            "original_mods": str(PARKED if PARKED.is_dir() else MODS),
            "state": str(STATE)}


def enable():
    if dd.game_pids():
        raise RuntimeError("Close the game before switching its mod inventory")
    if PARKED.exists():
        raise RuntimeError("An isolation already exists; inspect status or restore it")
    if not MODS.is_dir() or MODS.is_symlink():
        raise RuntimeError("Expected the original plain Mods directory")
    if not (MODS / "ZCSandbox/dlls/main.dll").is_file():
        raise RuntimeError("ZC Sandbox DLL is missing")
    if (MODS / "ZCSandbox").is_symlink():
        raise RuntimeError("Expected this installation's regular ZCSandbox folder")
    state = {"active": True, "original": str(MODS), "parked": str(PARKED),
             "created_at": time.time(),
             "original_entries": sorted(p.name for p in MODS.iterdir()),
             "load_list_hashes": {name: digest(MODS / name) for name in
                                  ("mods.txt", "mods.json") if (MODS / name).is_file()}}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    MODS.rename(PARKED)
    try:
        MODS.mkdir()
        (MODS / "ZCSandbox").symlink_to(PARKED / "ZCSandbox", target_is_directory=True)
        (MODS / "mods.txt").write_text("ZCSandbox : 1\n")
        (MODS / "mods.json").write_text(
            '[{"mod_name":"ZCSandbox","mod_enabled":true}]\n')
    except BaseException:
        # Keep even a partially created test tree for diagnosis.
        restore()
        raise
    return status()


def restore():
    if dd.game_pids():
        raise RuntimeError("Close the game before restoring its mod inventory")
    if not PARKED.is_dir() or not STATE.is_file():
        raise RuntimeError("No recorded original Mods directory to restore")
    state = json.loads(STATE.read_text())
    if state["original"] != str(MODS) or state["parked"] != str(PARKED):
        raise RuntimeError("Isolation record does not match this installation")
    for name, expected in state["load_list_hashes"].items():
        if digest(PARKED / name) != expected:
            raise RuntimeError("Original load list changed: " + name)
    if sorted(p.name for p in PARKED.iterdir()) != state["original_entries"]:
        raise RuntimeError("Original mod inventory changed while isolated")
    if MODS.exists():
        if MODS.is_symlink():
            raise RuntimeError("Unexpected replacement Mods symlink")
        ended = dd.UE4SS / ("Mods.DenDesigner.sandbox-ended-" + str(time.time_ns()))
        MODS.rename(ended)
        state["test_tree_archived"] = str(ended)
    PARKED.rename(MODS)
    state["active"] = False
    state["restored_at"] = time.time()
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    return status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("enable", "restore", "status"))
    args = parser.parse_args()
    try:
        print(json.dumps({"enable": enable, "restore": restore, "status": status}[args.action](),
                         indent=2))
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, str(exc) + "\n")
