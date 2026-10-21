# Scripted prop-pack authoring

This optional workflow is for maintainers and automation. For pack creation entirely inside
Unreal Editor, use the [Prop Pack Editor guide](EDITOR-GUIDE.md) instead.

These instructions apply to the **DenDesigner-PropPack-Authoring** archive, which contains
Python/Bash tooling and ZComAuthoring. They do not apply to the separate editor-plugin archive.

## Supported authoring setups

Use either the **SWZC SDK or base SWZC Unreal Modkit**, plus the Den Designer prop-pack
authoring bundle. No private merged kit, reconstructed game classes, full Den Designer source
build or other mod checkout is required. The bundle supplies:

- `Plugins/DenDesignerGF`: the minimal uncooked provider Blueprint reference;
- `Plugins/ZComAuthoring`: editor helper source and Python asset builder;
- `tools/`: manifest generation and independent pack packaging;
- `unreal/scripts/`: registration authoring and fresh-editor verification;
- `authoring/prop-packs/template.json`: an asset-free starter manifest.

Read the [tested SDK/base-modkit setup](kit-compatibility.md) first. Both routes passed local
**Linux UE 5.6.1** authoring, fresh-editor reload, cooking and packaging. The bundled build script
and helper currently target Linux. A Windows authoring workflow has not yet been verified.

## Author a pack

1. Extract the authoring bundle. Copy its two `Plugins` folders into your kit's `Plugins` folder
   while the editor is closed. Do not overwrite an existing real `DenDesignerGF` plugin.
   Enable the plugins and build the editor helper against your kit's engine as described in
   the setup guide. These are editor prerequisites, not files to install in the game.
2. Copy `authoring/prop-packs/template.json`, choose a unique plugin name and permanent lowercase
   pack ID. Replace the example chair path with your own imported asset. List each mesh's full
   object path, display name, dimensions in centimeters, collision flag and optional tags.
3. From the extracted bundle directory, generate your source plugin:

   ```sh
   python3 tools/prop_packs/prop_pack.py /path/to/pack.json \
     --output "/path/to/kit/Plugins/MyFurniture" --editor-mounted
   ```

   Enable that plugin in the project, then import assets under its mount (`/MyFurniture/`).
   Assign materials, build collision, and verify units, normals, UVs and pivots. Include all
   custom dependencies. Re-run the generator after changing manifest metadata; it preserves
   imported Content. Keep the source plugin inside the kit's `Plugins` folder.
4. Close the editor and build, selecting your SDK or base-modkit project explicitly:

   ```sh
   SWZC_KIT="/path/to/kit" SWZC_ENGINE="/path/to/UnrealEngine/Engine" \
     bash tools/prop_packs/build_prop_pack.sh "/path/to/kit/Plugins/MyFurniture"
   ```

   Python 3, Bash, ripgrep and the kit's matching UE build tools must be installed.
   The helper authors registration, validates meshes, cooks and assembles an independent
   manifest. It never installs into the game. Outputs are under `dist/build/prop-packs/MyFurniture`;
   `DEN_PROP_PACK_BUILD_ROOT` can choose a different output directory.
5. Check your pack in the game with the current Den Designer installed. Test catalog discovery,
   thumbnails, placement, materials and a layout reload. A successful cook alone is not a visual
   or runtime acceptance test. Linux custom shaders do not substitute for Windows shaders;
   the tested development sample uses existing engine material parents.
6. Distribute only the three matching containers (`MyFurniture_P.pak`, `.ucas`, `.utoc`), credits
   and a requirement for Den Designer. Never ship the reference Blueprint plugin, editor helper,
   kit files or a combined game plugin manifest. The build checks the cooked pack namespace.

## Rebuild the development sample

The maintainer’s local `example/assets/` directory contains three FBX meshes, three PNG
textures and material-slot metadata for the Arcade & Halloween development sample. This artwork
is **excluded from Git and the creator bundle**; a fresh checkout has the manifest, importer and
credits only. Consult [credits and provenance](example/CREDITS.md)
before redistributing that separate sample; the cabinet's original attribution needs confirmation.

Maintainers can generate `example/pack.json` into a prepared kit's `Plugins/DenPropsExample` and
run the repository build helper with `--sample-art`, explicit `SWZC_KIT` and `SWZC_ENGINE`,
provided the local artwork is available. No
full Den Designer build is required when the supplied minimal reference is installed.

The cabinet uses the engine's opaque widget material variant; pumpkins use the existing
basic-shape material. The importer checks cabinet texture assignments. These three props passed
SDK and base-modkit authoring/cook/reload checks; see the setup guide for the exact scope.

## Maintaining the creator bundle

`python3 tools/prop_packs/package_prop_authoring.py` assembles the self-contained ZIP from this repository.
The checked-in reference and helper source are the creator dependencies. Updating the shared
provider contract requires the maintainer to refresh the reference with `tools/prop_packs/prop_pack_reference.py`
from a verified runtime build, then repeat compatibility checks. Creators do not run that exporter.
