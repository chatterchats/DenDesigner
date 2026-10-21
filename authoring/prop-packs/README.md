# Den Designer prop packs (schema 1)

A prop pack is a separate content-only Game Feature containing your static meshes, textures,
material instances, a small registration Blueprint and its own plugin manifest. Players install
its containers alongside Den Designer 0.9.0 or later. No Lua, UE4SS or native DLL is needed.

In the editor, **Catalog → All collections → Prop packs → your pack** shows its contents.
Search includes prop names, pack name, pack ID, author and tags. The normal thumbnail worker
renders each mesh. Placement, transforms, Storeroom, history and compositions use their existing
asset-path-based behavior.

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
   python3 tools/prop_pack.py /path/to/pack.json \
     --output "/path/to/kit/Plugins/MyFurniture" --editor-mounted
   ```

   Enable that plugin in the project, then import assets under its mount (`/MyFurniture/`).
   Assign materials, build collision, and verify units, normals, UVs and pivots. Include all
   custom dependencies. Re-run the generator after changing manifest metadata; it preserves
   imported Content. Keep the source plugin inside the kit's `Plugins` folder.
4. Close the editor and build, selecting your SDK or base-modkit project explicitly:

   ```sh
   SWZC_KIT="/path/to/kit" SWZC_ENGINE="/path/to/UnrealEngine/Engine" \
     bash tools/build_prop_pack.sh "/path/to/kit/Plugins/MyFurniture"
   ```

   Python 3, Bash, ripgrep and the kit's matching UE build tools must be installed.
   The helper authors registration, validates meshes, cooks and assembles an independent
   manifest. It never installs into the game. Outputs are under `dist/prop-packs/MyFurniture`;
   `DEN_PROP_PACK_BUILD_ROOT` can choose a different output directory.
5. Check your pack in the game with the current Den Designer installed. Test catalog discovery,
   thumbnails, placement, materials and a layout reload. A successful cook alone is not a visual
   or runtime acceptance test. Linux custom shaders do not substitute for Windows shaders;
   the tested development sample uses existing engine material parents.
6. Distribute only the three matching containers (`MyFurniture_P.pak`, `.ucas`, `.utoc`), credits
   and a requirement for Den Designer. Never ship the reference Blueprint plugin, editor helper,
   kit files or a combined game plugin manifest. The build checks the cooked pack namespace.

The generated provider is a child of `/DenDesignerGF/Runtime/BP_DenPropPack` with schema version 1.
Its GameFeatureData adds that component to `BitReactorGameState`. The plugin declares DenDesignerGF
as a dependency so its shared class exists before registration. There are no mesh hard references
in the registration metadata: opening the catalog never loads the whole pack's geometry.

For manual authoring, the provider fields are `PackID`, `Title`, `Author`, `Version`, `SchemaVersion`
and aligned arrays `Paths`, `Labels`, `Details`, `Dimensions`, `Solid`, `SearchTexts`.
The JSON generator fills these arrays for you. Do not rename the shared base class or its fields.

## Limits and updates

- Schema 1 supports static mesh props with asset-backed materials. It does not register gameplay
  actors, scripts, animations or functional arcade games. The sample cabinet is decorative.
- Up to 32 providers, with 2,048 props per pack. Catalog import processes at most eight steps or
  three milliseconds per tick. Search keeps the existing 300-result display cap; pack shelves
  show all their entries.
- Invalid headers reject the pack; invalid/duplicate rows are skipped. A diagnostic appears in
  the catalog footer. Conflicting pack IDs (case-insensitive) reject both providers in that import.
  Packs cannot replace existing catalog rows. Two separate packs should never own the same path.
- Install, update or remove containers while the game is closed. Restart to discover changes;
  hot-install/uninstall is not supported. Each new editor session reads installed providers.
- Keep plugin names and asset paths stable across updates. Saves and compositions retain those
  paths, rather than transient catalog row numbers. Renaming a mesh breaks existing placements.
- Uninstalling a pack does not erase layout entries. Missing assets follow the existing apply
  issue path; reinstalling the same paths lets them load again. Back up layouts before removing
  content, and avoid replacing an arrangement while its dependencies are missing.
- Thumbnail files are keyed by mesh path. If an update changes a mesh in place, remove that
  mesh's cached PNG from `Saved/ZComDen/thumbs` to regenerate its preview.

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

`python3 tools/package_prop_authoring.py` assembles the self-contained ZIP from this repository.
The checked-in reference and helper source are the creator dependencies. Updating the shared
provider contract requires the maintainer to refresh the reference with `tools/prop_pack_reference.py`
from a verified runtime build, then repeat compatibility checks. Creators do not run that exporter.
