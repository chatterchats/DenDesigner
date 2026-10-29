# Den Designer — pak edition

Decorate the Den with the game's props. This edition runs entirely from cooked Blueprint assets:
no UE4SS, Python, or additional DLL is required to play.

The **Compositions** toolbar destination is local: create, browse, place and delete
saved arrangements. **HoloNet** opens a window for zcom.app: browse and import other
captains' builds, share your own (updates keep their code and ask what changed), see
your shares, and connect your account. It needs the matching HoloNet bridge **0.9.20**
with this **0.9.20** pak; see its guide. The offline editor and local Compositions work
without the bridge.

The archive mirrors the game's `SWZeroCompany` folder. Its single component lives under
`Content/Paks/~mods/DenDesigner/`, with `modinfo.json` and `zcom-mod.json` beside the three containers.
The metadata identifies **Den Designer** by Chats and declares an IoStore mod with no UE4SS dependency.
Import the ZIP into your mod manager, or follow the manual installation steps below.

The component's `manifest.json` identifies its exact version, files and hashes. Its verification
scope covers build and package checks. Release notes describe the in-game testing performed.

## Install

1. Close the game.
2. If updating from 0.9.0-preview.2 or older (including 0.7.0), remove the old `DenDesignerGF_P.pak`, `.ucas` and `.utoc`
   directly inside `Content/Paks/~mods` before installing the new subfolder. Keep a backup outside
   `~mods`; do not load both sets. If a manager installed them, use its update/replace or uninstall
   workflow so it does not redeploy the old copy.
3. Copy this archive's `Content` folder into the game's **SWZeroCompany** folder, alongside its
   existing `Content` and `Binaries` folders. The result must be:

   ```text
   SWZeroCompany/Content/Paks/~mods/DenDesigner/DenDesignerGF_P.pak
   SWZeroCompany/Content/Paks/~mods/DenDesigner/DenDesignerGF_P.ucas
   SWZeroCompany/Content/Paks/~mods/DenDesigner/DenDesignerGF_P.utoc
   SWZeroCompany/Content/Paks/~mods/DenDesigner/modinfo.json
   SWZeroCompany/Content/Paks/~mods/DenDesigner/zcom-mod.json
   ```

4. Load your campaign and enter the Den. Interact with the office console to **Open Den Designer**,
   or press **Ctrl+Home** from anywhere in the Den. The console shows the game's edit icon at a
   distance, then your interaction key and **OPEN DEN DESIGNER** when nearby.

Install all three files from the same version. Close the game before replacing them on an update.
Keep one copy of each; renamed copies from a mod manager can still be loaded by the game.

## Editing

- The game's HUD hides while the editor is open and returns when you close it.
- Fly with WASD, Space up, Ctrl down, and Shift for faster movement. Hold RMB to look around.
- Click a prop to select it. Choose Select, Move, Rotate or Scale on the menu bar, or press T to
  cycle them; Select hides the gizmo. Axis and plane handles constrain the edit. The inspector on
  the right shows the selected prop's position, rotation and scale; its fields accept values with Enter.
- Move and Scale gizmos sit at the prop's bounds centre. Beside the rotation fields, click **Pivot** to
  cycle **Centre → Bottom → Top → Original**, or choose **Settings → Rotation → Rotate around**.
  The rotation rings mark that point; numeric angles and Q/E or wheel turns use it too. Bottom and Top
  follow the prop's local vertical axis when tilted. Original uses the mesh's authored origin.
  Changing the pivot moves the rotation gizmo; the prop stays in place. The choice is saved between sessions.
- Drag along a surface; Shift-drag moves vertically. Q/E or the wheel rotate. Use +/− to scale.
- Moving a prop near another snaps it flush against it, lines up its edges or centre, or (with
  Shift) stacks it on top; sideways and front-to-back can follow different neighbours. Guide lines
  and a label show the snap, which reaches further when the camera is further away. Hold Alt to place freely, or
  turn SNAP off on the menu bar. Settings set the default, the guides and the snap distance.
- C duplicates, X stores, and Z/Y undo or redo. The Storeroom restores stored props without undo.
- Catalog, Storeroom, Compositions and Layouts open from the tabs on the left; choose the open tab
  again to close it.
- The catalog provides search, collections and thumbnails. Choose a prop, then click the world
  to place it. Shift-click places additional copies; Esc cancels placement.
- Grid, Range, Floors, Walls and Structure are on the menu bar; highlighted ones are on. Grid shows
  its step and Range its distance; click them to change. Floors and Walls independently enable selection of their
  respective pieces; Structure controls the remaining architecture, such as ceilings and beams.
  Floors and walls do not require Structure to be on. Range limits selection distance.
- Settings contains camera speeds, background-task toggles and key bindings; it opens in place of
  the inspector. Help displays the effective controls. F9 is reserved because it conflicts with an observed load/mod action.
- Save commits the layout. Done or the opening shortcut exits; unsaved changes require a choice.

## Default controls

These are the defaults; **Help** shows your effective editor bindings.

| Control | Action |
|---|---|
| Ctrl+Home | Open the editor or request exit. The office console also opens it. |
| WASD; Space / Ctrl | Fly horizontally; rise / descend. |
| Hold right mouse | Look around. |
| Shift | Fast flight; fine wheel turns; height movement during a prop drag. |
| Left click / drag | Select / move along a surface. |
| Shift-click during placement | Place additional copies of a prop or composition. |
| Wheel or Q/E | Rotate the selection or placement preview. |
| +/−, including keypad | Scale uniformly. |
| Arrows; Page Up/Down | Nudge horizontally; nudge vertically. |
| T | Cycle Select, Move, Rotate and Scale tools. |
| F | Frame the selection in the camera. |
| C | Duplicate the selection. |
| R | Reset an existing scenery edit; straighten/reset scale on a placed prop, keeping its yaw. |
| X or Delete | Store the selection. |
| Z / Y | Undo / redo. |
| G | Cycle grid steps: Off, 5, 10, 25 or 50 cm. |
| Alt, held | Bypass nearby-prop snapping. Grid snapping remains independent. |
| Tab / H / L | Toggle Catalog / Storeroom / Layouts. |
| Esc | Cancel the current action or go back. |

Nudges use the grid step, or 5 cm when the grid is off. Resetting an existing scenery edit
restores its captured baseline. Storing a placed prop moves it to the Storeroom; storing existing
scenery hides it through the saved layout. The Storeroom has search and Restore all. Its unavailable
list also lets you forget an unresolved edit; Undo can restore that entry in the active session.

## Settings

Settings save automatically and apply immediately. **Reset settings** restores defaults.

| Setting | Default | Range/choices |
|---|---|---|
| Flight speed | 900 cm/s | 200–3000 cm/s |
| Fast flight multiplier | 3× | 1–8× |
| Look sensitivity | 2.5 | 0.5–10 |
| Snap to nearby props | On | On / Off |
| Snapping guides | On | On / Off |
| Close-up snap distance | 8 cm | 2–30 cm |
| Rotate around | Centre | Centre / Bottom / Top / Original |
| Draft autosave | On | On / Off |
| Generate thumbnails | On | On / Off |
| Open editor | Ctrl+Home | Supported key plus Ctrl, Shift, Alt or no modifier |

Click a keyboard binding and press its replacement; Esc cancels capture. Each configurable action
needs its own key, and F9 is reserved. Rebinding fast flight also changes the key used for fine
wheel turns and height dragging. Mouse controls, Alt's nearby-snap bypass, Esc, Delete, arrows,
Page Up/Down and +/− remain fixed. Keyboard and mouse are required for editing.

Grid, Range and the selection filters are on the menu bar. Range cycles 10, 20, 40 and 100 m.
Initial preferences have a 20 m range, grid Off, Floors On, Walls Off and Structure Off. The Snap
button changes nearby-prop snapping for the current session; Settings store its default. Floors
and Walls remain independent of Structure.

## Prop packs

Compatible prop packs add their own static meshes through **Catalog → All collections → Prop packs**.
Install all three of a pack's containers alongside Den Designer while the game is closed, then
restart. Each pack has its own shelf; names, authors and tags also work in the main search.
Thumbnails, placement, Storeroom and compositions work with registered meshes normally.

Use packs built for this game and Den Designer 0.9.0 or later. Do not mix different versions of
the same pack. Invalid registrations are skipped with a message in the catalog footer.
The Arcade & Halloween sample is a separate development pack; its cabinet is a decorative prop.

Removing a pack does not remove its entries from your layouts. Missing meshes cannot appear until
the pack is reinstalled at the same asset paths. Keep a layout backup before removing content.
If a pack update changes an existing mesh's appearance, remove its cached PNG from
`Saved/ZComDen/thumbs` to let the editor generate a fresh image.

## Compositions

Save arrangements of up to 128 editable props, then place more copies in any campaign.

The library uses thumbnail cards with a name and part count. Previews show the complete
arrangement, including its relative transforms and supported material overrides. Visible cards
generate their pictures automatically when thumbnails are enabled; cached pictures are reused
on later visits. Replacing a saved composition refreshes its preview. Picture generation does
not place anything in your layout or add undo steps.

1. Open **Compositions** and choose **Select parts**. Click props to add them; click again to
   remove them. All selected parts have a gold outline. Finish selecting when ready.
2. Enter a name and choose **Save composition**. The originals stay in place. Saving a name
   that already exists asks before replacing it.
3. Select an arrangement in the library and choose **Place selected**. The preview appears
   once all meshes and materials have loaded. Move the pointer to position it; wheel or Q/E
   turns the group and +/− scales it uniformly. Its anchor is the bottom-center of its bounds.
4. Click to place it, Shift-click for additional copies, or Esc to cancel. Each placement is
   one undo step. Once placed, its parts can be edited individually.

Relative positions, rotations, scales and supported material assets are preserved. The same
selection protections apply as elsewhere in the editor. Unsupported or missing parts prevent
capture or placement; a composition never replaces the rest of your layout. Deleting one from
this library asks for confirmation and leaves previously placed copies intact.

Compositions use separate rotating banks in the mod's native data directory below. They are
available across campaigns and are saved immediately, independently of the current layout draft.
This feature is available in the pak edition only.

## Layouts, presets and recovery

The Home layout is shared across campaigns. Layouts can give the current campaign its own copy,
return it to Home, or save/load named presets. Stored props are part of a layout and its presets.
Loading a preset replaces the working layout; **Save** commits the layout you want to use.
The appropriate saved layout applies when the Den loads and after mission return.

Den Designer writes its own slots under:

```text
%LOCALAPPDATA%\SWZeroCompany\Saved\SaveGames\ZComDen\Native\v1
```

These are **mod SaveGame objects**, separate from the game's campaign saves. Layouts, presets, compositions and
settings have rotating banks; keep the entire directory together when backing up. Do not rename
or combine individual banks from different backups. The thumbnail cache remains under
`Saved\ZComDen\thumbs`.

Draft autosave is enabled by default. After an interrupted editing session, opening the editor
offers recovery. The saved layout remains active until you choose to recover the draft.
Unavailable objects remain recorded and appear in the Storeroom's unavailable list.

## Uninstall

Close the game and remove `Content/Paks/~mods/DenDesigner`, or uninstall through the manager that
deployed it. If you still have an older flat installation, remove its three `DenDesignerGF_P` files
from `Content/Paks/~mods` too. Keep the mod's Saved directories
if you might reinstall. No campaign-save repair is needed.

## Compatibility and editing limits

The current runtime targets Steam build **25898267**, listed in `zcom-mod.json`. Check the archive
manifest for its exact version. Other builds and the EA App release are unverified. Build/package
verification and compiled Blueprint checks are separate from in-game testing; release notes record
the latter.

The editor supports eligible visible static-mesh components in the Den. Animated characters,
individual instances in instanced-mesh components, protected interactive/gameplay objects and
unsupported objects supplied by other mods are outside its selection scope. Rejected picks report
why they cannot be edited. Placed catalog meshes are decorations and do not acquire the original
object's gameplay interactions or scripts. The editor's interface text is in English.

Back up your mod data before game updates or changing your mod setup. Changes to game objects,
asset paths or streaming can affect saved edits; unavailable entries remain listed in the
Storeroom. Compatible prop packs are the supported route for independent mesh content.

For a problem report, include the game build, Den Designer version, other mods/prop packs, steps
to reproduce, on-screen feedback and a screenshot or recording where useful. If produced, the game
log is `%LOCALAPPDATA%\SWZeroCompany\Saved\Logs\SWZeroCompany.log`. Logs may include local paths;
review them before sharing.
