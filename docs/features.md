# Den Designer — feature guide

This guide describes the `1.1.0-preview.18` runtime. The [player guide](../distribution/pak/README.md)
covers installation, updating, uninstalling and data locations. The [Nexus copy](nexus/description.bbcode)
is the publication version of this feature overview.

## Opening the editor

Enter the Den and interact with the console in the office. Its distant pencil marker becomes
**OPEN DEN DESIGNER** with your exploration interaction key when you approach. The alternative
opening shortcut is **Ctrl+Home**, which works from elsewhere in the Den once it has loaded.
The shortcut's key and modifier can be changed in Settings.

The editor hides the game HUD and gives you a flying camera. Closing returns to the game's camera,
HUD and controls. Choose **Save** to commit your layout and **Done** to leave. If you have unsaved
changes, the editor offers Save, Discard or Keep editing. The opening shortcut also requests exit.

## Workspace and camera

- **Menu bar:** Select, Move, Rotate and Scale tools; grid and nearby-prop snapping; selection
  range; Floors, Walls and Structure filters; history, Help, Settings, Save and Done.
- **Left library:** Catalog, Storeroom, Compositions and Layouts. Click the active tab again to
  close it.
- **Right inspector:** the selected prop's position, rotation, scale and rotation pivot. Settings
  take the inspector's place while open.
- **Status bar:** mouse controls and feedback about selection, placement and pending work.
- **Camera:** fly with WASD, Space to rise and Ctrl to descend. Hold the right mouse button to
  look around; Shift increases flight speed. **F** frames the selected prop.

Help displays the effective editor key bindings, including your replacements.

## Finding and placing props

The Catalog contains thousands of static meshes from the installed game. Search by name or tags,
browse collections, and return to recently used props. Thumbnail cards show the meshes before you
place them. Compatible prop packs get their own shelves within the Prop packs collection, and
pack names, authors and tags participate in catalog search.

Choose a catalog prop to start a placement preview. Move the pointer to position it, turn it with
the wheel or Q/E, and use +/− to scale it. Click to place it, Shift-click to place additional copies,
or Esc to cancel. Placement loads the required assets before showing the preview.

Thumbnails are generated in the background and cached for later visits. Generation can be disabled
in Settings. Composition thumbnails show the whole saved arrangement rather than just one part.

Props placed by Den Designer are decorations. Placing a mesh does not give it the original game
object's interactions, scripts or gameplay behavior.

## Selecting and transforming

Click an editable prop to select it. The Select tool hides the gizmo; Move, Rotate and Scale expose
handles for their respective operations. **T** cycles tools. Axis handles constrain an edit to one
axis; supported plane handles constrain movement or scaling to a plane.

You can also drag a prop along a surface, hold Shift while dragging to lift/lower it, rotate with
Q/E or the mouse wheel, and scale uniformly with +/− or the keypad equivalents. Shift+wheel makes
fine turns. If you rebind the fast-flight key, that replacement also controls fine wheel turns and
height dragging.

The inspector accepts numeric position, angle and scale values; press Enter to apply a field.
Position/angle fields display two decimal places, while entered values retain their precision.
Arrow keys nudge the selection relative to the camera's nearest cardinal direction; Page Up/Down
nudge vertically. Nudges use the grid step, or 5 cm with the grid off.

**C** duplicates the selected prop, preserving its supported mesh/material appearance. **R** resets
an existing scenery edit to its captured baseline. For a placed prop, Reset straightens pitch/roll
and returns scale to 1 while keeping its yaw.

### Rotation pivots

Choose **Centre**, **Bottom**, **Top** or **Original** beside the rotation fields, or use
**Settings → Rotation → Rotate around**. Centre/Bottom/Top use the mesh's bounds; Original uses its
authored origin. Bottom and Top follow the prop's local vertical axis when it is tilted.

The rotation gizmo marks the chosen point. Gizmo, numeric, wheel and key rotations all use that
pivot. Changing the pivot does not move the prop. Move and Scale gizmos use the bounds centre;
scaling holds that centre in place. The pivot choice persists between sessions.

## Grid, nearby-prop snapping and selection filters

These are separate controls:

| Control | Behavior |
|---|---|
| **Grid** / **G** | Cycle Off, 5, 10, 25 and 50 cm steps. |
| **Snap** | Toggle snapping to nearby props for the current editing session. Settings store its default. |
| **Range** | Cycle selection reach through 10, 20, 40 and 100 m. |
| **Floors** | Allow selection of floor pieces. |
| **Walls** | Allow selection of wall pieces. |
| **Structure** | Allow selection of other architecture, such as ceilings and beams. |

Floors and Walls work independently of Structure. The highlighted controls are enabled. Initial
preferences have Floors on, Walls and Structure off, a 20 m selection range and the grid off.

Nearby-prop snapping matches bounding boxes: place objects flush against a side, align their edges
or centres, or stack them with a height drag. It also matches centres to edges and edges to centres.
Different movement axes can follow different neighbours when their orientations align, including
quarter-turn differences. Gizmo snapping respects the active axis or plane.

Guide lines and a cursor label show the match. The detection range increases with camera distance;
Settings offer a close-up distance of 2–30 cm, default 8 cm, and a guide toggle. Floor-sized pieces
are excluded as nearby-prop snap targets; walls can still be targets. Grid snapping runs first.
**Hold Alt to bypass nearby-prop snapping**; this does not switch the grid off.

## Storeroom and undo/redo

**X** or **Delete** stores the selected prop. A placed prop moves into the Storeroom; editable
existing scenery is hidden by its saved edit. **H** opens the Storeroom, where you can search the
stored list, restore an entry, or restore all. Storing is not a permanent asset deletion.

The unavailable list retains edits that could not be applied in the current Den, including missing
pack meshes or game objects. They remain part of the layout. You can forget an unavailable edit;
Undo can bring that entry back. Restoring a missing asset requires the corresponding content to
be present again.

**Z** undoes and **Y** redoes edits in the current editing session. A completed drag and a placed
composition are grouped into single history steps. History is for the active session; restoring
stored props does not require an old undo history.

## Home, campaign layouts and presets

- **Home:** one saved decoration layout shared by campaigns that do not have their own copy.
- **Campaign copy:** give the current campaign its own layout, based on the current document.
- **Return to Home:** switch the current campaign back to the shared layout through Layouts.
- **Named presets:** save arrangements of the whole layout for later loading. Stored props are
  included. Loading a preset replaces the working layout; saving/deleting presets has its own
  library operations and confirmations.

The coordinator selects and applies the appropriate saved layout when the Den loads, without
requiring you to open the editor. It handles streamed scenery and reapplies the layout on return
from a mission. Decoration data is held in the mod's own saves, separately from campaign saves.

## Compositions

Compositions are reusable groups of up to **128 editable props**, available across campaigns.

1. Open **Compositions**, choose **Select parts**, and click props to add/remove them. Selected
   parts have a gold outline. Finish selecting, name the group and choose **Save composition**.
2. Choose a thumbnail card and **Place selected**. The group preview appears after its assets load.
3. Position it with the pointer, turn it with the wheel or Q/E, and scale it uniformly with +/−.
   Click to place, Shift-click for more copies, or Esc to cancel.

Groups preserve relative positions, rotations, scales and supported material overrides. Their
placement anchor is the bottom-centre of their bounds. Placed parts can be edited individually;
compositions are templates, not permanently linked objects. Placing one does not replace the rest
of your layout. Replacing or deleting a library entry asks for confirmation and leaves existing
placed copies intact.

Library cards have names, part counts and cached pictures of the complete arrangement. Replacing a
composition refreshes its picture. The composition library saves immediately, separately from the
active layout's Save action and draft. Unsupported/missing parts prevent capture or placement.

## Prop packs and creator tools

Compatible, independently installed prop packs extend the Catalog. Their meshes use the same
placement, transformation, duplication, Storeroom, composition and persistence workflows as the
built-in catalog. Invalid/conflicting registrations are skipped with feedback in the catalog.

Install a pack's matching `.pak`, `.ucas` and `.utoc` while the game is closed, then restart.
Removing a pack keeps its entries in your layouts; reinstalling content at the same asset paths
lets those meshes resolve again. If an update changes a mesh's appearance, delete its cached
thumbnail to generate a fresh one.

The runtime does not include a prop pack, sample artwork or an arbitrary model importer. The
separate [creator tools](../authoring/prop-packs/EDITOR-GUIDE.md) use the public SDK/base Modkit and
remain a preview pending Windows editor testing. Their availability is separate from the runtime
release; they are not a player requirement or part of the runtime download.

## Settings and controls

Settings save automatically and apply immediately. Reset settings restores defaults.

| Setting | Default | Choices/range |
|---|---|---|
| Flight speed | 900 cm/s | 200–3000 cm/s |
| Fast flight multiplier | 3× | 1–8× |
| Look sensitivity | 2.5 | 0.5–10 |
| Snap to nearby props | On | On/Off |
| Snapping guides | On | On/Off |
| Close-up snap distance | 8 cm | 2–30 cm |
| Rotate around | Centre | Centre, Bottom, Top, Original |
| Draft autosave | On | On/Off |
| Generate thumbnails | On | On/Off |
| Open editor modifier/key | Ctrl+Home | Supported keyboard key and Ctrl, Shift, Alt or no modifier |

Rebind camera movement, fast flight, Q/E turning, Store, Copy, Undo, Redo, Focus, Reset, Grid,
Catalog, Storeroom, Layouts and gizmo cycling by clicking their key fields and pressing replacements.
Esc cancels key capture. Conflicting assignments are rejected; **F9 is reserved**. The fast-flight
key also controls fine wheel rotation and height dragging.

Mouse buttons/wheel, Alt's nearby-snap bypass, Esc, Delete, arrow keys, Page Up/Down and +/− remain
fixed. The editor is designed for keyboard and mouse, with English interface text.

## Persistence, drafts and backups

Layouts, presets, compositions and settings use rotating save banks under:

```text
%LOCALAPPDATA%\SWZeroCompany\Saved\SaveGames\ZComDen\Native\v1
```

Back up that entire directory together. Do not mix or rename individual banks from different
backups. Thumbnail images are separate, under `Saved\ZComDen\thumbs`, and can be regenerated.

Draft autosave records unfinished work. After an interrupted session, opening the editor offers
recovery; the draft does not silently replace the saved layout. Explicit **Save** is still how you
commit the layout. Incompatible or damaged data produces feedback rather than silently replacing
it with a new layout.

Uninstalling removes the runtime's placed props and edits from play, while your campaign saves
remain usable. Keeping the mod's data allows reuse after reinstalling. See the player guide for
removal paths and migration from an older flat-container installation.

## Editing boundaries

The editor runs in the Den and supports eligible, visible static-mesh components. Animated
characters, individual instances in instanced-mesh components, protected interactive/gameplay
objects and unsupported objects supplied by other mods are outside its editable scope. A rejected
selection reports why it cannot be edited. Compatible prop packs are the supported way to add
independent mesh content.

Game updates or other mods that change Den objects, asset paths or streaming can affect existing
edits. Unavailable entries are retained for review. Back up mod data before changing your content
setup. Build/package checks and compiled kit tests do not establish every in-game combination;
release verification is recorded separately in the [verification guide](verification.md).
