# Changelog

## 0.9.0-preview.2 — pak-only project refresh

- Verified prop-pack authoring, fresh-editor reload, cooking and packaging in both prepared public kits (Linux UE 5.6.1).
- Added a standalone creator bundle with the minimal provider reference and editor helper source; no private merged kit required.

- Retired the Lua edition, MXM integration, old override plugin, feasibility prototype and obsolete probes from this repository.
- Removed Lua build/test dependencies: native UI templates, direct JSON catalog generation, fixed gizmo reference cases and self-contained sample art sources.
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
- Added optional one-time migration from the original edition's JSON layouts.
- Passed standalone release regression and exact-build acceptance, including mission-success return.

Earlier development history and retired source are preserved outside the active project during the
2026-10-20 refresh. The Lua edition is no longer built or packaged here.
