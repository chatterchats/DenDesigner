# Den Designer v0.4.1

Decorate the Den, the way FFXIV's housing editor lets you decorate a house. Fly a free camera around the Den, pick up
the furniture that's there and move, turn, scale, copy or store it, and place any of nearly 5,000 props from across
the game. Your Den comes back the same every time you return to it.

Nothing is written into your save games. Layouts live in their own folder (see "Where things are saved").

## Install

Needs [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) for Zero Company.

Extract the zip into the game's `SWZeroCompany` folder (the one with `Binaries` and `Content` in it). That puts:

- `Binaries/Win64/ue4ss/Mods/ZComDen/` (the mod)
- `Content/Paks/~mods/ZComDen_P.pak`, `.ucas` and `.utoc` (the editor's camera, toolbar and panels)

Optional: the Mixamoo Mod Config Manager (MXM, on Nexus Mods) adds Den Designer's settings to its F2
menu: keys, camera speed and more. Without it the defaults below apply.

## Use

In the Den, while you're walking around, press **Ctrl+Home**. The camera lifts off and the toolbar opens.

| | |
|---|---|
| **W A S D**, **Space** / **Ctrl** | fly; up and down |
| **Shift** | fly faster |
| hold **right mouse** | look around |
| **left click** | select a prop (gold outline); drag it to move it along floors and tables |
| **Shift** while dragging | lift it up or down |
| **wheel** or **Q** / **E** | turn it (Shift + wheel: one degree at a time) |
| **+** / **-** | scale it |
| **arrows**, **Page Up** / **Page Down** | nudge it |
| **X** or **Delete** | store it (hide it; the Storeroom gets it back) |
| **C** | copy it |
| **R** | reset it (a Den prop goes back where the Den had it) |
| **F** | fly to it |
| **Z** / **Y** | undo / redo |
| **G** | grid snap: off, 5, 10, 25, 50 cm |
| **Tab** | the catalog |
| **H** | the storeroom |
| **L** | layouts and presets |
| **Esc** | cancel a placement, deselect, then leave |

The panel at the bottom left shows the selection's exact position, rotation and scale: type a number and press
Enter.

**Catalog (Tab).** Every prop in the game, by shelf (Den furniture, crates, Bespin, Outer Rim, ...) or by search.
Click one and it follows the mouse; click in the Den to place it. **Shift+click** places another and keeps going.
Pictures are made the first time a shelf opens and kept afterwards.

**Storeroom (H).** Everything you stored, with pictures: click one to put it back, or restore everything. Below it,
edits still waiting for their object: the Den changes as the story goes on, so an edit to something the Den hasn't
built yet waits until it appears. Click one to forget it.

**Layouts (L).** By default every campaign shares one layout, the *home* layout. **Give this campaign its own
layout** makes a copy just for this campaign (the others keep home); you can switch back at any time. **Presets**
are named snapshots: save what you have, and load it again later or in another campaign. Loading is one undo step.

**Leaving.** With unsaved changes, Esc or Exit asks: Save, Discard or keep editing. If the game closes while you're
editing, the editor offers your changes back the next time you open it.

**What can't be edited:** characters, interactive objects (consoles, the holotable...), anything the story or
cutscenes use, and props other mods add. Walls, floors and girders are locked; the **Structure** button unlocks
them. Floor markings and decals can't be picked yet.

## Where things are saved

`%LOCALAPPDATA%\SWZeroCompany\Saved\ZComDen\`

| | |
|---|---|
| `home.json` | the home layout |
| `campaigns\<campaign>.json` | a campaign's own layout |
| `presets\` | your presets |
| `backups\` | the five previous versions of each layout |
| `thumbs\` | catalog pictures (safe to delete; they're made again) |

Delete the folder and the Den is exactly as the game made it.

## Settings (MXM, F2)

Open/close key and modifier (applies at the next game start), camera speed, look speed, starting grid snap and
reach, structure unlocked by default, unsaved-session recovery, catalog pictures, and every editor key above except
Esc, Delete, the arrows, Page Up/Down, +/- and the mouse.

## Uninstall

Delete `Binaries/Win64/ue4ss/Mods/ZComDen` and `Content/Paks/~mods/ZComDen_P.*`. The Den is back to normal at once;
your layouts stay in the Saved folder in case you reinstall.

## Problems

The log is `Binaries/Win64/ue4ss/Mods/ZComDen/zcom_den.log`. Every Den visit writes a line like
`Den | home layout (file) | 4 placed, 3 hidden, 3 moved | ...`, and the editor logs what it does.
