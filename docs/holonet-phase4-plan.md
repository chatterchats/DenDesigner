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

- The native bridge: `version.dll` proxy plus worker process (`native/community/`),
  WinHTTP transport, redirects off, bounded responses, cancellation.
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
  `connection-smoke-build.sh`, `lifecycle-smoke-build.sh`).
- In game (the user): connect with a key; browse and page; import a base-game
  build and a pack build (with and without the pack installed); share a new
  build; update it with "What changed" and see the changelog on zcom.app; check
  the Discord preview; disconnect, remember and forget; close the window during
  an upload.

## To ask the user when starting

- Keep "Add and place now" next to "Add to my Compositions"? (It's on the
  approved board.)
- Version for the HoloNet release: Den Designer 1.2.0-preview.1 and bridge
  0.2.0-preview.1?
- Is a Steam Deck available for testing the 1280×800 layout?
