## 0.9.25 (HoloNet bridge 0.9.20 unchanged; preview for in-game testing)

- **The rail folds while you place**: placing from the Catalog or Compositions
  (including HoloNet's Add and place now) folds the rail to icons. A drop, Esc
  or a load that fails puts it back as you pinned it; Shift-click keeps it
  folded while you place more. Show labels or the code icon unfolds it at once.
  Storeroom Restore is unchanged: it puts props back without a placing step.
- The code field's hint reads "Code or link", which fits the field.

## 0.9.24 (HoloNet bridge 0.9.20 unchanged; preview for in-game testing)

- **Fold to icons**: a button at the bottom of the rail folds it to a 64 px
  column of icons, and the open entry's content moves along beside it. Icons
  have tooltips, the Storeroom and My Shares counts become badges, and the
  HoloNet header becomes a divider that carries the connection dot. The code box
  becomes one icon: clicking it shows the labels again and puts the cursor in
  the code field. Show labels unfolds the rail. The choice is saved in
  preferences (`rail_labels`) and used the next time the editor opens.

## 0.9.23 (HoloNet bridge 0.9.20 unchanged; preview for in-game testing)

- Fix: reopening the editor loads My Shares and the Browse gallery again (they
  stayed empty until Refresh, because the new window was taken as already loaded).

## 0.9.22 (HoloNet bridge 0.9.20 unchanged; preview for in-game testing)

- **Clean names for imports**: a build imported from HoloNet is saved under its
  title, with its code kept as metadata (`ShareCode`) instead of in the name.
  If that name is taken, it falls back to "<title> <code>". IN LIBRARY and
  "already imported" use the code. Once per session, earlier imports named
  "<title> <code>" get their code moved into the metadata and, when the title is
  free, are renamed to it.
- **HoloNet loads early**: opening the editor connects to HoloNet and loads My
  Shares, so the rail's dot and count show before HoloNet is opened. Import
  waits for a running request (such as the window's first load) instead of
  cancelling it; Cancel also drops a waiting import.
- Fix: the footer no longer stays on "Contacting HoloNet…" after a request
  finishes, and shows the import result.

## 0.9.21 (HoloNet bridge 0.9.20 unchanged; preview for in-game testing)

- **One window** for the library and HoloNet (approved board "One window"): a
  labelled rail on the left edge with Your Den (Catalog, Storeroom, Compositions,
  Layouts) and HoloNet (Browse, Dens marked Soon, Share a build, My Shares,
  Account), and Have a code? at the bottom. The open entry's content sits beside
  the rail: the 470 px library panels, or HoloNet widened to the screen's right
  margin. HoloNet's own rail is gone. The rail stays up when nothing is open.
- Each content area has an X that closes it. The Storeroom and My Shares entries
  show their counts once listed; a green dot after HOLONET shows a connection.
- Import (Have a code?) opens HoloNet on Browse first, so its progress shows.

## 0.9.20 / HoloNet bridge 0.9.20 (Phase 4; not yet built or tested in game)

Versions restart at 0.9.20 ahead of 1.0.0; this follows 1.1.0-preview.22.

- **HoloNet window** replaces the docked Community panel: a centred window with
  Browse (search, Newest / Most imported, Only what I can use, cards with IN
  LIBRARY, detail pane with readiness, parts, footprint and code, Add to my
  Compositions, Add and place now, Get the prop pack on Nexus), Dens (coming soon),
  Have a code?, Share a build, My Shares and Account. "Connected as <name>" in the
  title bar. Full Den publishing placeholders are gone.
- **Sharing**: picking a saved composition checks it at once and suggests updating
  the share with the same title (same code, next revision, What changed) or
  sharing as new. Shares declare the prop packs used (from loaded packs, with
  their Nexus links) and the footprint, and send a 512 px preview when the card
  has one. **Share** on the Compositions panel opens it with that composition.
- **Bridge**: imports HoloNet's build format (prop packs, unlisted mods, any
  characters), one server setting, zcom.app and share.zcom.app links, server
  paging and search, My Shares, What changed, 512 px previews, card footprints.
- **Bridge is one file**: `den-community.exe` is gone; HoloNet runs on guarded
  threads inside `version.dll`. A crash in bridge code stops HoloNet (with a
  "restart the game" message), not the game. The key now lives in game memory.
  The installer removes 0.9.19's `den-community.exe`.
- Bridge fixes: under Wine/Proton a stalled server could hold a request until
  the 25-second deadline (Wine ignored the response timeout); now 6 seconds.
  A cancelled share deletes its unfinished upload.
- `native/community/e2e/run.sh`: Wine end-to-end tests of the bridge, including
  caught crashes, cancels, timeouts and fuzzed input.
- In-game test fixes: IN LIBRARY no longer disappears when a card's preview
  loads, and appears right after an import; the detail preview is full size;
  Add and place now starts placing; picking a composition finds the share to
  update even while My Shares is still loading, so Update needs one click.
- **Prop packs**: optional `nexus_url` in pack.json and the in-editor tool, checked
  the same way as HoloNet (a Star Wars Zero Company page on nexusmods.com; else a
  Nexus title search). `BP_DenPropPack` gains `NexusURL`.
- Tools: `tools/build/lint_specs.py` (offline Blueprint spec checks) and
  `tools/build/simulate_specs.py` (runs spec logic in tests).

## 1.1.0-preview.22 / Community bridge 0.1.0-preview.10

- Restore local WBP_DenCompositions creation/library/placement; add distinct
  WBP_DenCommunity and toolbar navigation with the same editor style.
- Public service-backed native cards, search/paging, detail/requirements view,
  revision-pinned downloads, bounded local preview rendering and cache reuse.
- Separate public selection, local upload source selection, reviewed snapshot,
  forms, account state and explicit download-to-library actions.
- Preserve headless transport, authenticated publishing and PNG padding fix;
  leave Dens and Full Den publication visibly unavailable.

## Community bridge 0.1.0-preview.9 (pak preview.21 unchanged)

- Fix cached-preview upload rejection caused by the engine PNG exporter writing
  allocator slack after IEND. Validate CRCs/structure and send only the complete
  cached PNG stream; keep server validation strict and preserve staged retry IDs.
- Report fixed specific messages for thumbnail/payload/metadata/revision/quota and
  service failures. Never reflect arbitrary response bodies into the game.
- Verified eight actual cache streams against service validation, 79 Python tests,
  and the isolated staged native transport with a padded synthetic cache image.

## 1.1.0-preview.21 / Community bridge 0.1.0-preview.8

- Fix the preview.20 startup crash caused by invalid serialized fields in the
  cooked editor host. Separate state/leaf helpers into BP_DenEditorState and
  split transform/help graphs while preserving the Community UI.
- Require deserialization of every cooked export and Blueprint script before
  packaging. Parser-reported errors are failures even if the parser exits zero.
- Preview.20 is withdrawn. Source compilation and kit VM checks alone did not
  detect its shipping serialization failure.

## 1.1.0-preview.20 / Community bridge 0.1.0-preview.7

- Dedicated in-game Community areas for Browse, Upload and Account; removed the
  desktop connection/publishing form and focus activation.
- UMG saved snapshot review, metadata, requirements, progress, retry, result links
  and copy controls; retained authenticated staged composition publication.
- Explicit unavailable Full Den state, in-panel saved-preset selection and
  save-current-as-new-preset action. No Full Den endpoint is used or claimed.
- Close/cancel invalidation, masked credential clearing, retained recoverable forms
  and separate reviewed upload identity.

# Changelog

## 1.1.0-preview.19 — experimental Community test import

- Add a bounded, token-scoped Community request and value import boundary to the
  composition panel, retaining the local library, thumbnail and placement workflow.
- Prepare a separate standalone native bridge using a `version.dll` proxy and a
  short-lived HTTPS worker; no UE4SS, Python installation or engine hooks required.
- Publish the reviewed `DenDesignerTest01` monitor composition and its versioned
  read-only API route. This native slice deliberately rejects unsupported assets,
  packs, material overrides, media and noninteger transforms.
- See `docs/community-verification.md` for exact test scope. Kit or worker results
  must not be treated as shipped-game UI/rendering verification.

## 1.1.0-preview.18 — selection after adding and restoring props

- Extend incremental selection updates to placement, restoration, undo and redo. Only the
  changed props are refreshed; normal edits no longer restart a full Den scan.
- Retain consecutive edits until their index updates are consumed, remove destroyed candidates,
  and refresh restored no-collision props without losing a pending pick. Full-layout replacements
  and invalidated change histories retain the complete-scan fallback.

## 1.1.0-preview.17 — selection after storing props

- Storing a prop with Delete/X now removes only its cached selection candidates instead of
  restarting a scan of the entire Den. Other props remain selectable after the store finishes.
- Index-reuse hints are tied to their world generation so Undo, restoration and later scene
  changes still rebuild the index when needed.

## 1.1.0-preview.16 — console icon fit

- Shrink the office console pencil icon by 10% around a centered pivot, with centered
  horizontal and vertical layout so the complete symbol stays in the middle of the circle.

## 1.1.0-preview.15 — console label and distant icon

- Supply **OPEN DEN DESIGNER** and the game's edit icon on the live interaction action. The game
  rebuilds non-ability actions with empty presentation data, which left preview.14 showing only
  the key and an empty distant marker despite the configured label.

## 1.1.0-preview.14 — visible office console prompt

- Added the native exploration indicator missing from the office console, so the game can show
  its interaction key and **Open Den Designer** label. The indicator hides while editing and is
  removed when the console unloads or the coordinator shuts down.

## 1.1.0-preview.13 — office console interaction

- The office console (`SM_HUB_ConsoleLocks_3x1`) now offers **Open Den Designer** through the
  game's normal exploration interaction. The opening shortcut remains available.

## 1.1.0-preview.12 — startup crash fix

- Split panel creation into individual Blueprint functions to avoid malformed cooked bytecode in
  `CreateEditorPanels`, which caused preview.11 to crash during game startup.
- Retains the cursor restoration and wheel rotation fixes.

## 1.1.0-preview.11 — wheel rotation fix

- Removed the Alt+wheel scale binding after preview.9 testing found it scaling on plain wheel input.
  Wheel rotates, Shift+wheel makes fine turns, and +/− (including the keypad) scales.

## 1.1.0-preview.10 — cursor on editor entry

- Restore the visible cursor, editor input mode and viewport focus after hiding the game HUD, then
  retry once on a later engine frame so the cursor does not require a click to appear.
- The deferred restore respects camera-look and text/key input focus, and is cancelled on close.

## 1.1.0-preview.9 — gizmo anchors and rotation pivots

- Move and Scale gizmos now sit at the prop's bounds centre, including meshes with an offset authored origin.
- Added a rotation pivot choice: Centre (default), Bottom, Top or Original. Change it beside the inspector's
  rotation fields or in Settings. Bottom and Top follow the prop's local vertical axis as it turns.
- Rotation rings, numeric angles and wheel/key turns keep the chosen point fixed; the gizmo marks that point.
  Scale handles keep the bounds centre fixed. Each edit's position and rotation/scale share one undo step.

User-reported regression checks (2026-10-26): compositions save, place and generate icons; layouts save
and apply; saving/reloading and exiting/relaunching the game preserve edits. Plain wheel incorrectly
scaled while Shift+wheel still fine-rotated; the source fix is listed above, pending in-game retest.

## 1.1.0-preview.8 — bounds snapping

- Moving a prop snaps it to nearby props by their bounding boxes: flush against a side, aligned
  edges or centres, or stacked on top with a Shift height drag. Gizmo move handles snap only
  along their axis or plane. Grid snapping still applies first.
- Also matches a prop's centre to a neighbour's edge and its edge to a neighbour's centre, and each axis
  can snap to a different neighbour facing the same way (or turned 90°), for corners and rows.
- The snap range grows with camera distance (about 10 pixels on screen), never below the snap distance.
- Guide lines and a label beside the cursor show the snap. Hold Alt to move freely.
- SNAP toggle on the menu bar; Settings add the default, guides and the close-up snap distance (2–30 cm, default 8).
- Floor-sized pieces are ignored as snap targets; walls are kept for placing props against them.

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
