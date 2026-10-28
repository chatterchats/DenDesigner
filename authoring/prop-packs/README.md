# Create a Den Designer prop pack

A prop pack adds your static meshes, textures and materials to Den Designer's catalog. Players
install its three containers alongside Den Designer 0.9.0 or later. The game pack is content-only:
players need no UE4SS, native DLL or authoring tools.

## Start in Unreal Editor

Use the **[Prop Pack Editor guide](EDITOR-GUIDE.md)** with the public **SWZC SDK or base SWZC
Unreal Modkit**. No private Merged Kit or full Den Designer source build is required.

The editor plugin provides **Tools → Den Designer Prop Packs**:

1. Create a pack and save its name, identity and author details.
2. Import your assets into the pack's content folder.
3. Add selected meshes from the Content Browser and edit their catalog details.
4. Validate, then build the pack from the panel.
5. Open the export folder, test the pack in game, and distribute the matching containers with credits.

Creators do not run custom Bash or Python files or edit JSON. The guide explains installation,
asset requirements, export locations and updating an existing pack.

Choose **DenDesigner-PropPack-Editor-0.2.0-preview.1.zip**. It bundles a stock Editor Utility Widget
and Python code run by Unreal's built-in interpreter. No custom native module, external Python
installation or engine BuildId-specific download is needed. The tool is versioned separately from
the game runtime and is still an unreleased preview; packs work with Den Designer 0.9.0 and later,
including **1.0.0**. Linux UE 5.6.1 is verified; Windows execution remains unverified.
Python does not remove the need for a Windows editor when cooking custom Windows material shaders.

## What players see

In the game's Den editor, **Catalog → All collections → Prop packs → your pack** shows its contents.
Search includes prop names, pack name, pack ID, author and tags. The normal thumbnail worker
renders each mesh. Placement, transforms, Storeroom, history and compositions use their existing
asset-path-based behavior.

## Automation and verification

The separate **[scripted authoring guide](SCRIPTED-AUTHORING.md)** covers the older Python/Bash
bundle, ZComAuthoring setup and rebuilding the local development sample. Those dependencies are
not used by the new widget/Python panel. Sample artwork is excluded from Git and both bundles;
see [sample credits](example/CREDITS.md).

The widget/Python workflow is checked in isolated copies of both public kits with the custom native
helpers disabled. See the [compatibility report](kit-compatibility.md) for the exact checks and limits.

## Registration contract (schema 1)

The generated provider is a child of `/DenDesignerGF/Runtime/BP_DenPropPack` with schema version 1.
Its GameFeatureData adds that component to `BitReactorGameState`. The plugin declares DenDesignerGF
as a dependency so its shared class exists before registration. There are no mesh hard references
in the registration metadata: opening the catalog never loads the whole pack's geometry.

For manual authoring, the provider fields are `PackID`, `Title`, `Author`, `Version`, `SchemaVersion`
and aligned arrays `Paths`, `Labels`, `Details`, `Dimensions`, `Solid`, `SearchTexts`.
Both authoring workflows fill these arrays for you. Do not rename the shared base class or its fields.

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

For portable sharing, manifests may declare stable mesh and material ownership in
`assets`. See [portable sharing](../../docs/portable-sharing.md#dependencies-and-compatibility)
for the schema, legacy mesh migration, and dependency checks.
