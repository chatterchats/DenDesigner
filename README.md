# Den Designer (ZComDenDesigner)

An FFXIV-housing-style Den editor for Star Wars: Zero Company. Player-facing description and controls:
[src/ZComDen/README.md](src/ZComDen/README.md).

Two halves:

- a **UE4SS Lua mod** (`src/ZComDen`) that keeps layouts outside the game's saves, applies them whenever the Den
  loads, and runs the editor;
- **kit assets** (`ZComDen_P` pak): the flying camera rig, the input actions and mapping context, and every panel.
  They're built headlessly from JSON specs by the SWZC Merged Kit's `ZComAuthoring` plugin; nothing is made by hand
  in the editor GUI.

## Layout

| Path | |
|---|---|
| `src/ZComDen/Scripts/` | `main` (composition), `den_watch` (Den arrival, reapply, file watch), `apply` (layout -> Den, single-object ops), `resolve` (bulk object lookup), `store` / `layout` / `json` (files, presets, drafts, backups), `editor` (edit mode), `history` (undo), `pick` (what's editable), `highlight` (stencil outlines), `catalog` + generated `catalog_data`, `thumbs` (picture studio), `keys` (rebinding); `hook_registry` / `actions` / `logging` as in the other mods; `MXM.lua` (MXM's client, unmodified). |
| `src/ZComDen/MXM/settings.lua` | The MXM settings schema. `values.lua` next to it is written by the menu and gitignored. |
| `unreal/specs/editor.py` | Generates `unreal/specs/editor/*.json` (committed for review): 21 input actions, the mapping context, `BP_DenEditorRig`, `WBP_DenToolbar`, the catalog item and list entries, `WBP_DenCatalog`, `WBP_DenLayouts`, `WBP_DenStoreroom`, `WBP_DenTransform`. |
| `unreal/specs/probe/` | The Phase 0 probe set (`--set probe`); `probes/kit_open.lua` needs it installed. |
| `unreal/ZComDen/` | The plugin the kit cooks (`RemapPluginContentToGame=True`). `Content/` is a build product. |
| `tools/build_plugin.sh` | Generate + author + cook + pak + checks; `--install` copies the pak into the main install's `~mods` (game closed!). |
| `tools/build_catalog.py` | Rebuilds `catalog_data.lua` from the ZCRE dump (mesh JSON cached in `ZCRE/out/static_meshes`). Rerun after a patch. |
| `tools/package.py` | The release zip (`dist/ZComDenDesigner-<version>.zip`), checked file by file. |
| `tools/dd.py` | Dev driver for the main install: `restart` (kill, Lutris launch, ZC Sandbox loads the sandbox Den), `con "zcomden ..."`, `lua`, `shot`, `log`. |
| `tools/run-tests.sh` | Offline tests (LuaJIT): store/layout/json, apply over a UE4SS mock, history, pick, catalog, thumbs framing, keys. |

## Build and test

```sh
tools/run-tests.sh                      # offline, ~1 s
tools/build_plugin.sh                   # kit assets -> dist/plugin (~40 s); game must be closed for --install
python3 tools/dd.py restart             # game up in the sandbox campaign's Den
python3 tools/dd.py con "zcomden open"  # then: zcomden do <command> [arg] | select <id> | state | eval <lua> | reload
python3 tools/dd.py shot                # dist/screen.jpg, UI included
python3 tools/package.py
```

`zcomden reload` re-reads every script through `io.open` + `load`: UE4SS serves `require`, `dofile` and `loadfile`
cached copies, so anything else keeps running old code.

## Things learned the hard way

- Load kit assets by their **plugin** names (`/ZComDen/ZComDen/...`). The pak also remaps them to `/Game/ZComDen/...`,
  but loading that name makes a second copy of each class, and the assets' own references (casts, entry classes)
  point at the first.
- Never do a blocking asset load inside a hook on a Blueprint function (a widget click): it deadlocked the game.
  Kit events run one tick later (`later()`), from the game thread's tick.
- Hooks live only while the editor is open, and every panel exists (hidden) for that time: a kit class nothing
  references gets garbage collected with its functions, leaving hooks pointing at nothing.
- `editor.lua` has a local `select()` (the selection), so Lua's `select("#", ...)` is `nargs(...)` there (a test
  guards it).
- Outlines use the Den's own custom-depth post-process (stencil 32 gold, 15 blue); overlay materials don't draw on
  Nanite meshes.
- Alt never reaches the game's input under Proton: no Alt chords.
- Under Proton, ZC Sandbox sees every write to `cmd.txt` as a replaced file and reruns all of it: write one command
  per file (`dd.py send` does).
