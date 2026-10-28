#!/bin/bash
# Build an independent, content-only pack with its own manifest. Never installs it.
set -euo pipefail
cd "$(dirname "$0")/../.."
repo=$(pwd)
folder=$(realpath "${1:?Usage: build_prop_pack.sh <plugin-folder> [--sample-art]}")
[ "$#" -le 2 ] || { echo 'Too many arguments' >&2;exit 2; }
case "${2:-}" in ""|--sample-art) ;; *) echo 'Unknown option' >&2;exit 2 ;; esac
kit=${SWZC_KIT:?Set SWZC_KIT to your SDK or base-modkit project directory}
engine=${SWZC_ENGINE:?Set SWZC_ENGINE to your matching UnrealEngine/Engine directory}
if [ "${2:-}" = '--sample-art' ] && [ ! -f "$repo/authoring/prop-packs/example/assets/materials.json" ]; then
    echo 'Sample art is local-only and excluded from Git. Import your own assets and omit --sample-art; see authoring/prop-packs/README.md.' >&2
    exit 1
fi
python3 tools/prop_packs/prop_pack.py "$folder/Authoring/pack.json"
name=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["plugin"])' "$folder/Authoring/pack.json")
# A pack may be an ordinary editor-mounted plugin in SDK/base-kit projects.
if [[ "$folder" == "$(realpath "$kit")/Plugins/"* || "$folder" == "$(realpath "$kit")/Mods/"* ]]; then
    :
else
    mkdir -p "$kit/Mods"
    [ -e "$kit/Mods/$name" ] || ln -s "$folder" "$kit/Mods/$name"
    [ "$(readlink -f "$kit/Mods/$name")" = "$folder" ] || { echo 'Conflicting kit plugin path'; exit 1; }
fi
build_root=${DEN_PROP_PACK_BUILD_ROOT:-"$repo/dist/build/prop-packs/$name"}
logs="$build_root/logs";out="$build_root/SWZeroCompany/Content/Paks/~mods";work="$build_root/work"
mkdir -p "$logs" "$out" "$work"
export TMPDIR=${TMPDIR:-/tmp}
export DEN_PROP_PACK="$folder"
# The shipped BaseGame registry is platform independent; the cooker expects its target directory.
if [ ! -f "$kit/Releases/BaseGame/Linux/AssetRegistry.bin" ]; then
    [ -f "$kit/Releases/BaseGame/Windows/AssetRegistry.bin" ] || { echo 'Missing BaseGame DLC registry; see authoring/prop-packs/kit-compatibility.md' >&2;exit 1; }
    mkdir -p "$kit/Releases/BaseGame/Linux"
    cp "$kit/Releases/BaseGame/Windows/AssetRegistry.bin" "$kit/Releases/BaseGame/Linux/AssetRegistry.bin"
fi
if [ "${2:-}" = '--sample-art' ]; then export DEN_PROP_PACK_SOURCE="$repo/authoring/prop-packs/example/assets"; fi
"$engine/Binaries/Linux/UnrealEditor-Cmd" "$kit/SWZeroCompany.uproject" -run=pythonscript -script="$repo/unreal/scripts/build_prop_pack.py" -unattended -nop4 -nosplash -NullRHI -stdout -FullStdOutLogOutput -NoCrashDialog > "$logs/author.log" 2>&1 || true
rg 'DENPACK|ZCOMAUTH.*(error|warning|FAILED)' "$logs/author.log" || true
rg -q 'DENPACK_RESULT ok' "$logs/author.log" || { echo 'Pack authoring failed'; exit 1; }
if rg -q 'ZCOMAUTH .*: (warning|error):' "$logs/author.log"; then
    echo 'Resolve Blueprint compile diagnostics before cooking' >&2;exit 1
fi
NuGetAudit=false "$engine/Build/BatchFiles/RunUAT.sh" -ScriptsForProject="$kit/SWZeroCompany.uproject" BuildCookRun -project="$kit/SWZeroCompany.uproject" -nop4 -utf8output -unattended -nocompileeditor -skipbuildeditor -platform=Linux -clientconfig=Shipping -cook -stage -pak -iostore -dlcname="$name" -DLCPakPluginFile -basedonreleaseversion=BaseGame -AdditionalCookerOptions="-AllowUncookedAssetReferences" -archive -archivedirectory="$kit/Packaged" > "$logs/cook.log" 2>&1 || { tail -30 "$logs/cook.log";exit 1; }
# UAT mirrors the source plugin location (Mods or Plugins) into its archive/cook.
paks=$(find "$kit/Packaged/Linux/SWZeroCompany" -type f -name "${name}SWZeroCompany-Linux.utoc" -printf '%h\n')
[ -n "$paks" ] && [ "$(printf '%s\n' "$paks" | wc -l)" -eq 1 ] || { echo 'Ambiguous/missing cooked plugin';exit 1; }
registry=$(find "$folder/Saved/Cooked/Linux/SWZeroCompany" -type f -name AssetRegistry.bin)
[ -f "$registry" ] || { echo 'Missing/ambiguous cooked registry';exit 1; }
for ext in ucas utoc;do cp "$paks/${name}SWZeroCompany-Linux.$ext" "$out/${name}_P.$ext";done
# Source descriptors may be editor-mounted. The shipped descriptor is always an active Game Feature.
python3 - "$folder/Authoring/pack.json" "$work" <<'PYMANIFEST'
import json,sys
from pathlib import Path
sys.path.insert(0,'tools/prop_packs')
from prop_pack import descriptor,validate,sharing_manifest
manifest,work=sys.argv[1:];doc=validate(json.loads(Path(manifest).read_text()));name=doc['plugin'];runtime=descriptor(doc)
Path(work,f'{name}.pack.json').write_text(json.dumps(sharing_manifest(doc),indent=2)+'\n')
Path(work,f'{name}.uplugin').write_text(json.dumps(runtime,indent=2)+'\n')
Path(work,f'{name}.upluginmanifest').write_text(json.dumps({'Contents':[{'File':f'../../../SWZeroCompany/Plugins/GameFeatures/{name}/{name}.uplugin','Descriptor':runtime}]},indent=2)+'\n')
PYMANIFEST
plugin_dir="../../../SWZeroCompany/Plugins/GameFeatures/$name"
cat > "$work/pak.txt" <<LIST
"$work/$name.upluginmanifest" "../../../SWZeroCompany/Plugins/$name.upluginmanifest" -compress
"$work/$name.uplugin" "$plugin_dir/$name.uplugin" -compress
"$registry" "$plugin_dir/AssetRegistry.bin" -compress
LIST
"$engine/Binaries/Linux/UnrealPak" "$out/${name}_P.pak" -create="$work/pak.txt" -platform=Linux -compressionformats=Oodle -compresslevel=4 -compressmethod=Kraken > "$logs/pak.log" 2>&1
"$engine/Binaries/Linux/UnrealPak" "$out/${name}_P.utoc" -List > "$logs/content-list.log" 2>&1
python3 - "$name" "$folder/Authoring/pack.json" "$logs/content-list.log" <<'PY'
import json,sys,re
from pathlib import Path
name,manifest,listing=sys.argv[1:];doc=json.loads(Path(manifest).read_text());text=Path(listing).read_text()
entries=re.findall(r'Display: "([^"]+)" offset:',text)
assert entries and all(x=='<ContainerHeader>' or any(x.startswith(f'../../../SWZeroCompany/{location}/{name}/') for location in ('Mods','Plugins','Plugins/GameFeatures')) for x in entries),'Pack contains assets outside its own namespace'
for asset in [name,'BP_PropPack']+[x['mesh'].split('.')[-1] for x in doc['props']]+[x['path'].split('.')[-1] for x in doc.get('assets',[])]:
    assert f'/{asset}.uasset"' in text,'Missing '+asset
print('Verified independent pack:',name,len(entries),'cooked entries')
PY
cp "$work/$name.pack.json" "$out/$name.pack.json"
(cd "$out" && sha256sum "${name}_P".*) > "$build_root/SHA256SUMS"
echo "Pack ready in $out"
