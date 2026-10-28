# Architecture

Den Designer is a content-only Unreal Game Feature in the `/DenDesignerGF/` namespace.
ZComAuthoring constructs Blueprint classes and graphs in the development editor; only cooked assets
ship in the player runtime archive. The runtime does not call Python, an injected DLL or the editor-only authoring plugin.

## Lifecycle and editing

`BP_DenRuntimeCoordinator` attaches to the game's modular GameState. It applies the selected layout
in `HUB_Root`, watches streamed content and owns the world-specific editor lifecycle. Travel closes
the editor and releases world references. A separate shortcut component opens the editor after the
Den is ready.

The editor host owns the UI, input, selection and camera session. Its camera is a view target;
it does not possess the player's pawn. Closing restores the game's view and input. Widgets send
messages through `BP_DenEditorBus`; queued runtime work handles loading and mutations outside widget
callbacks. Catalog searches, asset loading, registration and thumbnail jobs are incremental.

Services are generated from the correspondingly named `runtime_*.py` modules: world resolution and
apply, pick/surface, transforms/drag/gizmos, history, layouts/store/drafts, catalog/placement,
Storeroom, preferences/input, compositions and thumbnails. `ui_templates.py` supplies native widget
and input templates; `runtime_editor_assets.py` wires the bus, font styling and focus guards.

The editor UI has a menu bar (tools, grid/range, selection filters, history and saving), a library
dock on the left whose tabs open one panel at a time, an inspector dock on the right (Settings take
its place while open) and a status bar. Tools, tabs and filters show their state by tint, applied by
`StyleEditorToggle`. Icons come from `unreal/icons/*.svg`: `tools/build/render_icons.sh` renders them
and `unreal/scripts/editor_icons.py` imports them as UI textures before the widgets are authored.

Move drags snap to neighbouring props by their bounding boxes (`runtime_snap.py`, math in
`BP_DenSnapMath`). When a move begins, nearby props are taken from the picker's index; floor-sized
pieces are skipped. Each preview first finds the closest snapping neighbour, compared in its own
yaw frame; then every neighbour square to that frame competes per axis, so different axes can snap to
different props. Matches are flush faces, aligned minimums/centres/maximums, and centre-to-edge or
edge-to-centre. Only axes the drag may move snap: X/Y for surface drags, Z for Shift height drags,
and axes along a gizmo handle's line or inside its plane. The range is the snap distance or about
10 pixels at the prop's depth, whichever is larger. Grid snapping runs first; Alt skips neighbour snapping. Guide
lines are procedural overlay geometry (`BP_DenSnapGuides`), since shipping builds strip debug lines.
`tests/fixtures/snap_cases.json` holds hand-derived reference cases for the math.

Edit anchors (`runtime_pivot.py`) use mesh-local bounds, transformed with the selected component's full
rotation and signed scale. Move/Scale use the bounds centre; Rotate uses the saved `rotation_pivot`
preference (centre/bottom/top/origin). The drag captures its local anchor at press. Rotation and scale
previews compensate the component origin by the old minus new transformed anchor offset, so the selected
point stays fixed. `CommitSelectionPose` applies the same compensation to numeric and wheel/key rotations.
Drag history includes the position compensation with the angle/scale in one transaction. Stored transforms
remain component-origin transforms; the pivot preference does not change layout identities or mesh assets.

Editor entry applies cursor visibility, game/UI input and viewport focus after the game HUD transition
(`FinishEditorEntry`). A frame-counter deadline schedules one retry strictly after the opening engine
frame. It is consumed before applying, skips held camera-look or focused text/key fields, and is cleared
on detach; there is no ongoing focus/cursor override during editing.

Incremental world batches retain their mutation identities and the generation range they cover.
Consecutive batches accumulate until selection consumes them; cancellation and full-layout
replacement invalidate the journal. After world application finishes, selection snapshots the
previous index generation before revalidating the selected prop. A contiguous journal lets the
picker prune destroyed candidates and refresh only the static-mesh components of affected placed
actors or vanilla records, including additions, restores, undo and redo. Pending picks are restarted
against the refreshed candidates without a full scene index scan. Missing/unresolvable objects are
skipped; ordinary candidate visibility and lifetime checks remain in force.

Direct transform previews also have generation-scoped reuse hints. If no contiguous journal or
valid hint is available, selection retains the budgeted whole-Den index fallback. Initial indexing
consumes any old journal because its new world snapshot already covers those changes.

## Persistent identities

`ST_DenEntry` records placed, stored and vanilla component edits with stable keys, full object/asset
paths, transforms and supported material overrides. Layouts save values rather than live UObject
references. History records grouped before/after states; placing a composition is one transaction.

Struct and property GUIDs derive from published asset paths and field names. Keep those identities,
`/DenDesignerGF/Runtime/` class names and persistent slot names stable when refactoring. Visible UI
labels can change without changing saved identities.

Layouts, drafts, presets, compositions and preferences use dedicated Blueprint SaveGame objects in
`Saved/SaveGames/ZComDen/Native/v1`. Rotating banks and revision identities support recovery. Drafts
are explicitly recovered; they do not silently replace the saved layout. The game campaign-save
subsystem is not used to store decoration data. The editor reads and writes its native mod slots
directly through Unreal's SaveGame APIs.

Thumbnail PNGs remain under `Saved/ZComDen/thumbs`. Catalog/Storeroom previews use mesh paths;
composition previews use library revision and entry identities and render a snapshot of the whole
arrangement. Missing assets remain recorded so a returning pack or sublevel can resolve them later.

## Prop packs

A separate content Game Feature adds a child of `BP_DenPropPack` to the GameState and declares
DenDesignerGF as a dependency. Schema 1 carries pack identity and aligned metadata arrays with soft
mesh paths. Registration never loads every mesh upfront. The catalog validates providers, rejects
conflicting IDs and adds accepted rows under **Prop packs**. Stable full asset paths allow the usual
placement, storage, composition and persistence services to work with pack content.

The creator archives include a minimal provider base, not the sample pack's meshes or artwork.
Creator limits, materials/cooking constraints and update behavior are in the
[prop-pack guide](../authoring/prop-packs/README.md).

### Creator tooling

`DenPropPackEditor` is a content-only editor plugin: a stock Editor Utility Widget shell plus bundled
Python. Its Tools menu creates UMG controls and binds Python callbacks at runtime. No custom native
class or compiled module is required. `model.py` handles schema/filesystem checks, `service.py` handles
Unreal asset authoring and export, and `panel.py` manages the form and background job lifecycle.

Editable metadata lives in the source plugin's `Authoring/pack.json`, outside cooked Content.
Source plugins are enabled in the project descriptor and mount in the editor. New folders can mount
immediately when their paths have no spaces; otherwise the panel requests a one-time restart.
Registration uses stock Blueprint/DataAsset factories and reflected soft class paths, including in
the base modkit where the game class is absent. Export writes a separate shipping manifest.

Unreal objects are accessed only on the editor thread. The worker receives plain data, runs UAT and
UnrealPak, audits the cooked namespace and publishes a unique export only on success. Slate tick
callbacks report completion; reopening the tab retains an active job. The panel does not call the
older Python/Bash helpers or install into the game. The player pack contains no authoring scripts.
The older scripted route produces the same schema-1 contract and remains available for automation.

## Boundaries

Floors, Walls and Structure independently gate selection. Interactive/gameplay objects and other
protected actors remain guarded. Editable static-mesh components inside supported actors are handled;
animated characters and individual ISM/HISM instances remain outside the supported scope.

The current Linux cook workflow is established for this Blueprint runtime. It is not a guarantee
that arbitrary newly compiled material shaders will run in the Windows game. The sample uses
existing shipped engine parents and has been checked in game.

### Office console entry

`BP_DenOfficeConsole` adds a transient native `InteractableComponent` beside the loaded office
console mesh. It uses `IA_ExploreInteract` with **Open Den Designer**, without activating a game
ability or overriding map assets. A separate `BP_DenConsoleIndicator` derives from the native
`BitReactorWidgetComponent` and uses the shipped `WBP_TacticalExplorePrompts` widget, which reads
the interaction action/text and displays the current input binding. On the target game build,
`UInteractableComponent::DetermineValidInputActionAbilities` reconstructs non-ability actions
with only their input action, dropping configured text and icon. The console handles
`OnEnterNearInteraction` and `OnEnterInteraction` to populate the live `InteractableAction.Abilities`
with **OPEN DEN DESIGNER** and `ImageBank.Icon.Options.Edit`, preserving the input action and
ability tags. These component bindings run before the indicator view model's later proximity
listener reads the live action. The console caches its own prompt icon after locating the
indicator widget by attached actor; other interactables are excluded. The pencil renders at
90% scale around a centered pivot, with zero translation and centered horizontal/vertical
alignment of its 30 px container. Pending widget discovery is throttled and the
cached reference is cleared when its indicator is removed. Its manual lifetime follows
console availability, retries registration if the local indicator manager is not ready, and ends
with the console actor. Discovery checks the exact mesh asset and native Den map
namespace, scans at most 64 actor/component steps per frame, and retries while streaming. The
interaction follows the mesh bounds and becomes unavailable while the editor is open or the
console is hidden/unloaded. Its coalesced request goes through the coordinator's existing layout
preparation and mount path. The coordinator owns one interaction actor and destroys it on shutdown.
