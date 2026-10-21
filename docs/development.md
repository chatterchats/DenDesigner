# Development

The maintained project is the pak-only editor. The retired Lua runtime, override plugin,
feasibility prototype and historical probes are not build dependencies or release contents.

## Repository map

| Path | Purpose |
|---|---|
| `unreal/DenDesignerGF/` | Runtime Game Feature descriptor; `Content/` is generated. |
| `unreal/specs/runtime*.py` | Blueprint runtime, widgets, input and services. |
| `unreal/specs/graph.py` | Shared graph-generation helpers. |
| `unreal/specs/ui_templates.py` | Native widget trees and camera/input templates. |
| `unreal/specs/runtime/` | Generated JSON specifications, retained for review. |
| `unreal/data/` | Catalog metadata and gizmo geometry consumed directly by the build. |
| `unreal/scripts/` | Editor-only authoring and compiled Blueprint tests. |
| `tools/` | Build, packaging, migration, validation and optional game-test helpers. |
| `tests/` | Python tests, fixed reference fixtures and the separate travel QA plugin. |
| `authoring/prop-packs/` | Creator guide, bundled helper/reference, starter and development-sample manifests. |
| `unreal/DenPropsExample/` | Separate development sample plugin; never bundled with the editor. |
| `distribution/` | Documentation shipped with runtime and optional migration archives. |
| `dist/` | Ignored builds, logs, packages and local verification evidence. |

## Prerequisites

These prerequisites are for maintaining the full Den Designer runtime in Chats’ **private** build
environment. Prop-pack creators use the [public SDK/base-modkit workflow](../authoring/prop-packs/README.md)
and do not need this kit.

Use the project's UE **5.6.1** SWZC Merged Kit, regenerated with the editor-only **ZComAuthoring**
plugin, and Python 3.10+. Core build and test tooling does not require LuaJIT or the old edition.
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
bash tools/build_gf.sh --author-only         # author/compile in the kit; no cook or installation
bash tools/build_gf.sh                       # author, cook, validate and record hashes
bash tools/test_native.sh --existing         # execute the authored Blueprint tests in the kit
python3 -m unittest discover -s tests -p '*_test.py'
```

`test_native.sh` without `--existing` reauthors the runtime first. Tests use the kit's own
`Saved` directory and dedicated test slots. They do not install mods or touch game campaign saves.
Do not run authoring, cooking and native tests concurrently against the same kit.

The runtime build emits `dist/gf/SWZeroCompany/Content/Paks/~mods/DenDesignerGF_P.{pak,ucas,utoc}`.
Logs are in `dist/gf-logs`. `tools/gf_build_info.py` verifies exact input hashes, the authored asset
allowlist, the single-plugin manifest and the runtime coordinator entry point.

To install a verified build, close the game and use `bash tools/build_gf.sh --install`.
`SWZC_GAME` may override the game directory containing `SWZeroCompany`; otherwise the script reads
the kit's `GameInstallDirectory.txt`. Installation refuses a running game. Disable only the old
Den Designer edition first, following the player guide; other UE4SS mods may remain installed.

## Packages and versioning

The version lives in `unreal/DenDesignerGF/DenDesignerGF.uplugin` (`Version` and `VersionName`).
Increment the version before publishing different content under an existing archive name.

```sh
python3 tools/gf_build_info.py
python3 tools/package_gf.py                    # preview version only
python3 tools/package_gf.py --acceptance /path/to/reviewed-report.json
```

Stable versions require reviewed, exact-build acceptance evidence. Preview packages explicitly
state that full regression is incomplete. Packaging checks every archived byte, generates a manifest
and checksum, and refuses to replace a same-version archive with different content. It creates a
runtime ZIP and a separate optional migration ZIP. Prop packs, QA plugins, source art, private
screenshots and unreleased presets are excluded by the explicit package inventory.

## Data and sample assets

`unreal/data/catalog.json` is the canonical catalog input. Normal builds never regenerate it
implicitly. To refresh it from an updated ZCRE registry and mesh cache:

```sh
python3 tools/build_catalog.py --zcre /path/to/ZCRE --report
```

Review path, label, shelf and count changes before rebuilding. This exports metadata only.
`unreal/data/gizmo_geometry.json` contains the 16 validated procedural handle meshes. The frozen
ray fixture in `tests/fixtures/gizmo_pick.json` is an independent regression reference; do not
regenerate expected results from the implementation being tested.

The [SDK/base-modkit authoring checks](../authoring/prop-packs/kit-compatibility.md) document the
minimal dependency and editor-mounted source workflow for independent pack creators.
`python3 tools/package_prop_authoring.py` builds the standalone creator ZIP, including the
versioned reference Blueprint and helper source under `authoring/prop-packs/Plugins`. It excludes
sample artwork and needs no private kit to package; reference updates are a maintainer operation.
The pack build helper requires explicit `SWZC_KIT` and `SWZC_ENGINE` paths.

The [sample prop pack](../authoring/prop-packs/README.md) rebuilds from local FBX/PNG sources
when those files are available under the Git-ignored `example/assets` directory. A clean checkout
includes the manifest, importer and credits, but no sample artwork. When present, the sample
does not need adjacent mods, a Blender export step or Lua scripts. Existing engine materials
are referenced by path. The cabinet uses an opaque parent to prevent front faces drawing through
its side panels. The sample is a development artifact with separate attribution and provenance
limitations; it is not silently included in a public editor package.

## Optional in-game tools

`tools/dd.py` provides status, kill, Lutris launch and guarded game-window screenshots. Its local
install path and Lutris ID are development configuration. `tools/game_keys.py` sends guarded input
only to the identified game window. A lost-focus check must stop the attempt; never remove the guard.

`dd.py den`, `send` and `restart` require the separately installed **ZC Sandbox** controller.
`lua` and `con` require the separate development console. These optional diagnostic routes do not
prove UE4SS independence; use normal game input with the loader disabled for standalone acceptance.
`log` reads the game's native log. See [verification](verification.md) before running live tests.
