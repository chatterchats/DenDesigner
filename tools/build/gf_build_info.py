#!/usr/bin/env python3
"""Record/verify the exact pak build and its authored inputs before packaging."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = "DenDesignerGF"
CONTAINERS = tuple(PLUGIN + "_P." + ext for ext in ("pak", "ucas", "utoc"))
PAKS = Path("dist/build/runtime/SWZeroCompany/Content/Paks/~mods")
DESCRIPTOR = Path("unreal/DenDesignerGF/DenDesignerGF.uplugin")
REPORT = Path("dist/build/runtime/build-info.json")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    require(path.is_file() and not path.is_symlink(), "Missing/plain-file requirement: " + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(root):
    paths = [DESCRIPTOR, Path("unreal/scripts/build_gf.py"), Path("unreal/scripts/editor_icons.py"),
             Path("tools/build/build_gf.sh"), Path("tools/build/render_icons.sh"), Path("tools/build/gf_build_info.py")]
    for folder, pattern in [("unreal/specs", "*.py"), ("unreal/data", "*.json"),
                            ("unreal/generated/runtime", "*.json"), ("unreal/icons", "*.svg")]:
        paths.extend(p.relative_to(root) for p in sorted((root / folder).glob(pattern)))
    return {p.as_posix(): sha(root / p) for p in sorted(paths)}


def inspect(root):
    descriptor = json.loads((root / DESCRIPTOR).read_text())
    require(not descriptor.get("Modules"), "The pak edition must not contain native modules")
    require(descriptor.get("CanContainContent") and descriptor.get("BuiltInInitialFeatureState") == "Active",
            "Expected an active content Game Feature")
    version = descriptor["VersionName"]
    require(re.fullmatch(r"\d+\.\d+\.\d+(?:-[a-z0-9.]+)?", version), "Invalid standalone version")
    specs = [json.loads(p.read_text()) for folder in ("runtime",)
             for p in sorted((root / "unreal/generated" / folder).glob("*.json"))]
    require(specs, "No authored asset specs")
    expected = {f"../../../SWZeroCompany/Mods/{PLUGIN}/Content/{s['path'].removeprefix('/'+PLUGIN+'/')}.uasset"
                for s in specs}
    expected.add(f"../../../SWZeroCompany/Mods/{PLUGIN}/Content/{PLUGIN}.uasset")
    # Icon textures are imported by build_gf.py rather than authored from specs.
    expected |= {f"../../../SWZeroCompany/Mods/{PLUGIN}/Content/Editor/Icons/T_Icon_{p.stem}.uasset"
                 for p in (root / "unreal/icons").glob("*.svg")}
    require(all(s["path"].startswith("/" + PLUGIN + "/") for s in specs), "Unexpected asset namespace")
    logs = root / "dist/build/runtime-logs"
    entries = lambda text: set(re.findall(r'Display: "([^"]+)" offset:', text))
    require(entries((logs / "content-list.log").read_text()) == expected | {"<ContainerHeader>"},
            "Cooked asset inventory differs from the authored allowlist")
    manifest = (logs / "manifest-list.log").read_text()
    require('mount point "../../../SWZeroCompany/Plugins/"' in manifest, "Unexpected pak mount")
    require(entries(manifest) == {PLUGIN + ".upluginmanifest",
            f"GameFeatures/{PLUGIN}/AssetRegistry.bin", f"GameFeatures/{PLUGIN}/{PLUGIN}.uplugin"},
            "Unexpected plugin-manifest contents")
    author = (logs / "author.log").read_text()
    brain = f"/{PLUGIN}/Runtime/BP_DenRuntimeCoordinator.BP_DenRuntimeCoordinator_C"
    require("DENDESIGNERGF entry " + brain in author and "DENDESIGNERGF_RESULT ok" in author,
            "Build does not prove the selected Game Feature entry point")
    require(not re.search(r"ZCOMAUTH .*: (?:warning|error):", author), "Authoring emitted compile diagnostics")
    require("AutomationTool exiting with ExitCode=0" in (logs / "cook.log").read_text(), "Cook did not succeed")
    sums = {name: digest for digest, name in
            (line.split() for line in (root / "dist/build/runtime/SHA256SUMS").read_text().splitlines())}
    actual = {name: sha(root / PAKS / name) for name in CONTAINERS}
    require(actual == sums, "Container hashes do not match the completed build")
    return {"format": 1, "version": version, "prototype": False, "entry_point": brain,
            "runtime_assets": sum(s["path"].startswith("/" + PLUGIN + "/Runtime/") or
                                  s["path"].startswith("/" + PLUGIN + "/Editor/") for s in specs),
            "cooked_assets": len(expected), "containers": actual, "inputs": inputs(root)}


def verify(root=ROOT):
    report = json.loads((root / REPORT).read_text())
    require(report.get("prototype") is False, "Expected the pak runtime build")
    require(report == inspect(root), "Build inputs changed; rebuild before packaging")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    try:
        if args.record:
            report = inspect(ROOT)
            (ROOT / REPORT).write_text(json.dumps(report, indent=2) + "\n")
        else:
            report = verify()
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, "Build verification failed: " + str(exc) + "\n")
    print(f"Verified {report['version']}: {report['cooked_assets']} cooked assets")


if __name__ == "__main__":
    main()
