#!/usr/bin/env python3
"""Preview or install a staged Den Designer JSON migration.

python install_migration.py --migration /path/to/staged-import --saved /path/to/SWZeroCompany/Saved
Add --apply to install after reviewing the preview. Close the game first.
Uses Python 3.10+ only; never overwrites an existing native save or a source JSON.
"""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import uuid

from den_save import Codec, MAX_BYTES
from migrate_layouts import convert, parse_json, preset_name, require, LAYOUT, LIBRARY

NATIVE = Path("SaveGames/ZComDen/Native/v1")
FILE = re.compile(r"(home|campaign-[0-9A-F]{32}|presets)-(layout|draft)-([0-5])\.sav")
HASH = re.compile(r"[0-9a-f]{64}")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def relative(name):
    require(isinstance(name, str) and name and "\\" not in name and ":" not in name,
            "Invalid migration path")
    p = PurePosixPath(name)
    require(not p.is_absolute() and all(part not in ("", ".", "..") for part in name.split("/")),
            "Migration paths must stay inside the staging folder")
    return p


def plain_path(root, name):
    p = root
    for part in relative(name).parts:
        p = p / part
        require(not p.is_symlink(), "Symlinks are not accepted: " + str(p))
    return p


def read_checked(root, name, record):
    p = plain_path(root, name)
    require(p.is_file() and p.stat().st_size <= MAX_BYTES, "Missing or oversized file: " + str(p))
    require(isinstance(record, dict) and isinstance(record.get("sha256"), str)
            and HASH.fullmatch(record["sha256"]), "Missing SHA256 for " + name)
    data = p.read_bytes()
    require(sha(data) == record["sha256"], "Hash mismatch: " + name)
    return data


def load_bundle(migration):
    root = Path(migration).resolve(strict=True)
    require(root.is_dir(), "Migration must be a staging directory")
    manifest_path = plain_path(root, "migration.json")
    require(manifest_path.is_file() and manifest_path.stat().st_size <= MAX_BYTES,
            "Missing or oversized migration.json")
    manifest = parse_json(manifest_path.read_bytes(), "migration.json")
    require(isinstance(manifest, dict) and type(manifest.get("format")) is int
            and manifest["format"] == 1, "Unsupported migration manifest")
    originals, saves = manifest.get("originals"), manifest.get("saves")
    require(isinstance(originals, dict) and originals and isinstance(saves, dict) and saves,
            "Migration must contain originals and converted saves")
    original_data = {}
    for name, record in originals.items():
        relative(name)
        data = read_checked(root, "originals/" + name, record)
        require(record.get("bytes") == len(data), "Original size mismatch: " + name)
        original_data[name] = data
    require(len({name.casefold() for name in originals}) == len(originals),
            "Original paths collide ignoring case")
    codec = Codec()
    result = {}
    for name, record in saves.items():
        match = FILE.fullmatch(name)
        require(match is not None, "Unexpected native filename: " + name)
        key, channel, bank = match.groups()
        require(key != "campaign-" + "0" * 32, "Zero campaign identity")
        draft = channel == "draft"
        require(not draft or (key != "presets" and int(bank) < 2), "Invalid draft bank: " + name)
        data = read_checked(root, (NATIVE / name).as_posix(), record)
        cls, doc = codec.decode(data)
        require(cls == (LIBRARY if key == "presets" else LAYOUT), "Wrong native class: " + name)
        revision = doc["Revision"]
        require(type(revision) is int and revision > 0 and record.get("revision") == revision
                and (revision - 1) % (2 if draft else 6) == int(bank), "Invalid revision/bank: " + name)
        require(doc["StorageKey"] == key and doc["IsDraft"] == draft
                and record.get("draft") == draft, "Wrong scope/channel: " + name)
        require(doc["EntryCount"] == len(doc["Entries"]) == record.get("entries"), "Entry count mismatch: " + name)
        require(doc["ContentID"] and doc["WriteCompleteID"] == doc["ContentID"],
                "Incomplete native save: " + name)
        uuid.UUID(doc["ContentID"])
        require(doc["DraftBaseRevision"] == 0 and doc["DraftBaseID"] == "",
                "Legacy migrations must not invent a draft baseline")
        source = record.get("source")
        require(isinstance(source, str) and source in original_data, "Missing source original for " + name)
        if key == "presets":
            require(doc["Scope"] == "preset-library", "Wrong preset scope")
            sources = record.get("sources")
            require(isinstance(sources, list) and sources and all(isinstance(s, str) for s in sources)
                    and sources == sorted(set(sources))
                    and source == sources[0], "Invalid preset source list")
            entries = []
            for item in sources:
                require(item in original_data and item.startswith("presets/") and item.endswith(".json")
                        and len(relative(item).parts) == 2 and item != "presets/index.json",
                        "Invalid preset original")
                entries.append(dict(convert(parse_json(original_data[item], item)),
                                    Name=preset_name(PurePosixPath(item).stem)))
            expected = {"Entries": entries}
        else:
            campaign = key.removeprefix("campaign-") if key.startswith("campaign-") else ""
            require(doc["Scope"] == ("campaign" if campaign else "home")
                    and doc["CampaignID"] == campaign and doc["Enabled"], "Wrong layout identity: " + name)
            canonical = ("campaigns/" + campaign if campaign else "home") + (".draft.json" if draft else ".json")
            backups = {f"backups/{key}.{n}.json".casefold() for n in range(1, 6)} if not draft else set()
            require(source.casefold() == canonical.casefold() or source.casefold() in backups,
                    "Source original belongs to a different layout: " + name)
            expected = convert(parse_json(original_data[source], source))
        # Reconstruct the payload from the preserved originals, including omitted
        # Blueprint defaults. A changed manifest hash cannot conceal a wrong import.
        normalized = codec.decode(codec.encode(cls, expected))[1]
        require(doc["Entries"] == normalized["Entries"] and
                (key == "presets" or doc["GameVersion"] == normalized["GameVersion"]),
                "Converted data differs from preserved JSON: " + name)
        result[name] = {"data": data, "sha256": sha(data), "key": key,
                        "revision": revision, "draft": draft}
    folder = plain_path(root, NATIVE.as_posix())
    require({p.name for p in folder.iterdir()} == set(saves), "Unlisted files in staged native directory")
    return root, result


def game_running():
    if os.name == "nt":
        output = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SWZeroCompany.exe", "/FO", "CSV", "/NH"],
                                check=True, capture_output=True, text=True).stdout
        return any(row and row[0].casefold() == "swzerocompany.exe"
                   for row in csv.reader(io.StringIO(output)))
    require(Path("/proc").is_dir(), "Cannot check the game process on this OS; installation is unavailable")
    for p in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            args = p.read_bytes().split(b"\0")
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            # Other users' protected processes cannot be this user's Wine game.
            if p.parent.stat().st_uid != os.getuid():
                continue
            raise
        if any(arg.replace(b"\\", b"/").rsplit(b"/", 1)[-1].lower() == b"swzerocompany.exe" for arg in args):
            return True
    return False


def destination(saved):
    root = Path(saved).resolve(strict=True)
    require(root.is_dir() and root.name.casefold() == "saved"
            and (root / "SaveGames").is_dir(), "Choose SWZeroCompany's existing Saved folder")
    target = plain_path(root, NATIVE.as_posix())
    require(not target.exists() or target.is_dir(), "Native destination is not a directory")
    return target


def inspect_destination(target, files):
    pending, identical = [], []
    keys = {item["key"] for item in files.values()}
    existing = list(target.iterdir()) if target.exists() else []
    # Case-insensitive checks match Windows and catch unfamiliar bank names too.
    for p in existing:
        if not any(p.name.casefold().startswith(key.casefold() + "-") for key in keys):
            continue
        require(not p.is_symlink() and p.is_file() and p.name in files,
                "Native layout already exists: " + str(p) + ". Nothing will be overwritten.")
        require(p.stat().st_size <= MAX_BYTES and sha(p.read_bytes()) == files[p.name]["sha256"],
                "Native layout differs: " + str(p) + ". Keep both versions; automatic merging is not supported.")
    for name in sorted(files):
        p = target / name
        require(not p.is_symlink(), "Destination is a symlink: " + str(p))
        (identical if p.exists() else pending).append(name)
    return pending, identical


def install(migration, saved, apply=False):
    source, files = load_bundle(migration)
    target = destination(saved)
    require(not source.is_relative_to(target) and not target.is_relative_to(source),
            "Migration staging must be outside the native save directory")
    pending, identical = inspect_destination(target, files)
    report = {"destination": str(target), "install": pending, "already_identical": identical,
              "applied": False, "source_originals_preserved": True}
    if not apply:
        return report
    require(not game_running(), "Close Star Wars Zero Company before installing")
    if not pending:
        report["applied"] = True
        return report
    target.parent.mkdir(parents=True, exist_ok=True)
    created = []
    with tempfile.TemporaryDirectory(prefix=".den-import-", dir=target.parent) as work:
        work = Path(work)
        for name in pending:
            with (work / name).open("xb") as f:
                f.write(files[name]["data"])
                f.flush()
                os.fsync(f.fileno())
        # Recheck after staging, immediately before making any bank visible.
        require(not game_running(), "Game started during staging; no saves installed")
        require(destination(saved) == target, "Destination changed during staging")
        require(inspect_destination(target, files) == (pending, identical),
                "Native saves changed during staging; preview again")
        target.mkdir(exist_ok=True)
        try:
            # Latest canonical generation first. A sudden interruption can omit
            # earlier backups, but cannot make an older backup the current layout.
            order = sorted(pending, key=lambda n: (files[n]["draft"], -files[n]["revision"], n))
            for name in order:
                # Both paths are on the same volume. link is atomic and refuses
                # an existing path; unlike replace(), it can never overwrite it.
                os.link(work / name, target / name)
                created.append(name)
                require(sha((target / name).read_bytes()) == files[name]["sha256"],
                        "Installed hash mismatch: " + name)
        except BaseException:
            for name in reversed(created):
                p = target / name
                if p.is_file() and not p.is_symlink() and sha(p.read_bytes()) == files[name]["sha256"]:
                    p.unlink()
            raise
    report["applied"] = True
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--migration", type=Path, required=True)
    default = Path(os.environ["LOCALAPPDATA"]) / "SWZeroCompany/Saved" if os.environ.get("LOCALAPPDATA") else None
    parser.add_argument("--saved", type=Path, default=default, required=default is None)
    parser.add_argument("--apply", action="store_true", help="Install the previewed saves; the game must be closed")
    args = parser.parse_args()
    try:
        report = install(args.migration, args.saved, args.apply)
    except (ValueError, OSError, UnicodeError, subprocess.SubprocessError) as exc:
        parser.exit(1, "Installation stopped: " + str(exc) + "\n")
    print(json.dumps(report, indent=2))
    print("Original JSON and staged backups are unchanged.")
    if not args.apply:
        print("Preview only. Close the game and repeat with --apply to install.")


if __name__ == "__main__":
    main()
