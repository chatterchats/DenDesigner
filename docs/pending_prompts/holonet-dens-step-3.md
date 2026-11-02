# HoloNet Dens, step 3: in game

Den Designer (this repo, branch `community`) shares compositions through HoloNet. This brief makes
**Dens · Soon** real in the game: Browse Dens, Share, Import and Apply. It is step 3 of
`docs/holonet-dens-plan.md`. Read the plan first: its decisions are settled, so don't reopen them.

Steps 1 and 2 are done. The backend is **live on zcom.app**, including migration 0006 (the two-revision
rule, the caps of 10 Dens and 50 compositions, deleting shares), and there are no Dens on it yet.

Read before designing:
- `../ZComShare/docs/api.md`: the Den reads, `/codes/{code}`, `/den-uploads` and "The Den file".
  `../ZComShare/src/sharing/den.js` is the exact validator. **Where the plan and the API differ, the
  API is right.**
- `docs/holonet-phase4-plan.md`: the bridge, the mailbox and its wire format.
- `docs/portable-sharing.md`, `unreal/specs/runtime_presets.py` (`ShareCode`),
  `unreal/specs/runtime_refind.py` (the rule for each edit's scenery check),
  `unreal/specs/runtime_holonet_widget.py` (`BrowseDenArea` holds the "coming soon" text),
  `unreal/specs/runtime_community*.py`, `native/community/`.
- Mockups: boards **DenBrowse, DenApply, DenShare** on the canvas
  https://claude.ai/artifact/Qo83uSVbDmV8eexUDT5zAT. They predate the 2026-10-31 revisions, so they
  still show Storeroom lines, hidden counts and `<title> <code>` names. **The plan wins on wording
  and behaviour; the boards set the layout.** Only the cantina picture on them is real.

## What the live API expects

- Den uploads go payload → images → finalize. **There is no thumbnail step**, whatever the plan's
  Pictures section says: the server uses the cover picture as the thumbnail.
  - Begin needs an `Idempotency-Key`. An account can have **10 Dens**, hidden ones and new ones being
    uploaded included. An 11th returns 409 `DEN_LIMIT_REACHED`, and a 51st composition
    `COMPOSITION_LIMIT_REACHED`, each with a message to show; updating an existing share is always
    allowed. `service_failure` in `connection.c` only knows listed codes, so add both, or the game says
    "HoloNet refused this step".
  - `PUT /image/{area}`: PNG, up to 1 MiB and 1024 px, one per area. Files are write-once.
  - `POST finalize` with `{"cover":"<area>"}`.
- The server builds `metadata.areas` and `media`, and assigns new `prop-N` keys. Don't send them.
- It refuses, and the game must never send or must explain:
  - a Den with no entries (**the plan doesn't cover this in game; ask me what Share should say**);
  - any `Kind` other than 0 or 2;
  - a placed entry that is hidden, has a fingerprint or lacks a `Has*` flag;
  - a native entry without a fingerprint, with a PIE path or with a duplicate key;
  - scale outside (0, 100], or more than 64 materials;
  - more than 4,096 entries or 4 MiB.
- If a saved layout holds a native entry with no fingerprint, or anything else the server would
  refuse, ask me how Share should report it. Never rewrite it.
- Under sustained load, Cloudflare can refuse a request with Error 1102, an HTML page rather than JSON
  (see `../ZComShare/docs/capacity.md`). Occasional large Dens are fine, tested up to the largest file. Wait
  a few seconds and retry a refused upload step before showing an error; every step is safe to repeat.
- Other errors the game must show plainly: the Den limit, beta approval required, revision conflict,
  and a picture refused.
- Only a listing's newest two revisions have files. Older pinned URLs return 404, so a download that
  loses that race needs a plain error, not a hang.
- A share can be deleted on zcom.app. Its code then returns 404 for good, and it leaves My Shares. An
  imported preset stays on the importer's PC either way.
- `GET /my/listings` also returns `deleted_codes`, your 200 most recently deleted shares. Share uses it to
  offer your own deleted Den again; see the plan's Share section. If it's missing, tell me to deploy.
- `GET /codes/{code}` returns the kind for **Have a code?**. `GET /my/listings` rows carry their kind.

## Check these first

Sizes and pictures haven't been tried in the game, and either could change the design. Check them
before building the screens, and **stop and ask me if anything conflicts with the plan**.

1. **Size.** The mailbox carries at most 48 KiB per message (`DD_WIRE_MAX`, `native/community/core.h`).
   That fits a composition (128 parts); a Den is up to 4,096 entries and 4 MiB. Sharing, importing and
   the per-edit check all need a way to move that much between Blueprint and the bridge, for example
   numbered pages like `CATALOG/<page>`. Size it on a real layout and on the 4,096 limit, without a
   Blueprint hitch or runaway-loop error. `dd_document` also accepts only compositions
   (`core.c:754`), and the upload paths are hard-coded (`connection.c:141,166`).
2. **Pictures.** The plan says: hide the UI, take a screenshot, show the UI. The project has no
   screenshot call today; it only uses `SceneCapture` and `ExportRenderTarget` (RTF_RGBA8) in
   `runtime_thumbnails.py`, and the bridge reads that PNG from disk. Find out whether a shipping,
   pak-only build can take a real screenshot and get it to 1024×576. If only a scene capture works,
   compare it with the real view (lighting, post-processing, ReShade) and show me both before
   choosing. Check that a real picture stays under 1 MiB.

## Also part of this step

- The bridge: `den` catalog, download and upload with images, code lookup, kind on My Shares.
  Bump `DD_VERSION` and `VERSION` in `tools/build/package_community.py` when it changes.
- `docs/portable-sharing.md` and `tools/sharing/contract.py` (with `community.py`, `sharing_test.py`
  and `den-v1.json`) still require a whole-room `native_fingerprint` for Dens and allow stored props
  and zero entries. Update them to the plan's per-edit check.
- `Kind=1` is dropped when sharing. On Apply, the importer's own `Kind=1` entries stay in the working
  layout with their keys unchanged.
- Never mention the Storeroom or hidden counts in any Den screen.
- Update the plan and the docs for what you change.

## Camera spots (with me)

Before testing uploads, I go to each of the five areas with ZC Sandbox running and you read off the
camera transform; the spots go in the runtime spec. ZC Sandbox needs the UE4SS loader, which was
parked for performance testing (`dist/verification/perf-1.0.0/parked/` still holds `dwmapi.dll`).
Ask me before restoring it with `dist/verification/perf-1.0.0/restore.py`, and before we start.

## How to test in game

Use the `zcom` MCP (`mcp__zcom__*`). Ask me which save to load. Never Save in the editor; leave with
Done → Discard. Importing a Den changes layouts: never import over my real layouts; make a throwaway
layout or ask. Shares are public: tell me before publishing, and remind me to delete test shares
afterwards. I do that in My Shares on zcom.app; the game has no delete. Each test Den uses one of my 10
places until it's deleted.

Test at least: a Den with hidden scenery and with moved scenery; missing packs; an edit that doesn't
match this game (refused, nothing partly imported); a title already taken; the same code imported
twice; a preset from someone else's Den (not offered on Share); updating my own Den; leaving areas
out and changing the cover; a preset of my own deleted Den (`DELETED · CODE`, shared as new, takes the new
code); someone else's preset after they delete it (still not offered); **Use my camera**; Apply then Done → Discard (the room goes back); the
Den on zcom.app; and 1280×800.

## Rules

- No new behaviour beyond the plan and the mockups. Ask if something conflicts with how the game's
  runtime works rather than inventing a workaround.
- Saved identities stay stable; never rewrite existing layout keys.
- Match the surrounding spec style (compact graph helper calls, the same naming). Keep existing
  widget and Native_Event names where logic depends on them. World-click blocking
  (`EditorPointerBlocked` in runtime_gizmo_controller) must cover any new window.
- Before any install, these must pass: lint (`tools/build/lint_specs.py`), Python
  (`python3 -m unittest discover -s tests/python -p '*_test.py'`), native
  (`tools/build/test_native.sh`), and, if the bridge changed, `native/community/e2e/run.sh`.
- Bump the patch version and add a CHANGELOG entry for each preview installed. Close the game before
  installing.
- If the backend needs a change, tell me why first. I deploy the website and run production
  migrations myself.
- Don't commit or push unless I ask. Ask before committing anything you didn't write.
- Stop when the step is built, tested and installed. Tell me exactly what to test, and say plainly
  what you could not verify.
