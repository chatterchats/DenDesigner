#!/bin/bash
# Pak-only Game Feature, own manifest, no runtime DLLs or Lua.
set -euo pipefail
cd "$(dirname "$0")/.."
repo=$(pwd)
root=${SWZC_ROOT:-/run/media/chats/0c7bd812-03b4-405c-9602-31282b68fd64}
kit=${SWZC_KIT:-"$root/SWZC Merged Kit"}
engine="$root/UnrealEngine/Engine"
project="$kit/SWZeroCompany.uproject"
name=DenDesignerGF
platform=Linux
logs="$repo/dist/gf-logs"
out="$repo/dist/gf/SWZeroCompany/Content/Paks/~mods"
work="$repo/dist/gf-work"
author_only=false
install=false
for arg in "$@"; do
    case "$arg" in
        --author-only) author_only=true ;;
        --install) install=true ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done
export TMPDIR="$root/tmp"
mkdir -p "$logs" "$TMPDIR"
[ -f "$project" ] || { echo "Merged Kit not found" >&2; exit 1; }
[ -d "$kit/Plugins/ZComAuthoring" ] || { echo "Regenerate the kit with ZComAuthoring first" >&2; exit 1; }
[ -e "$kit/Mods/$name" ] || ln -s "$repo/unreal/$name" "$kit/Mods/$name"
[ "$(readlink -f "$kit/Mods/$name")" = "$repo/unreal/$name" ] || { echo "Unexpected Game Feature plugin path" >&2; exit 1; }
mkdir -p "$kit/Releases/BaseGame/$platform"
cp "$kit/Releases/BaseGame/Windows/AssetRegistry.bin" "$kit/Releases/BaseGame/$platform/"

echo "1/3 Authoring Blueprint runtime and UI"
python3 -I "$repo/unreal/specs/runtime.py"
DENDESIGNERGF_RUNTIME_SPECS="$repo/unreal/specs/runtime" \
    "$engine/Binaries/Linux/UnrealEditor-Cmd" "$project" \
    -run=pythonscript -script="$repo/unreal/scripts/build_gf.py" \
    -unattended -nop4 -nosplash -NullRHI -stdout -FullStdOutLogOutput -NoCrashDialog \
    > "$logs/author.log" 2>&1 || true
grep -E "ZCOMAUTH .*(error|warning|FAILED)|DENDESIGNERGF" "$logs/author.log" || true
grep -q "DENDESIGNERGF_RESULT ok" "$logs/author.log" || { echo "Authoring failed: $logs/author.log"; exit 1; }
if grep -q 'ZCOMAUTH .*: warning:' "$logs/author.log"; then
    echo "Blueprint compile warnings must be resolved before cooking." >&2
    exit 1
fi
$author_only && exit 0

echo "2/3 Cooking Blueprint-only plugin"
rm -rf "$kit/Packaged/$platform/SWZeroCompany/Mods/$name" "$repo/unreal/$name/Saved/Cooked"
NuGetAudit=false "$engine/Build/BatchFiles/RunUAT.sh" -ScriptsForProject="$project" BuildCookRun \
    -project="$project" -nop4 -utf8output -unattended -nocompileeditor -skipbuildeditor \
    -platform=$platform -clientconfig=Shipping -cook -stage -pak -iostore \
    -dlcname=$name -DLCPakPluginFile -basedonreleaseversion=BaseGame \
    -AdditionalCookerOptions="-AllowUncookedAssetReferences" \
    -archive -archivedirectory="$kit/Packaged" > "$logs/cook.log" 2>&1 \
    || { tail -25 "$logs/cook.log"; exit 1; }

echo "3/3 Assembling own-manifest package"
paks="$kit/Packaged/$platform/SWZeroCompany/Mods/$name/Content/Paks/$platform"
registry="$repo/unreal/$name/Saved/Cooked/$platform/SWZeroCompany/Mods/$name/AssetRegistry.bin"
test -f "$registry"
mkdir -p "$out" "$work"
for ext in ucas utoc; do cp "$paks/${name}SWZeroCompany-$platform.$ext" "$out/${name}_P.$ext"; done
python3 -I - "$repo/unreal/$name/$name.uplugin" "$work/$name.upluginmanifest" "$name" <<'PY'
import json, pathlib, sys
descriptor, output, name = sys.argv[1:]
data = {"Contents": [{"File": f"../../../SWZeroCompany/Plugins/GameFeatures/{name}/{name}.uplugin",
                      "Descriptor": json.loads(pathlib.Path(descriptor).read_text())}]}
pathlib.Path(output).write_text(json.dumps(data, indent=2) + "\n")
PY
plugin_dir="../../../SWZeroCompany/Plugins/GameFeatures/$name"
cat > "$work/pak.txt" <<LIST
"$work/$name.upluginmanifest" "../../../SWZeroCompany/Plugins/$name.upluginmanifest" -compress
"$repo/unreal/$name/$name.uplugin" "$plugin_dir/$name.uplugin" -compress
"$registry" "$plugin_dir/AssetRegistry.bin" -compress
LIST
"$engine/Binaries/Linux/UnrealPak" "$out/${name}_P.pak" -create="$work/pak.txt" -platform=$platform \
    -compressionformats=Oodle -compresslevel=4 -compressmethod=Kraken > "$logs/pak.log" 2>&1
"$engine/Binaries/Linux/UnrealPak" "$out/${name}_P.pak" -List > "$logs/manifest-list.log" 2>&1
"$engine/Binaries/Linux/UnrealPak" "$out/${name}_P.utoc" -List > "$logs/content-list.log" 2>&1
grep -q 'mount point "../../../SWZeroCompany/Plugins/"' "$logs/manifest-list.log"
grep -q "\"$name.upluginmanifest\"" "$logs/manifest-list.log"
! grep -q '"SWZeroCompany.upluginmanifest"' "$logs/manifest-list.log"
for asset in DenDesignerGF; do
    grep -q "/$asset.uasset\"" "$logs/content-list.log" || { echo "Missing asset: $asset"; exit 1; }
done
# Check every generated runtime/UI asset, including mapping actions and recycled
# list widgets. A new editor module must not silently fall out of the package.
python3 -I - "$repo/unreal/specs/runtime" "$logs/content-list.log" <<'PY'
import json, pathlib, sys
specs = sorted(pathlib.Path(sys.argv[1]).glob("*.json"))
listing = pathlib.Path(sys.argv[2]).read_text()
assert specs, "No generated native runtime specs"
missing = []
for source in specs:
    path = json.loads(source.read_text())["path"]
    assert path.startswith("/DenDesignerGF/"), path
    asset = path.removeprefix("/DenDesignerGF/")
    if f'/{asset}.uasset"' not in listing:
        missing.append(path)
assert not missing, "Missing native assets: " + ", ".join(missing)
print(f"Verified {len(specs)} native runtime/UI assets in the container")
PY
(cd "$out" && sha256sum "${name}_P".*) > "$repo/dist/gf/SHA256SUMS"
cat "$repo/dist/gf/SHA256SUMS"
python3 "$repo/tools/gf_build_info.py" --record
if $install; then
    # Verify again immediately before mutation, even if the game started during the cook.
    python3 -I - "$repo/tools" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import dd
if dd.game_pids():
    sys.exit("Refusing installation: game is running. Close it before installing paks.")
PY
    game=${SWZC_GAME:-$(cat "$kit/GameInstallDirectory.txt")}
    target="$game/SWZeroCompany/Content/Paks/~mods"
    mkdir -p "$target"
    cp "$out/${name}_P."{pak,ucas,utoc} "$target/"
    echo "Installed $name Game Feature"
fi
