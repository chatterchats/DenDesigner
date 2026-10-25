# Den Designer

An in-game Den editor for **Star Wars: Zero Company**. Place props, rearrange existing scenery,
and save your decorations separately from campaign saves. This repository contains the **pak-only
edition**: cooked Blueprint assets, with no UE4SS or additional DLL required to play.

Current version: **1.0.0**, targeting Steam build 25898267. It includes compositions and independent
prop packs. Full release regression on that build is in progress.

## Start here

- [Player guide](distribution/pak/README.md): installation, controls, layouts, recovery and uninstall.
- [Build and development](docs/development.md): prerequisites, commands and repository structure.
- [Architecture](docs/architecture.md): runtime services, asset identities and persistence boundaries.
- [Verification](docs/verification.md): automated checks, in-game testing and release requirements.
- [Create a prop pack](authoring/prop-packs/README.md): in-editor creation/export, public SDK/base-modkit setup and automation tools.
- [Changelog](CHANGELOG.md) and [credits](CREDITS.md).

## Features

- Searchable catalog with thumbnails, collections, recent props and independent prop packs.
- Surface dragging, numeric transforms, move/rotate/scale gizmos, duplication and undo/redo.
- Separate Floors, Walls and Structure selection switches, grid snapping and selection range.
- Storeroom for stored props and unavailable entries.
- Shared Home layout, per-campaign copies, named presets, draft recovery and rotating backups.
- Saved compositions with group placement and generated thumbnail cards.
- In-game settings and rebindable controls.

Layouts live under `Saved/SaveGames/ZComDen/Native/v1`; thumbnails use `Saved/ZComDen/thumbs`.
These existing namespaces are intentionally stable. The mod does not write decorations into the
campaign save.

## Source and builds

Players need the runtime ZIP, not this source checkout. Build archives are kept out of Git;
see the [player guide](distribution/pak/README.md) for installation.

Prop-pack creators use **Tools → Den Designer Prop Packs** in the public **SWZC SDK or base
Unreal Modkit**. Follow the [editor guide](authoring/prop-packs/EDITOR-GUIDE.md) to install the
creator plugin, add meshes, validate and export from Unreal Editor. The panel uses an Editor Utility
Widget and bundled Python; creators need no terminal commands, external Python installation,
custom C++ compilation or private Merged Kit.

The creator plugin is **0.2.0-preview.1**, separate from the game runtime version, and remains
unreleased: it is not part of Den Designer 1.0.0 until Windows editor testing is complete. A single
content/Python bundle replaces the earlier Source/Linux binary downloads. Linux UE 5.6.1 is tested
in both prepared kits; Windows execution remains unverified. Windows shader cooking still requires
a Windows editor. The [scripted route](authoring/prop-packs/SCRIPTED-AUTHORING.md) remains available
for automation. See the [development guide](docs/development.md#prop-pack-editor) for packaging.

The full Den Designer runtime is currently built in Chats’ **private Merged Kit**. It is not a
publicly supplied prerequisite or a supported clean-checkout build for other creators. Maintainer
commands, after configuring that environment:

```sh
bash tools/build/build_gf.sh
bash tools/build/test_native.sh --existing
python3 -m unittest discover -s tests/python -p '*_test.py'
python3 tools/build/package_gf.py
```

Build products and logs go to `dist/build/`; distributable ZIPs go to `dist/packages/`.
The [repository map](docs/development.md#repository-map) describes the source and tool groups.
The runtime archive contains all three `DenDesignerGF_P` containers.
It mirrors the game folder, with its payload, `modinfo.json`, `zcom-mod.json` and player documentation
together under `Content/Paks/~mods/DenDesigner/` for manual installs and mod-manager imports.
Creator tools and the development prop pack are separate. Close the game before installing
or replacing containers. See the development guide for environment paths and release packaging.

## License and sample assets

Den Designer code is MIT licensed; see [LICENSE](LICENSE). Game/engine assets and third-party
art retain their original ownership and licenses. The development sample manifest, importer and
[credits](authoring/prop-packs/example/CREDITS.md) are included, but its local artwork is excluded
from Git pending complete cabinet provenance. Public pack creators should use their own assets.
