# Architecture

Den Designer is a content-only Unreal Game Feature in the `/DenDesignerGF/` namespace.
ZComAuthoring constructs Blueprint classes and graphs in the development editor; only cooked assets
ship in the player runtime archive. The runtime does not call Python, Lua, an injected DLL or the editor-only authoring plugin.

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
subsystem is not used to store decoration data. Existing JSON layouts are supported through the
separate one-time migration utility, not an embedded Lua runtime.

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
