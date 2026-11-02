# Editor: bounds snapping while placing

Den Designer (this repo, branch `community`). **Bounds snapping with alignment guides** works
when you move a placed prop (Phase 2 of the UI rework): flush, stack and align against
neighbours, centre-to-edge kinds, per-axis neighbours in a shared frame, a screen-scaled range
(about 10 px), guides drawn by `BP_DenSnapGuides`, Alt = free. Code: `unreal/specs/runtime_snap.py`
(`BeginSnapDrag` only runs for a selection drag, `DragMode == 1`), the math in `BP_DenSnapMath`
(`runtime_snap_math.py`), fixtures `tests/fixtures/snap_cases.json`. True vertex snapping is ruled
out (vanilla meshes have no CPU access in the cooked game).

Placing from the **Catalog** (`runtime_placement.py`: `UpdatePlacementRay` traces the cursor,
grid-snaps X/Y and sits the prop's bottom on the hit) and from **Compositions**
(`runtime_composition_preview.py`: `SetCompositionPreviewOrigin`) doesn't snap to neighbours yet.
It was deferred until moving felt right, and it does now.

## Goal

The placement ghost snaps the same way a moved prop does, with the same guides and the same
Alt = free, for a single Catalog prop and for a whole composition (the composition's bounds act
as one box). The mockup board for placing (DeckPlacing on
https://claude.ai/artifact/Qo83uSVbDmV8eexUDT5zAT) shows the label "Flush · aligned to Bar counter"
next to the ghost; the existing snap badge already does this for moves.

## Before building

Read `runtime_snap.py` and the two placement specs, then ask me:
- Does placement snap by default, following the same Snap toggle in the menu bar?
- With the grid on and a neighbour in range, which wins (moves today: the neighbour)?
- Stacking on top of a prop vs the floor trace: the ray already lands on top surfaces; should
  stack snapping still apply?

## Order of work

1. Catalog placement snapping, reusing the move-snap code (factor out shared parts rather than
   copying them). Fixture cases for a ghost without a selection. Build, install, stop.
2. Composition placement snapping. Build, install, stop.

## How to test in game

Use the `zcom` MCP (`mcp__zcom__*`). Ask me which save to load. Never press Save in the editor;
leave with Done → Discard. Alt-held moves need XTest from Python (the MCP `input` tool can't hold
a modifier during a click or drag): move with `input move`, then send the key and button.

## Rules

- No new behaviour beyond the snapping that moves already have. Ask if something conflicts with
  how the runtime works rather than inventing a workaround.
- Placing still folds the rail and a drop or Esc restores it (0.9.25); Shift-click still places
  more.
- Match the surrounding spec style (compact graph helper calls, the same naming). Keep existing
  widget and Native_Event names.
- Lint (`python3 tools/build/lint_specs.py --show-new`), Python tests
  (`python3 -m unittest discover -s tests/python -p '*_test.py'`) and native tests
  (`bash tools/build/test_native.sh --existing`) pass before any install; bump the patch version and add a CHANGELOG entry for each
  preview installed.
- Don't commit or push unless I ask. Ask before committing anything you didn't write.
- At each stop, tell me exactly what to test in game, and say plainly what you could not verify.
