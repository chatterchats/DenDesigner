# HoloNet Dens: sharing whole Den layouts

Prepared 2026-10-30 on the `community` branch. Brief: `docs/pending_prompts/holonet-dens.md`.
Builds on `docs/holonet-phase4-plan.md` (compositions) and `docs/portable-sharing.md`.

## Decisions (2026-10-30, revised 2026-10-31)

| Question | Decision |
| --- | --- |
| Where an import goes | A **named preset** in Layouts, carrying its share code (presets already store `ShareCode`). The room doesn't change. **Apply now** loads it into the editor as unsaved work: Save keeps it, Done → Discard reverts. |
| What a share contains | **The room only**: placed props (`Kind=0`) and native scenery edits (`Kind=2`), **including hidden native scenery**. The sharer's stored placed props (`Kind=1`) are left out. |
| Storeroom | **Not mentioned anywhere** in Den sharing (in game or on the website): no hidden counts, no "Your Storeroom stays…" lines. The Storeroom may be replaced by straight deletion plus undo, so nothing here depends on it. Underneath, Apply still leaves the importer's own `Kind=1` entries in the working layout with their existing keys. Hidden scenery counts as a scenery edit. |
| Import name | As for compositions: the preset is named **just the Den's title**, and the code is stored as its `ShareCode`. Only if the title is already taken does it fall back to `<title> <code>`. |
| Re-sharing | **Not allowed.** A preset imported from someone else's Den isn't offered on Share. The author can still update their own Den, or share it again as new after deleting it (see Share, step 1). |
| Compatibility | Missing packs **block** the import and are listed with Nexus links, as for compositions. Game build is not pinned. Each native edit is checked against the importer's scenery (original mesh + original position); if any edit doesn't match, the import is refused and those edits are listed. No partial imports. |
| What can be shared | The **current saved layout** (labelled Home or Campaign) or a **saved preset**, saved copy only. |
| Pictures | Up to **five**, one per area: Hawk's office, Operator pit, Cantina, Command deck, Hangar (our own labels; the game doesn't name them). Each starts as an automatic shot from a fixed spot; the sharer can **leave an area out** or **Use my camera** for it: the current camera position, UI hidden, screenshot, UI shown again. The sharer marks one as the **cover**, defaulting to the first included area. |
| Keeping and limits (2026-11-01) | A listing keeps files for its **newest two revisions** only, Dens and compositions alike; older changelog notes stay. **10 Dens and 50 compositions per account** are hard caps (hidden ones and new uploads count; updates are always allowed), with no byte limit. See `../ZComShare/docs/capacity.md`. There is no rollback button. Owners can **delete a share** in My Shares on zcom.app. |
| Pictures vs the room | Pictures come from the live room, so Share needs the chosen Den **in the room with nothing unsaved**. Picking a preset that isn't loaded offers **Load into the room** (the same as Apply). Afterwards, Done → Discard goes back. |

## What a Den share is

A `zcom-share` document with `content_type: "den"`, in the same HoloNet shape the bridge already
uses for compositions (phase 4, row 2): compatibility `{game_id, game_version, mod_id,
mod_version}` (informational, not pinned), author `{id}`, dependencies `{packs, unknown_assets,
base_game_assets}`. `schema_version` > 1 is refused.

- `payload.entries`: `Kind` 0 or 2 only; `Kind=1` is dropped when sharing and rejected by the server.
- Native entries keep their cooked world path `Key`, `HasFingerprint: true`, `FingerprintMesh` and
  `FingerprintPosition`; `Hidden` is allowed with or without transform overrides. PIE paths are rejected.
- Placed keys are reassigned to payload-local IDs on export; on import they get fresh local IDs, so
  they never collide with the importer's stored props. Existing layout keys are never rewritten.
- Pack requirements come from placed meshes and **every non-empty material slot**, including
  materials set on native scenery.
- Limits: 4,096 entries (portable bound); 4 MiB document.
- `metadata.areas`: the included areas in order, with the cover marked (see Pictures).
- No whole-room `native_fingerprint` and no exact build match. `docs/portable-sharing.md` is
  updated to say Dens use the per-edit check.

## Import (in game)

1. Browse Dens (or **Have a code?** with a Den code or `zcom.app/den/…` link) → detail pane.
2. Check: required packs installed at a usable version; each native edit's original mesh is
   present at its original position (the existing `runtime_refind.py` rule: by path, else the unique
   mesh at that position within 2 cm per axis). The Den must be loaded with its scenery streamed in.
3. Result: **Ready to import** (N props · M scenery edits) or **Can't import**, listing
   missing packs and/or the scenery edits that don't match this game.
4. **Add to my Layouts** saves a preset named `<title>` with the code as its `ShareCode`
   (`<title> <code>` only when the title is taken). **Add and apply now** also loads it into the
   room. An existing preset with the same code is reported as "Already in your Layouts" (as
   compositions do with "In library").
5. Nothing is saved to Home or a campaign layout until you press Save.

## Share (in game)

1. **Pick a Den**: "Current layout · Home|Campaign" and each saved preset. Already-shared ones show
   "SHARED · CODE". If the pick isn't what's in the room, or the room has unsaved edits, show
   **Load into the room** / "Save or discard your changes first".
   **No re-sharing:** a preset is offered when it has no `ShareCode` (shared as a new Den) or
   when its code is one of the signed-in captain's own listings in My Shares (offered as an
   update). A preset whose code isn't one of theirs was imported from someone else and isn't
   offered. Ownership comes from My Shares, not from how the preset got its code, so an author who
   imports their own Den (another PC, a reinstall) can still update it.
   **After deleting your own Den:** a preset whose code is in the `deleted_codes` of `GET /my/listings`
   shows `DELETED · CODE` and is offered as a new Den only, with no update option and no What changed:
   "You deleted the earlier share of this Den, so this gets a new code." The title starts from the preset's
   name and the description empty. Sharing it replaces the preset's `ShareCode` with the new code; the old
   code stays dead. It takes one of the 10 places. Someone else's deleted Den and moderator removals aren't
   in that list, so they stay not offered. Known gap: a Den applied
   and then saved over Home or a campaign layout has no code, so it could be shared as new. We
   accept that.
   **Nothing to share:** if the pick has no entries left once `Kind=1` is dropped, Share is disabled and shows
   "This layout has no changes to share yet."
2. **Pictures**: five area cards with the automatic shot, each with Include toggle, **Use my camera**,
   **Retake automatic** and a Cover mark. At least one area must be included.
3. **Describe it**: title, description; *Update <title> · CODE* vs *Share as a new Den*; **What
   changed** when updating. Summary: props, scenery edits, required packs.
4. Share → progress → shared (code, Copy code, Copy link). Same states as compositions.

My Shares lists Den listings next to compositions (a kind label on each row); picking one opens
Share as an update.

## Pictures

- 1024×576 PNG (the server's 1 MP / 1024 px limit), scaled from a screenshot of the game view.
- One capture path for both kinds: hide the editor UI (and gizmo, selection and preview actors),
  take the screenshot, show everything again. **Use my camera** takes it from wherever the camera
  is now. Automatic shots move the camera to the area's fixed spot first and put it back afterwards.
- The fixed spots are stored in the runtime spec.
- The server uses the cover as the revision's thumbnail (no separate upload), so cards, the website
  card and the Discord preview work unchanged.

## Backend (`../ZComShare`)

- Migration `0005_den_images.sql`: `revision_images (revision_id, area, position, bytes, sha256,
  width, height)`, area in `office|pit|cantina|command|hangar`, at most one per area, immutable
  like revisions; matching upload table for the in-progress images.
- `src/sharing/den.js`: validates Den documents (above), builds requirements and counts
  (props, scenery edits; hidden scenery counts as an edit).
- Uploads: `POST /api/v1/den-uploads`, `PUT …/:id/payload`, `PUT …/:id/image/:area`, `POST
  …/:id/finalize` with the cover area; same auth, beta approval, quotas and cleanup as compositions.
- Reads: `GET /api/v1/den/:code/image/:area` (and by revision under My Shares);
  `GET /api/v1/codes/:code` → `{kind}` so **Have a code?** resolves either kind (codes are already
  unique across kinds).
- Website: `/dens` reuses the home gallery, filtered to Dens (replacing "coming soon");
  `/den/:code` detail page with the area images, counts (props, scenery edits), requirements, code
  and revisions. Matches the composition pages. No Storeroom or hidden-scenery wording.
- Tests in `test/api.test.js` and `test/web.test.js`.

## Runtime facts

- **Streaming**: settled. All five areas stay loaded while the editor is open.
- **Area names**: settled. The game doesn't name them; the five labels above are ours.
- **Area camera spots**: still open. When we're close to testing uploads, you'll go to each spot
  with ZC Sandbox running and I'll read off the camera transform for each.

## Order of work

1. Mockups on the HoloNet canvas (Dens browse, detail, share incl. pictures, import result,
   website listing and detail). Stop for approval.
2. Backend and tests. Stop: you deploy and run the migration.
3. In game: bridge (`den` catalog/download/upload with images, code
   lookup), Browse Dens, Share, Import, Apply. Camera spots recorded with you (ZC Sandbox) before
   upload testing. Lint, Python and native tests; patch bump and CHANGELOG; build, install. Stop.
4. Polish from your in-game feedback.
