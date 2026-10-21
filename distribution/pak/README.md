# Den Designer — pak edition

Decorate the Den with the game's props. This edition runs entirely from cooked Blueprint assets:
no UE4SS, Lua, MXM, Python, or additional DLL is required to play.

The archive's `manifest.json` identifies its exact version and files. Stable releases include
`acceptance.json` with their verification scope and container hashes; preview packages have not
completed full in-game release acceptance.

## Install

1. Close the game.
2. If upgrading from the Lua edition, first keep a copy of
   `%LOCALAPPDATA%\SWZeroCompany\Saved\ZComDen`. Disable only the old **Den Designer** mod in your
   mod manager. For a manual installation, move the `ZComDen` folder out of
   `SWZeroCompany\Binaries\Win64\ue4ss\Mods` to a backup location. Keep its contents intact.
   UE4SS may remain installed for other mods.
3. Remove the old `ZComDen_P.pak`, `ZComDen_P.ucas`, and `ZComDen_P.utoc` from the game's
   `SWZeroCompany\Content\Paks\~mods`, keeping backup copies. Do not change other mods' files.
4. Copy this archive's `Content` folder into the game's **SWZeroCompany** folder, alongside its
   existing `Content` and `Binaries` folders. The result must be:

   ```text
   SWZeroCompany/Content/Paks/~mods/DenDesignerGF_P.pak
   SWZeroCompany/Content/Paks/~mods/DenDesignerGF_P.ucas
   SWZeroCompany/Content/Paks/~mods/DenDesignerGF_P.utoc
   ```

5. Load your campaign and enter the Den. Press **Ctrl+Home** to open Den Designer.

Install all three files from the same version. Close the game before replacing them on an update.
Keep one copy of each; renamed copies from a mod manager can still be loaded by the game.
The pak edition and Lua edition should not run together: both use Ctrl+Home by default and can
apply separate layouts to the same Den.

## Editing

- Fly with WASD, Space up, Ctrl down, and Shift for faster movement. Hold RMB to look around.
- Click a prop to select it. Use Move, Rotate, or Scale in the selection panel, or T to cycle
  the gizmo. Axis and plane handles constrain the edit. Numeric fields accept values with Enter.
- Drag along a surface; Shift-drag moves vertically. Q/E or the wheel rotate. Use +/− to scale.
- C duplicates, X stores, and Z/Y undo or redo. The Storeroom restores stored props without undo.
- The catalog provides search, collections and thumbnails. Choose a prop, then click the world
  to place it. Shift-click places additional copies; Esc cancels placement.
- Grid and Range are on the top bar. Floors and Walls independently enable selection of their
  respective pieces; Structure controls the remaining architecture, such as ceilings and beams.
  Floors and walls do not require Structure to be on. Range limits selection distance.
- Settings contains camera speeds, background-task toggles and key bindings. Help displays the
  effective controls. F9 is reserved because it conflicts with an observed load/mod action.
- Save commits the layout. Done or the opening shortcut exits; unsaved changes require a choice.

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

## Bring layouts from the Lua edition

Use the separate **Den Designer Migration** download. It converts Home/campaign JSON layouts,
their backups, drafts and presets without modifying the originals. Python 3.10+ is needed only
for this optional one-time conversion; it is not a dependency of the mod.

The pak edition does not directly read JSON layouts. The migration installer previews its writes
and refuses to replace a different native layout. Legacy drafts require explicit recovery because
the old format did not record which saved revision they were based on.

## Uninstall

Close the game and remove the three `DenDesignerGF_P` files. Keep the mod's Saved directories
if you might reinstall. No campaign-save repair is needed.

To return to the Lua edition, restore its backed-up mod folder and three `ZComDen_P` files.
Your original JSON layouts remain available. Edits made in the pak edition are separate and are
not automatically converted back to JSON.

## Verification

The 0.7.0 stable release passed full standalone regression. The current 0.9.0 previews add
compositions and prop packs with focused checks; they have not repeated the entire release matrix.
Always use the archive manifest and any acceptance certificate to identify its verification scope.

The release regression exercises the editor with UE4SS disabled, including automatic startup,
selection, placement, numeric transforms, all 16 gizmo handles, surface and height dragging,
Storeroom, history, preferences, layouts/presets, draft recovery, migration and thumbnails.
The mission-return check uses a separate test plugin to trigger the game's mission-success
sequence; that plugin is not included. The unreleased Tidy Bar preset is not included.

The mod edits visible static-mesh components. Animated characters and individual instances in
instanced-mesh components remain outside the supported editor scope; unsupported picks are
reported rather than saved as edits. Back up your mod data before game updates: changed game
assets can leave unavailable entries, which remain listed for review in the Storeroom.
