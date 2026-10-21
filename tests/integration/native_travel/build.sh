#!/bin/bash
# Disposable test-only pak; never installed automatically or packaged for users.
set -euo pipefail
cd "$(dirname "$0")/../../.."
repo=$(pwd)
root=${SWZC_ROOT:-/run/media/chats/0c7bd812-03b4-405c-9602-31282b68fd64}
kit=${SWZC_KIT:-"$root/SWZC Merged Kit"}
engine="$root/UnrealEngine/Engine"
project="$kit/SWZeroCompany.uproject"
work="$repo/dist/verification/travel-qa"
name=DenTravelQA
plugin="$work/$name"
export TMPDIR="$root/tmp"
mkdir -p "$plugin" "$TMPDIR" "$work/logs" "$work/out"
cat > "$plugin/$name.uplugin" <<'JSON'
{"FileVersion":3,"Version":1,"VersionName":"test-only","FriendlyName":"Den Travel QA (REMOVE AFTER TEST)","CanContainContent":true,"ExplicitlyLoaded":true,"BuiltInInitialFeatureState":"Active","Plugins":[{"Name":"GameFeatures","Enabled":true},{"Name":"ModularGameplay","Enabled":true},{"Name":"DenDesignerGF","Enabled":true}]}
JSON
[ -e "$kit/Mods/$name" ] || ln -s "$plugin" "$kit/Mods/$name"
[ "$(readlink -f "$kit/Mods/$name")" = "$plugin" ] || { echo 'Unexpected QA plugin path' >&2; exit 1; }
DEN_TRAVEL_REPO="$repo" "$engine/Binaries/Linux/UnrealEditor-Cmd" "$project" \
 -run=pythonscript -script="$repo/tests/integration/native_travel/author.py" -unattended -nop4 -nosplash -NullRHI -stdout -FullStdOutLogOutput -NoCrashDialog \
 > "$work/logs/author.log" 2>&1 || true
rg 'ZCOMAUTH.*(error|warning)|DEN_TRAVEL_QA' "$work/logs/author.log" || true
rg -q 'DEN_TRAVEL_QA_RESULT ok' "$work/logs/author.log" || exit 1
if rg -q 'ZCOMAUTH .*: warning:' "$work/logs/author.log"; then
    echo 'Resolve QA Blueprint warnings before cooking' >&2
    exit 1
fi
NuGetAudit=false "$engine/Build/BatchFiles/RunUAT.sh" -ScriptsForProject="$project" BuildCookRun \
 -project="$project" -nop4 -utf8output -unattended -nocompileeditor -skipbuildeditor \
 -platform=Linux -clientconfig=Shipping -cook -stage -pak -iostore -dlcname=$name -DLCPakPluginFile \
 -basedonreleaseversion=BaseGame -AdditionalCookerOptions="-AllowUncookedAssetReferences" \
 -archive -archivedirectory="$kit/Packaged" > "$work/logs/cook.log" 2>&1
paks="$kit/Packaged/Linux/SWZeroCompany/Mods/$name/Content/Paks/Linux"
for ext in ucas utoc; do cp "$paks/${name}SWZeroCompany-Linux.$ext" "$work/out/${name}_P.$ext"; done
python3 - "$plugin/$name.uplugin" "$work/$name.upluginmanifest" <<'PY'
import sys,json,pathlib
pathlib.Path(sys.argv[2]).write_text(json.dumps({'Contents':[{'File':'../../../SWZeroCompany/Plugins/GameFeatures/DenTravelQA/DenTravelQA.uplugin','Descriptor':json.loads(pathlib.Path(sys.argv[1]).read_text())}]}))
PY
cat > "$work/pak.txt" <<LIST
"$work/$name.upluginmanifest" "../../../SWZeroCompany/Plugins/$name.upluginmanifest" -compress
"$plugin/$name.uplugin" "../../../SWZeroCompany/Plugins/GameFeatures/$name/$name.uplugin" -compress
"$plugin/Saved/Cooked/Linux/SWZeroCompany/Mods/$name/AssetRegistry.bin" "../../../SWZeroCompany/Plugins/GameFeatures/$name/AssetRegistry.bin" -compress
LIST
"$engine/Binaries/Linux/UnrealPak" "$work/out/${name}_P.pak" -create="$work/pak.txt" -platform=Linux > "$work/logs/pak.log" 2>&1
"$engine/Binaries/Linux/UnrealPak" "$work/out/${name}_P.utoc" -List > "$work/logs/contents.log" 2>&1
for asset in DenTravelQA BP_TravelProbe WBP_TravelProbe; do rg -q "/$asset.uasset" "$work/logs/contents.log"; done
(cd "$work/out" && sha256sum *) > "$work/SHA256SUMS"
echo "QA containers ready in $work/out (not installed)"
