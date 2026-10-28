# Current in-game publishing UI — preview.20

The native review form described in the historical notes below has been removed.
Community → Upload now reviews an exact saved snapshot and all mesh/material
paths inside UMG, collects metadata, and uses the unchanged authenticated staged
composition API. Form values survive errors and area changes. The reviewed library
identity is checked again before sending. Public URL/share code copy actions use
the background bridge. Full Den upload/capture is unavailable; only explicit
new-preset saving and preset selection are offered in that area. The inspected
service has composition upload routes only, with read-only Den listing routes.

See [current player instructions](../distribution/community/README.md).

---

> Connection update: bridge 0.1.0-preview.6 adds in-game Connect, opt-in plain local
> remembered keys, automatic reconnect, and Forget connection. See
> [the authentication update](community-authentication.md). Earlier references to
> memory-only key entry in a separate window describe preview.5. Publishing review
> retains its native window in this update.

# Composition publishing — beta implementation

The implementation spans this checkout and adjacent `../ZComShare`. The frozen
`tools/sharing/service_slice/foundation` is historical regression data and is not
the running service source. No production deployment, production migration, beta approval,
or game installation is part of these implementation checks.

## Player flow

Connect with a personal upload key in the separate Community window. Select a
**saved composition card**, wait for its preview, and choose **Publish saved
composition…**. Publishing reads the saved library snapshot after checking its
revision; it never captures the current world selection. Mesh paths, decimal
transforms, collision mode, and ordered material slots are preserved.

The Community window reviews part count and every detected mesh/material path.
Enter a title (1–120 characters) and description (up to 4,000 characters). This
native beta uses printable ASCII text. Reviewed monitor paths are identified as
base game; other paths are explicitly unreviewed. The service independently
recomputes asset coverage, never trusts client pack ownership, author or media
metadata, and does not imply an unreviewed path is installed or loadable.

Choose Publish / retry. For an update enter the existing share code and its
current revision number. Successful updates keep the code and create an immutable
revision. The success message contains the public URL. The website account page
lists owned publications and offers Unpublish and authenticated revision recovery.

The bridge reads the **existing card PNG**, with the same cache filename algorithm,
from the fixed `Saved/ZComDen/thumbs` directory. The mailbox contains only a
restricted basename and structured composition values. No arbitrary paths,
response URLs, credentials, remote binaries, or SaveGame classes are accepted.
The identical thumbnail bytes are used on the page, gallery and social cards;
there is no second website render. A missing thumbnail blocks publication.

## Protocol and validation

All API endpoints return JSON independently of `/comp/{code}` HTML. Website
sessions require the canonical HTTPS Origin plus `X-CSRF-Token` on mutations.
Game upload keys use HTTPS Authorization headers, with expiry/revocation checks.
Public publishing is hard gated by `community_users.beta_approved=1` at upload
creation and at the final SQL publication transition. There is no environment
switch that allows general public publishing. Existing private review-queue
routes remain private and do not publish anything.

1. `POST /api/v1/composition-uploads` with `Idempotency-Key` (16–96 ASCII
   letters/numbers/underscore/hyphen) and `{title, description, code?, base_revision?}`.
   A new listing omits code and uses base revision zero. Creation reserves quota.
2. `PUT /api/v1/composition-uploads/{id}/payload` uploads JSON bytes.
3. `PUT /api/v1/composition-uploads/{id}/thumbnail` uploads the cached PNG bytes.
4. `POST /api/v1/composition-uploads/{id}/finalize` re-reads and validates **both
   stored objects**, creates the normalized downloadable document with authoritative
   attribution and integrity, then atomically creates the revision and public
   pointer. No incomplete upload is readable through public routes.
5. `GET` the upload endpoint checks status. `DELETE` cancels staging.

Each staged file uses a unique upload UUID and a conditional create-only R2 PUT.
A retry of identical bytes succeeds; different bytes conflict. Final document
bytes are deterministic, so a failure after storing the document but before D1
commit can be retried. A D1 trigger commits the revision and listing in one SQL
transition, rejects a stale base revision, and rechecks beta approval. The update
also rechecks the key/session grant. Competing updates cannot both become the
same revision. Retrying finalize or a lost success response returns the existing
publication. Revision database rows cannot be updated.

The native retry key covers metadata, payload and thumbnail. Repeated Publish
clicks and a lost final response recover the same publication. Expired/cancelled
staging gets a fresh request-token-derived key. Changing metadata starts a new
upload. Cancellation checks mailbox identity before every stage and before
finalize. If cancellation races an already committed finalize, publication may
have completed: check the account listing and unpublish if needed. Closing or
crashing before cancellation leaves private staging for scheduled cleanup.

### Enforced limits

| Resource | Service limit |
| --- | --- |
| Uploaded and normalized payload | 256 KiB each |
| Composition parts | 1–128 |
| Material slots per part | 64 |
| Images | Exactly one thumbnail |
| PNG bytes | 1 MiB |
| PNG dimensions/pixels | Up to 1024×1024 / 1,048,576 pixels |
| Accepted PNG encoding | 8-bit RGB/RGBA, noninterlaced, nonanimated |
| Simultaneously active uploads | 3 per account |
| New uploads | 20 per rolling 24 hours, including failed/cancelled uploads |
| Retained storage reservation | 64 MiB per account, including all revisions and staging |
| Staging lifetime | 1 hour |

Reservation conservatively includes a full payload allowance for retained source
JSON, normalized document and PNG. The native transport additionally has a 64 KiB
SaveGame and 48 KiB wire budget; it fails closed rather than truncating large
values. API clients can use the larger service payload allowance. The game allows
10 minutes to review a publish request, with a 25-second active network deadline.

Payload validation checks actual byte counts, UTF-8 JSON, duplicate keys, nesting,
part/material limits, asset paths, finite transforms and positive scales. The
service reconstructs complete portable entries rather than storing arbitrary
client fields. Native-level entries, hidden entries and incomplete transforms
cannot be published as compositions. PNG validation checks the signature, every
chunk length and CRC, ordering, IHDR dimensions/encoding, IEND, absence of trailing
data and animation, bounded zlib decompression, exact raster length and filter
bytes. MIME, Content-Length, extensions and caller-supplied image dimensions are
not evidence of validity.

## Public reads, updates and retention

- `GET /api/v1/comp/{code}` resolves current metadata; `?revision=N` pins an old
  revision while the listing is public.
- `/document` and `/thumbnail` under that endpoint return revision bytes, with the
  same optional revision query. Document metadata includes exact size and SHA-256.
  The native downloader pins the resolved revision before downloading and checks
  both hash and byte length. Metadata image paths are never fetched by the game.
- `/comp/{code}` is server-rendered with creator/profile, thumbnail, description,
  part count, requirements, revision, share code, copy buttons and download.
  Open Graph and Twitter metadata are in the initial HTML for unfurling services.
- `GET /api/v1/my/compositions` lists owned publications.
- `DELETE /api/v1/my/compositions/{code}` unpublishes only the authenticated
  author's listing. Public metadata and file routes then stop serving it.
- `GET /api/v1/my/compositions/{code}/revisions/{N}/document` (or `/thumbnail`)
  recovers an author's retained revision even after unpublishing.

**Retention policy:** all finalized revision documents, source payloads, thumbnails,
and revision records are retained indefinitely during beta, including after
unpublishing. They count against the author's quota. There is no automatic
pruning or in-place replacement of published files. Old public revision URLs work
while the listing is public; the owner recovery API works after unpublishing.
Changing this policy requires a separately reviewed migration and advance notice.
Unpublishing cannot erase copies already downloaded or cached by other services.
Public file responses revalidate after at most 60 seconds; private reads are no-store.

The hourly cleanup handler marks expired uploads closed and deletes only
cancelled/expired upload objects. It processes a bounded, fairly rotated batch
and repeats tombstone deletion to catch late PUTs racing cancellation/expiry.
Published UUIDs are never selected. Failed deletes leave tombstones for retry.
Tombstones also retain idempotency outcomes and usage history; they are not
published documents. Bucket access must remain private with no r2.dev/public
custom domain, listing access or direct signed upload URLs.

## Verification and release boundary

Run the Community service tests, `scripts/verify-publication-runtime.mjs` (local
workerd/R2), and `npm run deploy:check` in `../ZComShare`. Run
`python3 -m unittest discover -s tests/python -p composition_publishing_test.py -v`
here for the actual service publication → portable validator → native parser
round trip, preserving decimal transforms and material order. Run the existing
Community Python suites, `native/community/connection-smoke-build.sh` plus the
matching isolated Wine smoke executable, and `tools/build/test_native.sh` for
compiled Blueprint coverage. The fake native transport exercises staged upload
failure, retry after a lost finalize response, duplicate recovery and cancellation.

Before release: apply additive Community migration `0003_publishing.sql` before
deploying the Worker, deploy its built static assets and hourly trigger, retain the
private bucket configuration, ship the matching pak/native bridge, and verify an
actual approved-account publish/update/import in the shipped game. Check a live
social unfurl separately. Unit tests, local workerd, kit VM and Wine smoke do not
establish live Steam, production deployment or shipped-game acceptance.

Completed local checks on 26 October 2026:

- Community: 19 Node tests passed, including fault injection, concurrent revisions,
  revocation during finalize, usage limits and owner recovery.
- Local workerd/R2: conditional create-only writes and PNG decompression checks passed.
- Additive migration: 8 SQL commands applied successfully to local development D1.
- Designer: 35 existing Community Python tests plus the new cross-repository
  publication/import round trip passed.
- Compiled Unreal runtime: 1,405 checks passed, including saved-card publication,
  thumbnail basename, material preservation and cancellation.
- Windows proxy/worker cross-compilation and isolated Wine fake-transport smoke
  passed. Service website build and deployment dry run passed.

Production publication, actual signed-in player UX, real cached PNG upload from
packaged rendering, social unfurl and shipped-game placement remain live release
acceptance checks. Native beta title/description entry currently accepts ASCII;
this is a UI limitation, not a service trust boundary.

## Production deployment — 27 October 2026

Deployed to https://share.zcom.app at the user's request. Production migration
`0003_publishing.sql` applied successfully (8 SQL commands). Worker version
`6a31cf81-f9f4-479e-bf6b-153ecff69484` includes the updated static assets and hourly
cleanup schedule (`0 * * * *`). The 19 service tests passed before deployment.

Post-deployment: all 32 standard website/API smoke checks passed. Additional live
checks confirmed the beta-publishing health stage, file storage binding, deployed
publishing assets, and 401 responses for unauthenticated upload creation,
finalization, and author-list access. No account approvals or test publications
were created. Authenticated player publication, packaged-game thumbnail upload,
import/placement and a real social unfurl remain acceptance checks. Deployment
updates the service; the matching game pak/native bridge still requires installation.
