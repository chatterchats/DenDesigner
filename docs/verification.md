# Verification

## Automated checks

Run from the repository root:

```sh
python3 -m unittest discover -s tests/python -p '*_test.py'
bash tools/build/build_gf.sh
bash tools/build/test_native.sh --existing
python3 tools/build/package_gf.py
```

Python tests cover package contents, metadata, immutable archives, catalog conversion, creator
validation and preservation of existing assets. Native tests execute compiled Blueprint behavior:
persistence/recovery, world edits, selection, transforms, history, UI, preferences, catalog,
thumbnails, compositions and pack registration. The fixed 360-ray gizmo fixture is an independent
regression reference; do not regenerate its expected answers from the implementation under test.

Persistence tests use disposable slots and restore any kit fixtures they temporarily replace.
They do not depend on saves left by a previous test run. Use a kit copy for creator integration
checks; see [development](development.md#prop-pack-editor). Never run authoring, cooking and native
tests concurrently against the same kit.

The build validator checks the cooked asset allowlist, plugin manifest, compile/cook success and
source/container hashes. The packager checks metadata, ZIP contents, hashes and same-version
immutability. Keep one validator per boundary; there is no separate certificate/report framework.
The ZIP's `verification_scope` is `build_and_package` for both preview and stable versions. Actual
in-game results belong in release notes. A version number does not establish test coverage.

Native details are in `dist/build/runtime-logs/native-test.log`; the command prints failures and
the final result. Other build logs live beside it. Local screenshots and notes may be kept under
`dist/verification/`; they are not shipped or required as a particular report format.

## Release checklist

Before publishing a candidate:

- Build it, run both automated suites, package it and inspect the extracted ZIP. Check the version,
  description, three matching containers and `modinfo.json`/`zcom-mod.json` under the single
  `Content/Paks/~mods/DenDesigner/` folder.
- Start the game with UE4SS disabled. Enter the Den, open/close the editor, travel to a mission and
  back, then restart. Check camera restoration and automatic layout application.
- Select placed and vanilla props; exercise floor/wall/structure switches, selection range,
  surface/height drag, numeric transforms, gizmo axis/plane/ring handles, duplication and undo/redo.
- Search/place catalog and pack props, generate/reuse thumbnails, store/restore props, and capture,
  save, restart and place a composition. Check missing-pack entries survive removal/reinstallation.
- Save Home and campaign layouts, switch scopes, load presets, change/rebind settings and restart.
  Interrupt an editing session to check draft recovery; confirm backups and unavailable entries.
- Restore the original test setup and note the tested build, checks performed and remaining limits
  in the release notes. Windows creator testing is separate from playing the Windows game under Proton.

A successful automated run covers compiled behavior and package integrity. Visuals, physical input,
shipping-game lifecycle and compatibility need the in-game checks above.

## Safe game testing

Use the throwaway ZC Sandbox campaign (`BA3302BC4165EB931E86A39BFF208F71`) on the main installation.
Back up the mod's Saved folders, sandbox saves, installed containers and loader state before changing
anything. Close the game before replacing containers; restore the original files after testing.
Do not edit user INIs, another mod's settings or symlinked mods' source `enabled.txt` files.

ZC Sandbox can supply diagnostic control, but a separate run with the loader disabled establishes
standalone operation. Guard input/screenshots against the game losing focus, and obtain an
uninterrupted input window. Never use a real campaign as a disposable fixture.

`tests/integration/native_travel/build.sh` creates a separate **DenTravelQA** feature for checking
mission-success return. Its F7 helper is restricted to the sandbox and `SK_Kaller_020_Root`.
It is never installed automatically or shipped; remove it when finished.

## Recorded creator verification

The widget/Python creator was checked on Linux UE 5.6.1 in isolated public SDK and base-modkit copies.
Real panel callbacks covered Save, provider/GameFeature authoring, asynchronous Build, namespace
audit and export. Fresh editor processes checked registration; a graphical run checked rendered
layout and tab-reopen/build-completion behavior. Custom native authoring helpers were disabled.
Windows editor execution and arbitrary Windows material shaders remain unverified.

### Fresh creator ZIP and exported-pack acceptance — 2026-10-21

Creator **0.2.0-preview.1** was installed from its ZIP into a fresh base-kit copy, reusing only
engine-matched base-kit modules. A project path containing spaces exercised restart/mount behavior.
Stock FBX/PNG import and real panel callbacks produced a textured cube and pumpkin pack.

That export passed automatic registration, catalog thumbnails, textured placement, saving and a full
restart in the shipping game under Proton with ZC Sandbox assisting control. Both props returned at
their saved transforms; cached thumbnails retained their hashes and modification times. Original
game data/mods were restored. This was a focused pack check; neither prop had simple collision.
The detailed [kit compatibility report](../authoring/prop-packs/kit-compatibility.md) describes scope
and prerequisites. Historical local outputs may have been removed during cleanup.
