# Development

The maintained project is the pak-only editor and its separate creator tools.

## Repository map

| Path | Purpose |
|---|---|
| `unreal/DenDesignerGF/` | Runtime Game Feature descriptor; `Content/` is generated. |
| `unreal/specs/runtime*.py` | Blueprint runtime, widgets, input and services. |
| `unreal/specs/graph.py` | Shared graph-generation helpers. |
| `unreal/specs/ui_templates.py` | Native widget trees, the UI theme and camera/input templates. |
| `unreal/icons/` | Editor UI icons: 24 px white-stroke SVGs, tinted by the widgets. |
| `unreal/generated/runtime/` | Generated JSON specifications, retained for review. |
| `unreal/data/` | Catalog metadata and gizmo geometry consumed directly by the build. |
| `unreal/scripts/` | Editor-only asset authoring, import, export and verification scripts. |
| `tools/build/` | Runtime build, packaging, catalog generation and release validation. |
| `tools/prop_packs/` | Creator-bundle packaging, scripted pack builds and provider-reference export. |
| `tools/dev/` | Optional guarded game input, screenshots and Sandbox isolation. |
| `tests/python/` | Standard-library tests; run without Unreal. |
| `tests/unreal/` | Compiled Blueprint tests and public-kit creator integration checks. |
| `tests/fixtures/`, `tests/integration/` | Fixed reference data and the separate travel QA plugin. |
| `authoring/prop-packs/` | Widget/Python editor plugin, creator guides, optional scripted helper, shared reference and manifests. |
| `unreal/DenPropsExample/` | Separate development sample plugin; never bundled with the editor. |
| `distribution/pak/` | Player documentation and mod-manager metadata shipped with the runtime. |
| `dist/build/` | Ignored current build products, work files and logs. |
| `dist/packages/` | Runtime and creator ZIPs with checksums. |
| `dist/verification/`, `dist/state/` | Current test evidence and development-helper state. |

## Prerequisites

These prerequisites are for maintaining the full Den Designer runtime in Chats’ **private** build
environment. Prop-pack creators use the [public SDK/base-modkit workflow](../authoring/prop-packs/README.md)
and do not need this kit.

Use the project's UE **5.6.1** SWZC Merged Kit, regenerated with the editor-only **ZComAuthoring**
plugin, and Python 3.10+.
The kit supplies its own Unreal Python API and authoring helper. Player installations require none
of these development tools.

The shell helpers currently target the Linux kit layout. Set:

```sh
export SWZC_ROOT="/path/to/volume-containing-UnrealEngine-and-kit"
export SWZC_KIT="$SWZC_ROOT/SWZC Merged Kit"
```

`SWZC_ROOT/UnrealEngine/Engine` must contain the editor and UAT. The kit needs its reconstructed game
assets and `Releases/BaseGame/Windows/AssetRegistry.bin`. Build helpers create their plugin symlinks
under `Mods/` and reject a symlink targeting a different checkout. Do not hand-edit managed kit assets;
regenerate the kit through its own tooling when that infrastructure changes.

## Generate, build and test

```sh
python3 -I unreal/specs/runtime.py            # regenerate reviewable JSON only
bash tools/build/build_gf.sh --author-only         # author/compile in the kit; no cook or installation
bash tools/build/build_gf.sh                       # author, cook, validate and record hashes
bash tools/build/test_native.sh --existing         # execute the authored Blueprint tests in the kit
python3 -m unittest discover -s tests/python -p '*_test.py'
```

`test_native.sh` without `--existing` reauthors the runtime first. Tests use the kit's own
`Saved` directory and dedicated test slots. They do not install mods or touch game campaign saves.
Do not run authoring, cooking and native tests concurrently against the same kit.

The runtime build emits `dist/build/runtime/SWZeroCompany/Content/Paks/~mods/DenDesignerGF_P.{pak,ucas,utoc}`.
Logs are in `dist/build/runtime-logs`. `tools/build/gf_build_info.py` verifies exact input hashes, the authored asset
allowlist, the single-plugin manifest and the runtime coordinator entry point.

Source generators stay in `unreal/specs/`; their reviewable JSON output belongs in
`unreal/generated/runtime/`. Edit the generators and regenerate rather than editing JSON by hand.
Unreal plugin directory names and mounted asset paths are independent of this repository layout.

To install a verified build, close the game and use `bash tools/build/build_gf.sh --install`.
`SWZC_GAME` may override the game directory containing `SWZeroCompany`; otherwise the script reads
the kit's `GameInstallDirectory.txt`. Installation refuses a running game. Disable only the old
Den Designer edition first, following the player guide; other UE4SS mods may remain installed.

## Packages and versioning

The version lives in `unreal/DenDesignerGF/DenDesignerGF.uplugin` (`Version` and `VersionName`).
Increment the version before publishing different content under an existing archive name.
Update `distribution/pak/modinfo.json` and `distribution/pak/zcom-mod.json` to the same version.
The packager checks their shared title, author, description and standalone IoStore identity against
the verified runtime; mismatched metadata stops packaging.

```sh
python3 tools/build/gf_build_info.py
python3 tools/build/package_gf.py
```

Before publishing, complete the [release checklist](verification.md#release-checklist).
Packaging checks every archived byte, generates a manifest
and checksum, and refuses to replace a same-version archive with different content. It creates a
runtime ZIP. Prop packs, QA plugins, source art, private
screenshots and unreleased presets are excluded by the explicit package inventory.

The runtime archive mirrors `SWZeroCompany/`, with every file under
`Content/Paks/~mods/DenDesigner/`: three matching containers, both mod-manager metadata files,
player docs, license and integrity manifest. The manifest records build/package verification;
in-game results belong in release notes. The creator-editor ZIP is editor
tooling and is not labelled as an installable game mod.

`--install` uses the same `DenDesigner` subfolder and refuses an existing flat container set to
avoid loading duplicate versions. See the player guide for updating an older manual installation.

All package commands write to `dist/packages/`. Existing runtime and creator-editor ZIPs were
retained unchanged. Historical build reports describe their original test runs; they are not
substitutes for rebuilding with the current inputs. Disposable historical output is outside the
maintained working tree.

## Data and sample assets

`unreal/data/catalog.json` is the canonical catalog input. Normal builds never regenerate it
implicitly. To refresh it from an updated ZCRE registry and mesh cache:

```sh
python3 tools/build/build_catalog.py --zcre /path/to/ZCRE --report
```

Review path, label, shelf and count changes before rebuilding. This exports metadata only.
`unreal/data/gizmo_geometry.json` contains the 16 validated procedural handle meshes. The frozen
ray fixture in `tests/fixtures/gizmo_pick.json` is an independent regression reference; do not
regenerate expected results from the implementation being tested.

The [editor workflow](../authoring/prop-packs/EDITOR-GUIDE.md) is the primary creator route; see
[Prop-pack editor](#prop-pack-editor) below for its maintainer packaging commands.
The [compatibility report](../authoring/prop-packs/kit-compatibility.md) records verification limits
for both public kits and both authoring routes.

`python3 tools/prop_packs/package_prop_authoring.py` builds the separate **scripted** authoring ZIP, including
ZComAuthoring and the versioned reference Blueprint. Its [automation guide](../authoring/prop-packs/SCRIPTED-AUTHORING.md)
covers prerequisites and the build helper's explicit `SWZC_KIT` and `SWZC_ENGINE` paths. Neither
creator bundle includes sample artwork or requires the private kit to package.

The [sample prop pack](../authoring/prop-packs/README.md) rebuilds from local FBX/PNG sources
when those files are available under the Git-ignored `example/assets` directory. A clean checkout
includes the manifest, importer and credits, but no sample artwork. When present, the sample
does not need adjacent mods or a Blender export step. Existing engine materials
are referenced by path. The cabinet uses an opaque parent to prevent front faces drawing through
its side panels. The sample is a development artifact with separate attribution and provenance
limitations; it is not silently included in a public editor package.

## Optional in-game tools

`tools/dev/dd.py` provides status, kill, Lutris launch and guarded game-window screenshots. Its local
install path and Lutris ID are development configuration. `tools/dev/game_keys.py` sends guarded input
only to the identified game window. A lost-focus check must stop the attempt; never remove the guard.

`dd.py den`, `send` and `restart` require the separately installed **ZC Sandbox** controller.
`con` sends Unreal console commands through ZC Sandbox. These optional diagnostic routes do not
prove UE4SS independence; use normal game input with the loader disabled for standalone acceptance.
`log` reads the game's native log. See [verification](verification.md) before running live tests.

## Prop-pack editor

`authoring/prop-packs/Plugins/DenPropPackEditor` is a content-only editor plugin using a stock Editor
Utility Widget and Unreal's bundled Python. It requires PythonScriptPlugin and
EditorScriptingUtilities, but no ZComAuthoring or custom native module. Its version is maintained in
`DenPropPackEditor.uplugin`, currently `0.2.0-preview.1`, independently of the game runtime.

The shipped `Content/UI/EUW_PropPacks.uasset` is an empty stock widget shell. Python constructs the
form and callbacks when opened through Tools. Maintainers can regenerate the shell by running
`unreal/scripts/build_pack_editor_panel.py` inside a disposable enabled test project, then copying
that asset back. This uses stock Unreal factories; no native authoring helper is needed.

Package the single content/Python ZIP after source or documentation changes:

```sh
python3 tools/prop_packs/package_editor_authoring.py
python3 -m unittest discover -s tests/python -p 'editor_authoring*_test.py'
```

The archive embeds `EDITOR-GUIDE.md` as its README, the Python files and widget, and the minimal
provider reference. Its manifest records source hashes and engine version, with no custom engine
BuildId requirement. Source/Binaries, bytecode, sample art and the old helper are excluded.

Integration test `tests/unreal/test_pack_editor.py` creates **DenPythonTest** from an engine cube.
Run only in disposable SDK/base-modkit project copies with the authoring plugin and reference
installed, Python enabled and custom helpers disabled:

```sh
DENPACK_EDITOR_TEST_MODE=build /path/to/Engine/Binaries/Linux/UnrealEditor-Cmd \
  /path/to/test-kit/SWZeroCompany.uproject -run=pythonscript \
  -script=/absolute/path/to/repo/tests/unreal/test_pack_editor.py \
  -unattended -nop4 -NullRHI -stdout -FullStdOutLogOutput
```

Modes are `smoke`, `build` and `verify`. Run `verify` in a fresh editor process after `build` to check
serialized provider and GameState/component registration. The build mode exercises real UMG Save
and asynchronous Build callbacks and audits all three exported containers. A relocated SDK may need
its plugin/engine `Binaries/Linux` folders on `LD_LIBRARY_PATH`; that is kit setup, not a requirement
for the content-only authoring plugin. Windows execution is not yet verified.

For the docked UI lifecycle, run `tests/unreal/test_pack_editor_ui.py` with
`-ExecutePythonScript=/absolute/path/to/script.py` in a graphical editor after the cube test.
It opens the panel, closes/reopens the tab with a pending completion future, checks retained form
state and completion, and exits automatically. Use a dedicated test display for unattended runs.

Creators use the panel, not these maintainer commands. See the
[editor guide](../authoring/prop-packs/EDITOR-GUIDE.md) for installation, mounting and cooking limits.
