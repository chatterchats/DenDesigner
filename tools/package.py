#!/usr/bin/env python3
"""Builds the release zip from the repo (never from the live mod folder).

The zip mirrors the game's SWZeroCompany folder, so installing is one extract:
  Binaries/Win64/ue4ss/Mods/ZComDen/    the mod's player files (src/ZComDen, minus logs and MXM values)
  Content/Paks/~mods/ZComDen_P.*        the kit pak (tools/build_plugin.sh), checked against its SHA256SUMS
Development tools (tools/, probes/, unreal/) never ship.

    tools/package.py      -> dist/ZComDenDesigner-<version>.zip (+ .sha256)
"""
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "ZComDen"
SCRIPTS = SOURCE / "Scripts"
PAKS = ROOT / "dist" / "plugin" / "SWZeroCompany" / "Content" / "Paks" / "~mods"
MOD_ROOT = "Binaries/Win64/ue4ss/Mods/ZComDen"
REQUIRE = re.compile(r'require(?:\(|, )"(\w+)"')  # require("x") and pcall(require, "x")

version = json.loads((SOURCE / "modinfo.json").read_text())["version"]
assert re.fullmatch(r"\d+\.\d+\.\d+", version), "bad version in modinfo.json"
assert json.loads((SOURCE / "zcom-mod.json").read_text())["version"] == version, "zcom-mod.json version"
assert f'local VERSION = "{version}"' in (SCRIPTS / "main.lua").read_text(), "main.lua VERSION"
assert f'version = "{version}"' in (SOURCE / "MXM" / "settings.lua").read_text(), "MXM settings version"
assert f"Den Designer v{version}" in (SOURCE / "README.md").read_text(), "README title version"


def scripts():
    """Every script, each reachable from main.lua through require() (or main.lua's module list)."""
    mods = {p.stem: p for p in SCRIPTS.glob("*.lua")}
    listed = set(re.findall(r'"(\w+)"', re.search(r"local MODULES = \{(.*?)\}", (SCRIPTS / "main.lua").read_text(),
                                                   re.S).group(1)))
    seen, pending = set(), ["main"]
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        for ref in REQUIRE.findall(mods[name].read_text()):
            assert ref in mods, f"{name}.lua needs the missing {ref}.lua"
            pending.append(ref)
    assert seen == set(mods), f"scripts nothing requires: {sorted(set(mods) - seen)}"
    assert listed == set(mods) - {"main"}, f"main.lua's module list is out of date: {sorted(listed ^ (set(mods) - {'main'}))}"
    return sorted(mods.values())


def paks():
    sums = dict(reversed(line.split()) for line in (ROOT / "dist/plugin/SHA256SUMS").read_text().splitlines())
    out = {}
    for ext in ("pak", "ucas", "utoc"):
        path = PAKS / f"ZComDen_P.{ext}"
        assert path.is_file(), "build the kit pak first: tools/build_plugin.sh"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sums[path.name], f"{path.name} doesn't match SHA256SUMS"
        out[f"Content/Paks/~mods/{path.name}"] = path
    return out


def main():
    files = [SOURCE / leaf for leaf in ("enabled.txt", "modinfo.json", "zcom-mod.json", "README.md", "MXM/settings.lua")]
    files += scripts()
    assert all(p.is_file() and not p.is_symlink() for p in files)
    entries = {f"{MOD_ROOT}/" + p.relative_to(SOURCE).as_posix(): p for p in files}
    entries[f"{MOD_ROOT}/LICENSE"] = ROOT / "LICENSE"
    entries[f"{MOD_ROOT}/CREDITS.md"] = ROOT / "CREDITS.md"
    entries.update(paks())
    assert not any(name.endswith((".log", "values.lua", ".draft.json")) for name in entries)
    output = ROOT / "dist" / f"ZComDenDesigner-{version}.zip"
    output.parent.mkdir(exist_ok=True)
    if output.exists():
        # A released version is immutable: same version, same bytes, or bump it.
        with zipfile.ZipFile(output) as existing:
            same = set(existing.namelist()) == set(entries) and all(
                existing.read(name) == source.read_bytes() for name, source in entries.items())
        assert same, f"{output.name} already exists with different contents; bump the version"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, source in sorted(entries.items()):
            archive.write(source, name)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(entries)
        for name, source in entries.items():
            assert archive.read(name) == source.read_bytes(), name
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n")
    print(f"Verified {len(entries)} files: {output} ({output.stat().st_size // 1024} KB)")
    print(f"SHA256: {digest}")


if __name__ == "__main__":
    main()
