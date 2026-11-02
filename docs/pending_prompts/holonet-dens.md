# HoloNet: share whole Dens

Den Designer (this repo, branch `community`) shares **compositions** (groups of props) through
HoloNet. The rail already shows **Dens · Soon** (disabled; command `community_browse_dens` opens
`OpenHolonetArea` with `browse_dens`). This brief is about making it real: sharing and importing
a whole Den layout.

What exists:
- Backend (`../ZComShare`): listings already allow `kind IN ('comp','den','char')`
  (migration 0004); zcom.app has a `/dens` "coming soon" page. Only `comp` is used today.
- Portable format: `docs/portable-sharing.md` and `tools/sharing` (`python3 -m tools.sharing
  tests/fixtures/sharing/den-v1.json`). `content_type` may be `den`: native overrides, placed
  props, stored props and hidden native scenery, keyed by identity fingerprints.
- In game: Layouts (the Home layout and per-campaign layouts, with backups) and the HoloNet
  window's Browse, Share a build, My Shares and Have a code? (see `docs/holonet-phase4-plan.md`).

## Open questions to settle with me first

A Den edits the base game's own scenery (hidden or moved native props), not just added props,
so importing one is not like importing a composition. Decide with me before designing:
- Where an imported Den goes: replace my current layout (with a backup), become a new saved
  layout in Layouts, or only preview until I apply it.
- Whether a Den share includes stored and hidden props, and how missing prop packs and a
  different game build are reported.
- Which Den gets shared (current layout, a saved layout, Home vs campaign).
- Preview images for Dens (the in-game compositions use rendered thumbnails; a whole room may
  need a screenshot instead).

## Order of work

0. Ask the questions above; write the answers into a short plan in `docs/`.
1. Mock up the in-game screens (Dens browse, detail, share, import confirmation) and the
   website listing on the HoloNet canvas https://claude.ai/artifact/Qo83uSVbDmV8eexUDT5zAT,
   matching the existing boards (DeckHolonet, WebListing). Stop for my approval.
2. Backend: whatever the plan needs for `kind='den'` (upload, listing, revisions, website
   pages), with tests. Stop: I deploy.
3. In game: Browse Dens, share, import, in the approved design. Build, install, stop.
4. Polish from my in-game feedback.

## How to test in game

Use the `zcom` MCP (`mcp__zcom__*`). Ask me which save to load (Continue works fine). Saving in the editor is fine; leave
with Done → Discard. Importing a Den changes layouts; make a throwaway layout or ask. Shares are public: offer to delete test shares afterwards.

## Rules

- No new behaviour beyond the approved plan and mockups. Ask if something in a mockup conflicts
  with how the game's runtime works rather than inventing a workaround.
- Saved identities stay stable; never rewrite existing layout keys.
- Match the surrounding spec style (compact graph helper calls, the same naming). Keep existing
  widget and Native_Event names where logic depends on them. World-click blocking
  (`EditorPointerBlocked` in runtime_gizmo_controller) must cover any new window.
- Lint, Python tests and native tests pass before any install; bump the patch version and add a
  CHANGELOG entry for each preview installed.
- I deploy the website and run production migrations myself.
- Don't commit or push unless I ask. Ask before committing anything you didn't write.
- At each stop, tell me exactly what to test, and say plainly what you could not verify.
