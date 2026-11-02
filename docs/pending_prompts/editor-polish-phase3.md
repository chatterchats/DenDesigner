# Editor polish: drag-to-scrub fields, selection brackets, optional blur

Den Designer (this repo, branch `community`). The editor UI rework follows mockup board **D ·
Command Deck look, Workbench layout** on the canvas
https://claude.ai/artifact/58bWeSsyRPSB5vwT8mvJ77. Phase 1 (look and layout) and Phase 2 (bounds
snapping while moving props) are done and in game. This is **Phase 3**, the three items left over:

1. **Drag-to-scrub number fields.** In the Selected Prop inspector, dragging sideways on a field's
   label (X/Y/Z position, P/Y/R rotation, Scale) changes the value; typing still works.
2. **Corner-bracket selection.** The selected prop is marked with corner brackets as on board D,
   in addition to or instead of today's outline (custom depth stencil). Ask me which.
3. **Optional background blur** behind the editor's panels, as a setting, off by default
   (UMG BackgroundBlur). Check the cost on my machine before making it an option.

## Before building

Read board D and the current inspector (`ui_templates.py` `transform`, specs
`runtime_transform.py`, `runtime_selection.py`). Questions to ask me first:
- Scrub speed and steps: centimetres or the grid step per pixel? Shift = fine, as with the
  wheel? Does one scrub make one undo step (it should, like a drag)?
- Brackets: replace the outline or add to it? Screen-space (a widget around the projected
  bounds) or world-space (lines at the box corners)?
- Blur strength, and which panels get it (rail window, inspector, menu bar, status bar).

## Order of work

Each item is its own preview: build, install, stop for my in-game test.

1. Scrub fields (one undo step per scrub; the edit goes through the normal transaction path).
2. Selection brackets.
3. Blur setting (Settings, preferences key, off by default).

## How to test in game

Use the `zcom` MCP (`mcp__zcom__*`). Ask me which save to load. Never press Save in the editor;
leave with Done → Discard. The MCP can't hold a modifier during a click: for a Shift-drag, move
with `input move`, then send the key and button through XTest from Python.

## Rules

- No new behaviour beyond the three items. Ask if board D conflicts with how the game's runtime
  works rather than inventing a workaround.
- Match the surrounding spec style (compact graph helper calls, the same naming). Keep existing
  widget and Native_Event names where logic depends on them.
- World-click blocking (`EditorPointerBlocked`) must still cover every panel; a scrub must never
  select or move something behind the inspector.
- Lint (`python3 tools/build/lint_specs.py --show-new`), Python tests and native tests
  (`bash tools/build/test_native.sh --existing`) pass before any install; bump the patch version
  and add a CHANGELOG entry for each preview installed.
- Don't commit or push unless I ask. Ask before committing anything you didn't write.
- At each stop, tell me exactly what to test in game, and say plainly what you could not verify.
