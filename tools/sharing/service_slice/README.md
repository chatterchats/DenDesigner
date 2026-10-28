# Reviewed Community download slice

This directory prepares a **single maintainer test publication** for the adjacent
`ZComShare` foundation service. It is source to review and deploy, not evidence
that any public record exists. No remote deployment, D1 mutation or R2 upload has
been performed by this preparation.

The smallest service change bundles 1,235 bytes of data with the Worker instead
of adding upload, authentication, database migration or storage dependencies.
The existing D1 published metadata queries continue to serve other listings.
This is intentionally not a general publishing implementation. An explicit
reviewed code is the only document available through the new route.

- Share code: `DenDesignerTest01`
- Page after deployment: `https://share.zcom.app/comp/DenDesignerTest01`
- Resolve: `GET /api/v1/comp/DenDesignerTest01`
- Download: `GET /api/v1/comp/DenDesignerTest01/document`
- `HEAD` returns the same status/headers with no body.
- The listing adds `document_bytes` and `document_sha256`, covering the exact
  UTF-8 response body. Download URLs are constructed by the client from the code;
  no URL supplied in metadata or downloaded documents is followed.
- Unknown/unpublished document codes return structured 404; malformed codes
  return 400. Public API mutations remain 403, including these routes.

`composition.json` is a portable schema 1 composition with one Control Monitor A,
no material overrides and no prop packs. `listing.json` records the exact length
and SHA-256. `published-composition.js` contains those same immutable bytes and
metadata. The published document is never evaluated as code.

`catalog-evidence.json` records the independent catalog row and catalog digest.
Catalog presence establishes where the asset declaration came from; it does not
prove that the asset loads in the shipped build. `test-inventory.json` is the
narrow target/dependency input for this particular test, not an inventory of all
installed or loadable content. Verify the mesh using the kit and shipped-game
composition preview before describing the import as verified. The client must
still check asset loading; it must not trust a downloaded ownership declaration.
Target compatibility is Steam build `25898267`, Den Designer
`1.1.0-preview.19`, native fingerprint empty for a composition.

## Prepare and review

From the Den Designer repository:

```sh
python3 -m unittest discover -s tests/python -p community_service_test.py -v
python3 tools/sharing/service_slice/prepare.py \
  --service ../ZComShare --output /tmp/community-service-review
```

The preparation command requires a new output directory, reads the adjacent
service, and only writes into the specified review directory. It checks each
expected integration point once and stops if the foundation source changed.
`worker.patch` includes the Worker integration plus updates to existing service
unit tests and the smoke verifier, whose previous expectations required an empty
composition gallery. `source.sha256` identifies the foundation Worker used to
produce the checked-in patch.

The tests validate the portable contract and independent catalog source; execute
five service integration tests against a patched temporary copy of the frozen
`foundation/` baseline; and execute all
eight existing foundation Worker tests with their revised gallery expectations.
The frozen source hashes are checked; applying or deploying the patch in the
adjacent checkout does not change the test baseline.
They exercise real Request/Response handlers with fake D1/asset bindings, not a
Cloudflare runtime, external HTTP connection or shipped game.

## Apply and deploy

When ready to change the Community checkout, inspect the patch and generated
module, then apply from that checkout:

```sh
git apply --check /absolute/path/to/ZComDenDesigner/tools/sharing/service_slice/worker.patch
git apply /absolute/path/to/ZComDenDesigner/tools/sharing/service_slice/worker.patch
cp /absolute/path/to/ZComDenDesigner/tools/sharing/service_slice/published-composition.js src/published-composition.js
npm test
npm run deploy:check
```

Copy the source test `worker.test.mjs` into a temporary folder with the prepared
Worker, its `catalog.js`, `views.js`, `security.js`, `package.json`, publication
module and `composition.json` to run those additional five checks directly with
`node worker.test.mjs`. The Python test already performs this temporary setup.

Deployment uses the existing service's documented command, `npm run deploy`.
It publishes the fixed maintainer record to the existing service and should be
reported separately from local preparation. No new paid service is necessary.
After deployment, run the service's smoke verifier and check the exact download:

```sh
npm run verify -- https://share.zcom.app
```

Then resolve/download the test through the actual Den Designer transport; compare
raw length and SHA-256 with `listing.json`, validate the portable envelope, and
record that connection separately from fake-transport/unit-test results. The
client should show missing-code/offline states until that deployment exists.

## Rollback and compatibility

Revert the patch and remove `src/published-composition.js`, then redeploy the
previous service version. This removes the explicit publication. There are no
D1 rows, migrations or R2 objects to reverse. Existing non-test metadata routes
and closed uploads do not change. Do not reuse `DenDesignerTest01` for modified
bytes: publish a new explicit code and retain the immutable old document.
