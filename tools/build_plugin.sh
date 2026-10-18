#!/bin/sh
# Author (ZComAuthoring), cook and package Den Designer's kit assets with the merged kit.
#   tools/build_plugin.sh [--set editor] [--author-only] [--install]
# A set with a generator (unreal/specs/<set>.py) is regenerated first. Assets of other sets are removed from
# the plugin's Content, so the pak holds exactly one set.
set -eu
cd "$(dirname "$0")/.."
repo=$(pwd)
root=${SWZC_ROOT:-/run/media/chats/0c7bd812-03b4-405c-9602-31282b68fd64}
kit=${SWZC_KIT:-"$root/SWZC Merged Kit"}
engine="$root/UnrealEngine/Engine"
project="$kit/SWZeroCompany.uproject"
platform=Linux
logs="$repo/dist/plugin-logs"
out="$repo/dist/plugin/SWZeroCompany/Content/Paks/~mods"
set_name=editor author_only=false install=false
while [ $# -gt 0 ]; do
    case "$1" in
        --set) set_name=$2; shift ;;
        --author-only) author_only=true ;;
        --install) install=true ;;
        *) echo "unknown option $1" >&2; exit 2 ;;
    esac
    shift
done
specs="$repo/unreal/specs/$set_name"
[ -f "$specs.py" ] && python3 "$specs.py"
[ -d "$specs" ] || { echo "no spec set $specs" >&2; exit 1; }
content="$repo/unreal/ZComDen/Content/ZComDen"
for dir in "$content"/*/; do
    [ -d "$dir" ] || continue
    folder=$(basename "$dir")
    grep -lq "\"/ZComDen/ZComDen/$folder/" "$specs"/*.json 2>/dev/null || { echo "removing other set's assets: $folder"; rm -rf "$dir"; }
done

mkdir -p "$logs"
[ -f "$project" ] || { echo "SWZC Merged Kit not found: $project" >&2; exit 1; }
[ -d "$kit/Plugins/ZComAuthoring" ] || { echo "ZComAuthoring missing from the kit: rerun SWZCMergedKit/merge.py" >&2; exit 1; }
[ -e "$kit/Mods/ZComDen" ] || ln -s "$repo/unreal/ZComDen" "$kit/Mods/ZComDen"
# The DLC cook reads the base release for the cook platform; the shipped registry is a package list.
mkdir -p "$kit/Releases/BaseGame/$platform"
cp "$kit/Releases/BaseGame/Windows/AssetRegistry.bin" "$kit/Releases/BaseGame/$platform/"

echo "1/3 Authoring assets ($set_name)"
ZCOMDEN_SPECS="$specs" "$engine/Binaries/Linux/UnrealEditor-Cmd" "$project" -run=pythonscript \
    -script="$repo/unreal/scripts/build_assets.py" \
    -unattended -nop4 -nosplash -NullRHI -stdout -FullStdOutLogOutput -NoCrashDialog \
    > "$logs/author.log" 2>&1 || true
grep -E "ZCOMAUTH .*(error|warning|FAILED)" "$logs/author.log" | sed 's/^.*ZCOMAUTH/ZCOMAUTH/' >&2 || true
grep -q "ZCOMDEN_RESULT ok" "$logs/author.log" || { echo "Authoring failed; see $logs/author.log" >&2; exit 1; }
$author_only && { echo "Authored (--author-only)"; exit 0; }

echo "2/3 Cooking and packaging ($platform)"
rm -rf "$kit/Packaged/$platform/SWZeroCompany/Mods/ZComDen"
# NuGetAudit=false: new advisories for UAT's bundled Magick.NET otherwise fail the script build.
NuGetAudit=false "$engine/Build/BatchFiles/RunUAT.sh" -ScriptsForProject="$project" BuildCookRun \
    -project="$project" -nop4 -utf8output -unattended -nocompileeditor -skipbuildeditor \
    -platform=$platform -clientconfig=Shipping -cook -stage -pak -iostore \
    -dlcname=ZComDen -DLCPakPluginFile -basedonreleaseversion=BaseGame \
    -AdditionalCookerOptions="-AllowUncookedAssetReferences" \
    -archive -archivedirectory="$kit/Packaged" > "$logs/cook.log" 2>&1 \
    || { tail -20 "$logs/cook.log" >&2; echo "Cook failed; see $logs/cook.log" >&2; exit 1; }

echo "3/3 Assembling $out"
paks="$kit/Packaged/$platform/SWZeroCompany/Mods/ZComDen/Content/Paks/$platform"
rm -rf "$repo/dist/plugin" && mkdir -p "$out"
for ext in pak ucas utoc; do
    cp "$paks/ZComDenSWZeroCompany-$platform.$ext" "$out/ZComDen_P.$ext"
done
# The remap renames packages (/ZComDen/<rest> -> /Game/<rest>) through the container header's PackageRedirects.
grep -q "Remapping plugin content to game: 'True'" "$logs/cook.log" \
    || { echo "IoStore did not remap the plugin onto /Game; check unreal/ZComDen/Config/DefaultZComDen.ini" >&2; exit 1; }
"$engine/Binaries/Linux/UnrealPak" "$out/ZComDen_P.utoc" -List > "$logs/list.log" 2>&1
missing=0
for spec in "$specs"/*.json; do
    asset=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["path"].split("/",2)[2])' "$spec")
    grep -q "/Content/$asset.uasset\"" "$logs/list.log" || { echo "missing from the container: $asset" >&2; missing=1; }
done
[ $missing -eq 0 ] || { echo "see $logs/list.log" >&2; exit 1; }
( cd "$out" && sha256sum ZComDen_P.* ) > "$repo/dist/plugin/SHA256SUMS"
cat "$repo/dist/plugin/SHA256SUMS"

if $install; then
    game=${SWZC_GAME:-$(cat "$kit/GameInstallDirectory.txt")}
    target="$game/SWZeroCompany/Content/Paks/~mods"
    mkdir -p "$target" && rm -f "$target"/ZComDen_P.* && cp "$out"/ZComDen_P.* "$target/"
    echo "Installed: $target/ZComDen_P.{pak,ucas,utoc}"
fi
