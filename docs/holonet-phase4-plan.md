# Phase 4: the in-game HoloNet window

Prepared 2026-10-28, after HoloNet went live at https://zcom.app (ZComShare `main`,
commit `85ef192`). Work happens on the `community` branch, which holds ChatGPT's
Community work (pak 1.1.0-preview.22, bridge 0.1.0-preview.10) on top of the
editor split. API reference: `../ZComShare/docs/api.md`.

Design: mockup canvas https://claude.ai/artifact/Qo83uSVbDmV8eexUDT5zAT, boards
"In-game · Browse" and "In-game · Share a composition" (approved; browse board
"looks good"). Name: **HoloNet**.

## What stays and what gets rebuilt

Keep (it works; the user confirmed fetch, import, thumbnails and placement in-game):

- The native bridge (`native/community/`), WinHTTP transport, redirects off,
  bounded responses, cancellation. (Since 0.9.20 it is one `version.dll`; see
  "Single-DLL bridge" below.)
- The SaveGame mailbox between Blueprint and bridge
  (`runtime_community_mailbox.py`, `BP_DenCommunityWireSave`) and its request
  types: `CATALOG/`, `PREVIEW/`, `DOWNLOAD/`, `COPYURL/`, `COPYCODE/`, `CONNECT`,
  `AUTH`, `DISCONNECT`, `FORGET`, `PUBLISH`.
- Import into the local library (`BeginCommunityImport`, `AppendCommunityPart`,
  `AppendCommunityMaterial`, `CommitCommunityImport` in `runtime_community.py`).
- Remember/forget connection behaviour and the cached-PNG padding fix.

Rebuild:

- The window. `WBP_DenCommunity` is the library-dock template with more rows; it
  becomes a new centred `WBP_DenHoloNet` (below). `runtime_community_widget.py`,
  `runtime_community_ui.py` and `runtime_community_browser.py` are rewritten
  around it; the toolbar entry "Community" becomes "HoloNet".
- The bridge's API layer, to the HoloNet contract (next section).

## The bridge vs the live API

The installed preview.22 can browse HoloNet and publish to it, but **cannot import
new builds**: `dd_document` (`native/community/core.c:512`) requires exact key
sets from the old test format. Each row below is a required change.

| # | Today | HoloNet | Change |
| --- | --- | --- | --- |
| 1 | `share.zcom.app` hard-coded: `connection.c:60,150,155`, `worker.c:63,181,209`, `core.c:43`, `connection-smoke.c` | API at `https://zcom.app/api/v1` | One `DD_SERVICE_HOST` constant. Accept pasted `zcom.app/comp/…` and `share.zcom.app/comp/…` links. |
| 2 | `dd_document`: compatibility has exactly 5 keys with game build `25898267` and mod `1.1.0-preview.19`; author needs `display_name`; dependencies exactly `assets`/`packs`/`unknown_assets`; packs must be empty; every mesh listed in `assets` | compatibility `{game_id, game_version, mod_id, mod_version}`; metadata adds `footprint_cm`, author is `{id}`; dependencies `{packs, unknown_assets, base_game_assets}` | Rewrite the validator for this format. A mesh is valid if it's under `/Game/`, under a listed pack's `/<mount>/`, or listed in `unknown_assets`. Don't pin game or mod versions; refuse only `schema_version` > 1. Keep the size, depth, duplicate-key and integrity checks. |
| 3 | Fetches `/api/v1/compositions` (24 newest) and searches/pages locally, 6 per page (`dd_gallery_select`) | Server paging and search: `?page=&per_page=&q=&sort=newest\|imports&base_game=1`, returns `page, pages, total` | Ask the server for each page; URL-encode `q`. 8 cards per page fits the 4-column grid. |
| 4 | `dd_gallery_row` prints "Reviewed asset" lines | Items carry `creator.display_name`, `base_game_only`, `requirements.packs[{title, version, parts, url, link}]` | Send title, creator, parts, revision, readiness and pack titles as separate wire fields for the card and detail pane. |
| 5 | Begin-upload JSON: title, description, optional code + revision typed by the player | Also takes `changelog` (≤ 500 chars) | Add the "What changed" text. Code and base revision come from the chosen listing, never typed. |
| 6 | Uploaded build has no pack info | Server needs `dependencies.packs[{id, mount, version, title, url}]`, optional `metadata.footprint_cm` | Built by `BuildCommunitySubmission` from the loaded `BP_DenPropPack`s (PackID, Title, Version, plus the new Nexus URL; mount = first segment of the pack's asset paths) and the composition's bounds. |
| 7 | Uploads the 128×128 cached thumbnail (`runtime_thumbnails.py:107`) | Server takes up to 1024×1024; website cards and Discord previews want ~512 | Render a separate 512×512 capture when sharing. Leave the shared 128 target alone. |
| 8 | Profile parsed for `user_id` only | `/game/profile` adds `display_name` | Show "Connected as <name>". |
| 9 | none | `GET /api/v1/my/listings?page=&per_page=` (key auth), `PATCH /api/v1/my/listings/{code}` | New `MYSHARES/<page>` request for the My Shares list and the update picker. Hide/show is optional in-game (the website has it). |
| 10 | Copy URL builds `https://share.zcom.app/comp/…` | `https://zcom.app/comp/…` | Use the service host constant. |

Codes are now 8 Crockford base32 characters. `dd_code` accepts 6–32 ASCII, so
codes need no bridge change. Upper-case the input before showing it.

## Prop pack Nexus links (authoring side)

Agreed with the user: a pack's link is used only if it's an HTTPS Nexus Mods page
for `starwarszerocompany`. Otherwise (including no link), HoloNet links to
`https://www.nexusmods.com/games/starwarszerocompany/mods?title=<Pack Title>`.
The server enforces this; the authoring tools should help authors get it right:

- `pack.json` / `authoring/prop-packs/template.json`: optional `nexus_url`.
- `tools/prop_packs/prop_pack.py`: validate it the same way as the server, with
  a clear message.
- In-editor pack tool (`authoring/prop-packs/Plugins/DenPropPackEditor`): a
  field for it.
- Runtime `BP_DenPropPack` (`unreal/specs/runtime_prop_packs.py`): add `NexusURL`
  next to PackID/Title/Author/Version.
- Docs: `authoring/prop-packs/README.md` and `EDITOR-GUIDE.md`.

## The window (from the mockups)

A centred window about 1640×944 over the Den, under the editor menu bar. It must
also fit 1280×800 (Steam Deck), so the window scales down or the detail pane
narrows there.

- Title bar: HoloNet mark, "HOLONET", subtitle, connection pill ("Connected as
  ChatterChats" / "Not connected"), close.
- Left rail: **Browse**: Compositions, Dens (marked "Soon"). **Yours**: Share a
  build, My Shares (with count), Account. At the bottom, a "Have a code?" box
  with Import (codes or zcom.app links).
- **Browse**: search, Newest / Most imported, "Only what I can use" toggle (base
  game + installed packs), 4-column cards with an "In library" badge, page
  controls. Detail pane: large preview, title, "by X · revision N · when",
  description, readiness ("Ready to import · base game only", or which pack is
  missing), parts, footprint, code. Buttons: **Add to my Compositions** and
  **Add and place now**.
- **Share a build**: 1) pick a saved composition (3-column cards; already-shared
  ones show "SHARED · CODE"). 2) Describe it: title, description. "This share":
  *Update <title> · CODE (becomes revision N+1)* or *Share as a new build*.
  **What changed** appears only when updating. Requirements summary, "Shares the
  saved copy, not unsaved edits. Sharing as <name>.", a big Share button.
  States: not connected (key entry inline), sharing (progress, cancel), shared
  (big code, Copy code, Copy link).
- **My Shares**: your listings (page through them), each with code, revision,
  imports, Public/Hidden; selecting one opens it in Share as an update.
- **Account**: masked key field, Connect / Disconnect, "Remember on this PC" /
  Forget (with the existing plain-storage disclosure), "Get a key at
  zcom.app/account" (opens the browser).
- Also: a **Share** action on local composition cards in the library dock opens
  Share with that composition already picked.

## Milestones

Each one builds, passes tests and can be installed on its own.

1. **Bridge contract.** Items 1–4, 8 and 10. Rewrite `dd_document` and its
   tests; Wine smoke tests against `npm run dev` in ZComShare with seeded builds,
   then against zcom.app.
2. **Publishing data.** Items 5–7: changelog, pack declarations, footprint,
   512 px share render.
3. **Window skeleton.** `WBP_DenHoloNet` with title bar, rail, empty areas and
   toolbar entry; remove `WBP_DenCommunity`; keep every existing command working.
4. **Browse.** Server paging/search, cards, detail pane, Add / Add and place.
5. **Share and My Shares.** Update flow with "What changed", progress and result
   states (item 9).
6. **Account.**
7. **Prop pack Nexus links** (authoring tools and runtime).
8. **Package and install** pak + bridge, then the in-game checklist below.

## Verifying

- Python: the existing `tests/python/community_*` suites, updated for the new
  formats; new fixtures from real HoloNet documents (publish one through
  ZComShare's dev server and save it).
- Kit: `tests/unreal/test_community_native.py` through
  `tools/build/test_native.sh`; author with `build_gf.sh --author-only` first.
- Native: the Wine smoke builds in `native/community/` (`smoke-build.sh`,
  `connection-smoke-build.sh`) and the end-to-end suite
  `native/community/e2e/run.sh`.
- In game (the user): connect with a key; browse and page; import a base-game
  build and a pack build (with and without the pack installed); share a new
  build; update it with "What changed" and see the changelog on zcom.app; check
  the Discord preview; disconnect, remember and forget; close the window during
  an upload.

## Decisions (2026-10-29)

- Keep **Add and place now** next to **Add to my Compositions**.
- Versions: Den Designer **0.9.20** and bridge **0.9.20**; 1.0.0 is the final
  release. (Den Designer goes down from 1.1.0-preview.22, so Nexus and the
  installer must not treat 0.9.20 as older.) The bridge version is set
  (`DD_VERSION` in `core.h`); the pak version changes at milestone 8.
- No Steam Deck for testing: check 1280×800 by resizing the game window.
- The bridge is a single `version.dll` (no `den-community.exe`), with every
  bridge thread inside a structured exception guard. The key now lives in game
  memory; the owner accepted that (the key limits who can upload and allows
  moderation; it is not a high-value secret).

## Single-DLL bridge (0.9.20)

`den-community.exe` is gone: browse/import requests run on a worker thread and
the connection (key, My Shares, sharing) on a task thread inside `version.dll`,
started from a mailbox thread (`proxy.c`). The game's own threads only ever enter
the version forwarders.

- **Guards**: each thread body is wrapped in `__try/__except` (MSVC-target clang;
  `__C_specific_handler` from ntdll, no C runtime). A caught fault logs, wipes the
  key, answers the request in flight and every later one with "HoloNet stopped
  after an internal error. Restart the game to use HoloNet.", and leaves the game
  running. Reply writes use one lock released by `__finally`, so a fault can't
  leave it held. No process-wide exception filters are installed.
- **Cancel and timeout** no longer kill a process: the request's generation is
  bumped and the dropped thread can neither reply nor change state. It stops at
  its next network step (it reads only the bytes that have arrived) and a share
  dropped mid-upload deletes its unfinished upload. Handles are never closed from
  another thread, since the game's own HTTP may use WinHTTP.
- **Wine/Proton fix**: Wine's WinHTTP ignores `WinHttpSetTimeouts` for the wait
  on response headers and waited as long as the server stalled. Both transports
  now also set `WINHTTP_OPTION_RECEIVE_RESPONSE_TIMEOUT` (6 s).
- Threads get an explicit 2 MB stack (the JSON token table is 256 KB on the stack).
- Imports: kernel32, user32 (clipboard), winhttp, bcrypt and ntdll, all system DLLs;
  the game executable already imports WINHTTP.dll and USER32.dll.
- Upload replies are read with the bounded JSON parser (`dd_json_word`), not a text
  search, so their formatting doesn't matter.
- Installer: one file; upgrading removes 0.9.19's `den-community.exe` only when it
  matches the previous installation record.
- Tests: `native/community/e2e/run.sh` (wine, python3, cc) builds a test DLL with
  `-DDD_FAULT_TEST` crash points pointed at a local fake HoloNet, loads it in a
  stand-in game process, and checks browse, search, preview, import, copy, connect
  (wrong key, remembered, session only, relaunch reconnect), My Shares, share new
  and update (exact request bodies), disconnect/forget, offline, the 25-second
  deadline, cancel and replace (no stale replies), connect timeout and recovery,
  cancelled share cleanup, a crash in each of the four threads, 60 rapid requests,
  damaged mailbox files and damaged server replies (no caught faults allowed).

## Progress

All eight milestones are implemented in source (2026-10-29). Nothing here has
been built with the kit, packaged or run in the game yet.

| Milestone | State |
| --- | --- |
| 1. Bridge contract | Done. Bridge items 1–5, 7–10 |
| 2. Publishing data | Done. Catalog keeps each pack's mount, title, version and Nexus link (`DeclarePacks`, `DescribeSources`); the studio writes `Composition_<hash>_512.png` beside each composition card and the thumbnail queue remembers its footprint; `BuildCommunitySubmission` sends `dependencies.packs` and `metadata.footprint_cm` |
| 3–6. Window | Done. `WBP_DenHolonet` (`unreal/specs/runtime_holonet_widget.py`) replaces `WBP_DenCommunity`; host logic in `runtime_community_*.py` |
| 7. Prop pack Nexus links | Done. `pack.json`/template, `prop_pack.py`, in-editor tool field, `BP_DenPropPack.NexusURL`, docs |
| 8. Package and install | Versions set to 0.9.20 and docs updated. The kit build, packaging and install are yours to run (they need the kit and the game) |

Deviations from the mockup, to stay within engine calls the project already uses
(each can be revisited):

- Text boxes are single-line, so descriptions and What changed have no line breaks
  when typed in game (the website keeps them).
- Not connected on Share a build points to Account instead of taking the key inline.
- "Only what I can use" filters each page in the game (the server can only filter to
  base game), so a page can show fewer than eight cards; the page caption says how many
  are hidden.
- Local composition cards have no "SHARED · CODE" badge; instead the share whose title
  matches the composition's name is picked as the update target.
- Cards cached before 0.9.20 have no 512 px render or footprint until they render again;
  sharing them uses the 128 px card and leaves the footprint out.

### How it was checked here

- Python: 112 tests, including `tests/python/holonet_spec_test.py`, which runs the
  generated window graphs (card and pack rows from the real fixtures, readiness,
  filtering, the detail pane, My Shares, the PUBLISH text, the update choice, the
  share result, pack declarations and footprint) through `tools/build/simulate_specs.py`.
  It also checks the generated specs are up to date and lint clean.
- `tools/build/lint_specs.py` on all generated specs: links, functions, variables,
  duplicate ids, exec wiring, functions that never run, and engine calls or pins not
  used anywhere before (none are new).
- Bridge: connection smoke test and the real worker under Wine (MinGW build) against
  a local server serving the fixtures. For the single DLL: the suite above, 77 of 77
  checks, built from these sources with the Wine 9 SDK and `build.sh`'s flags (not the
  Proton SDK); a long run of the stress, crash and fuzz checks at 10× (4,000 damaged
  mailbox files, 600 damaged replies).
- Not run: the kit (`build_gf.sh --author-only`, `tools/build/test_native.sh`,
  `tests/unreal/test_community_native.py`, updated for the new window but not run), the
  official Wine-SDK bridge build, the proxy and lifecycle smoke tests, ZComShare's
  `npm run dev`, live zcom.app.

API formats, checked against ZComShare `docs/api.md` and `src/` (f3187cb):

- `/api/v1/compositions`: 1-based `page`, `pages`, `total`, full listing items
  (also `tests/fixtures/sharing/holonet-gallery-page.json`, covered by a bridge test).
- `/api/v1/my/listings`: listing items plus `visibility` (`public`/`hidden`).
- `/api/v1/game/profile`: `display_name`.
- Begin upload takes `changelog`; the build file's `dependencies.packs[{id, mount,
  version, title, url}]` (an empty `url` is allowed) and `metadata.footprint_cm`.

Local development build: `DD_SERVICE_HOST=localhost DD_SERVICE_PORT=3000
DD_SERVICE_INSECURE=1 bash native/community/build.sh` (recorded in
`build.json` as a development build; never ship it).

## In-game checklist

Build and install first: `build_gf.sh --author-only`, then `tools/build/test_native.sh`;
`bash native/community/build.sh` and `bash native/community/e2e/run.sh`; package with
`tools/build/package_community_bundle.py`. The bridge is now only `version.dll`; delete
an old `den-community.exe` from `Binaries/Win64` if you install by hand.

1. Open the editor, choose **HoloNet** on the menu bar. The window is centred under the
   menu bar; the title bar says Not connected. At 1280×800 (resize the game window) it
   still fits.
2. **Account**: paste a key, Connect. Title bar: Connected as <your name>. Try Remember on,
   restart the game, reopen HoloNet: still connected. Disconnect, then Forget.
3. **Browse**: cards load (8 per page); Next/Previous; search for a title; Most imported
   changes the order. A build you imported before shows IN LIBRARY.
4. Select a base-game build: preview renders, readiness "Ready to import · base game only",
   parts, footprint, code. **Add to my Compositions**: it appears in Compositions.
5. Select a build that uses a prop pack you **don't** have: "Needs the … prop pack";
   **Get the prop pack on Nexus** opens the right page. Turn on **Only what I can use**: it
   disappears from the grid. Install the pack, restart: it is ready and shows "uses …".
6. **Add and place now** on a build: Compositions opens and the placement preview follows
   the pointer; click to place.
7. **Have a code?**: paste a code, and separately a zcom.app/comp/… link: both import.
8. **Share a build**: pick a new composition (rendered after installing 0.9.20). Title is
   filled in; "Share as a new build" is chosen. Share: code shown; Copy code and Copy link
   work. On zcom.app the build has the prop packs (with Nexus links) and a sharp preview.
9. Change that composition, save it, pick it again: "Update <title> · CODE (becomes revision
   2)" is chosen and What changed appears. Share update. On zcom.app: revision 2 and its
   changelog. Check the Discord preview of the link.
10. **My Shares**: both shares listed with revision and imports; picking one opens Share as
    an update. On the Compositions panel, select a card and choose **Share**.
11. Close the window during a share: it stops; reopening shows no half-finished state.
    Unplug the network and browse: an error within a few seconds, and the game keeps running.
    `native.log` (next to the mailbox) says "HoloNet bridge 0.9.20 loaded (one DLL ...)".
12. Prop pack authors: add a Nexus page in the pack tool; an invalid one is refused with the
    explanation.

## Bridge wire for the window (milestones 3–5)

All values are UTF-8 in the bridge. The response SaveGame's `Wire` is ANSI when
ASCII and UTF-16 otherwise; UE reads both. Text fields never contain a tab or
line break.

- `CATALOG/<page>` (0-based), wire `<newest|imports>\t<all|base>\t<search>`.
  Reply: `gallery\t<page>\t<pages>\t<total>`, then per listing
  `card\t<code>\t<title>\t<creator>\t<parts>\t<revision>\t<imports>\t<base_game_only 0|1>\t<unknown asset count>\t<updated>\t<footprint>\t<description>`
  (footprint is display text such as `2.4 × 0.8 × 2.1 m`, or empty)
  and one `pack\t<code>\t<id>\t<title>\t<version>\t<parts>\t<nexus url>` per
  prop pack, then `end`. Eight per page. The description is the first 1000
  characters with `\n` for a line break and `\\` for a backslash. A wire with
  no tab is the preview.22 panel's search: six per page, old `listing` rows.
- `MYSHARES/<page>`, wire `request`. Reply: `shares\t<page>\t<pages>\t<total>`,
  then `share\t<code>\t<title>\t<latest revision>\t<imports>\t<public|hidden>\t<updated>`,
  then `end`. Needs a connection (else `error\tNot connected…`).
- `PUBLISH`: first line `Composition_<hash>.png` or `Composition_<hash>_512.png`
  (the share render, same thumbs folder), then `title\t…`, `description\t…`,
  optional `changelog\t…` and `update\t<code>\t<revision>` lines (values use
  `\n` and `\\`), then a line `payload` and the JSON. The old four-line form
  still works.
- Imports (`<code>`, `PREVIEW/`, `DOWNLOAD/`) keep their format; `report` is now
  a readable requirements line ("Base game only." / "Uses prop packs: …").
- Status messages keep the prefixes the game matches: `Published: https://zcom.app/comp/<code>`,
  `Connected as <name>` (or `Connected to HoloNet`), `Not connected`,
  `Key invalid`, `Remembered connection.`
