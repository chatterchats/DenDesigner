# Changelog

## 1.1.0-preview.6 — editor UI rework

- Reworked the editor UI: a menu bar with grouped tools, grid/range and selection filters; a library
  dock on the left with Catalog, Storeroom, Compositions and Layouts tabs; an inspector dock on the right;
  and a status bar with the fixed mouse and Esc controls.
- New look: translucent panels with thin outlines, an amber accent, condensed capital labels and icons.
  Active tools, tabs and filters are highlighted instead of reading "On"/"Off".
- The game's HUD hides while the editor is open, through the game's own cinematic HUD switch.
- Added a Select tool that hides the gizmo. Move, Rotate and Scale moved from the inspector to the menu bar.
- Catalog collections are a row of chips above two-column cards; Settings open in the inspector's place.
- Inspector fields show two decimals (0.01 cm); typed values keep full precision.
- Widget names, events, saved data and key bindings are unchanged.

## Unreleased — prop-pack editor tools

Not part of 1.0.0; awaiting Windows editor testing.

- Added Prop Pack Editor `0.2.0-preview.1`: an Editor Utility Widget with bundled Python for creating, editing, validating and exporting packs inside Unreal.
- Replaced the provisional C++ module and platform-specific archives with one content/Python bundle; no custom compiler toolchain or external Python installation required.
- Added asynchronous build progress, per-build logs, isolated exports, dependency checks and saved registration verification.
- Documented the new workflow, upgrade steps, one-time mounting restart for paths with spaces, and platform cooking limits.
- Kept schema-1 packs and the current game runtime unchanged; older scripted authoring remains available separately.

## 1.0.0 — first stable release

- Promoted the 0.9.0 preview runtime to stable: compositions, independent prop-pack support and the mod-manager package layout from 0.9.0-preview.3.
- Declared Steam build `25898267` in `zcom-mod.json`.
- Prop-pack creator tools are not part of this release; they stay in preview pending Windows testing.

## 0.9.0-preview.3 — mod-manager packaging

- Simplified verification to a manual release checklist, deterministic native persistence tests and one build-inventory validator; removed the certificate-report framework.
- Grouped the runtime payload and documentation under `Content/Paks/~mods/DenDesigner/`, following the Off Duty and Squad Six Reforged package layout.
- Added matching `modinfo.json` and `zcom-mod.json` with a player-facing description, stable mod ID and standalone IoStore requirements.
- Added metadata/version validation, nested integrity records and instructions for replacing older flat pak installations.
- Kept runtime asset paths, layout storage and the separate creator downloads intact.
- Removed the unused prototype-layout converter, its tests and downloads; the project uses native mod saves throughout.

## 0.9.0-preview.2 — pak-only project refresh

- Verified prop-pack authoring, fresh-editor reload, cooking and packaging in both prepared public kits (Linux UE 5.6.1).
- Added a standalone creator bundle with the minimal provider reference and editor helper source; no private merged kit required.

- Retired the old override plugin, feasibility prototype and obsolete probes from this repository.
- Added native UI templates, direct JSON catalog generation, fixed gizmo reference cases and self-contained sample art sources.
- Removed the four feasibility assets from the cooked editor; runtime asset and save identities remain stable.
- Reorganized documentation around players, development, architecture, verification and prop-pack creators.
- Stable release gates now explicitly include compositions and prop packs. The development sample remains separate.

## 0.9.0-preview.1 — prop packs

- Added schema-1 registration for independent static-mesh packs, with a Prop packs collection, validation and budgeted discovery.
- Added creator manifest/scaffolding and independent build tooling.
- Added a separate Arcade & Halloween development pack. Fixed source face winding and used opaque cabinet materials to prevent overlapping surfaces.
- User verified the textured cabinet and pumpkins in game; core registration received focused standalone and compiled checks.

## 0.8.0 previews — compositions

- Saved multi-prop arrangements, repeatable group placement and whole-group undo/redo.
- Added thumbnail cards that render the complete composition and refresh on replacement.
- Verified focused composition and thumbnail workflows with UE4SS disabled.

## 0.7.1 preview — architecture selection

- Made Floors, Walls and Structure independent selection switches, including oversized floor pieces.

## 0.7.0 — first pak-only release

- Moved editor runtime, camera/input, persistence, catalog, Storeroom, settings and thumbnail generation into cooked Blueprints.
- Passed standalone release regression and exact-build acceptance, including mission-success return.

Earlier development history remains available in Git.
