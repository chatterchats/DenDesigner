# Separate Community architecture — preview.22 / bridge preview.10

Installed with the game closed: distinct **Compositions** and **Community** toolbar
navigation and widget classes. WBP_DenCompositions is restored to the local
creation/library/placement workflow. New WBP_DenCommunity owns the online controls
and independent public-selection, upload-source, review/form and account state.
Both use the existing library dock geometry, styling, fonts, native cards and
navigation lifecycle; no native desktop form or embedded website is involved.
The installed preview.22 game remained running through the 50-second startup
smoke check with no new crash report; no save was loaded.

Completed on the final build:

- **1,444 compiled Unreal checks passed**, including actual native public-feed
  bytes and a real revision-pinned six-part public document delivered to the
  in-game parser. Public selection and local preview do not affect local selection
  or write the library. Explicit Download adds a saved composition without placing
  or selecting it. Upload source selection, reviewed payload and form survive
  public browsing, recoverable errors and tab changes. Browse actions cannot
  replace an active upload. Existing local Composition/Layout tests still pass.
- **82 Python tests passed**, including catalogue search/pages, bounded metadata,
  stale/unrevisioned entry exclusion, service/native contracts and installers.
- All **110 cooked packages and their scripts deserialize without errors**.
- The native bridge read the actual live catalogue without authentication, omitted
  the stale unrevisioned maintainer fixture, fetched the real public listing and
  downloaded its pinned revision with hash/size/schema/dependency validation. No
  publication, account mutation, credential read or game-library write occurred.
- Isolated Wine fake-transport regression passed for connection, remembered keys,
  saved-snapshot publishing, cache PNG padding removal, staged retry, lost finalize
  recovery, duplicate recovery and no visible controls. Its manual timer pumps use
  an isolated prefix and synthetic credentials; none are game/account secrets.
- Pak/native archive and installed hashes match. Previous files are retained under
  `dist/state/community-separated-install-*`; installation evidence is
  `dist/verification/community/separate-window-install.json`.

Browse uses six-card pages and client search over the deployed v1 service feed,
which currently returns its latest 24 entries. Each displayed card is a real
revisioned public listing. Previews download validated ordinary part values and
use the existing bounded asynchronous local render/cache service, keyed by code
and immutable revision. Remote image URLs, binaries and SaveGame classes are not
loaded. Detail includes creator, description, revision and detected/unknown
requirements; decoded part paths also populate full dependency review.

Dens browsing is a labelled placeholder without cards/download actions. Full Den
Upload lists saved local presets, with explicit save-current-as-new-preset and a
disabled Publish button explaining the missing Den backend/capture stage. No Den
values use composition endpoints. Authenticated composition publishing, ownership,
immutable revisions, idempotent retry, cancellation and the cached-PNG fix remain.
A newly authenticated publication through the moved controls remains player
acceptance; the prior bridge's live publishing success is not relabelled as a
new live publication test.

---

# Startup crash correction — preview.21 / bridge preview.8

Preview.20 is withdrawn after a shipped-game startup null dereference. Independent
cooked export/script parsing reproduced invalid serialized property types in the
editor host. The preview.19 baseline parsed cleanly with the same setup. Native
bridge binary hashes were unchanged, and the crash was in property loading in the
game executable rather than the background transport.

Preview.21 separates editor state/leaf helpers into BP_DenEditorState and splits
the help/transform graphs. All **108 cooked packages and their scripts deserialize
without errors**; **1,430 compiled kit checks** and **77 Python tests** pass.
Packaging now requires successful cooked verification against the exact container
hashes. It rejects parser errors/warnings about failed script serialization even
when the parser exits zero. No failing intermediate rebuild was installed.

The corrected paired build was installed with the game closed and all hashes
verified. The previous installation remains in its timestamped backup. Runtime
startup acceptance is recorded in `dist/verification/community/startup-after-fix.json`;
the crash diagnosis and clean baseline are retained under
`dist/verification/community/launch-crash-preview20/`. The underlying engine
serialization defect is not established; the verified class split is the fix for
this build. Community feature scope and Full Den limitations are unchanged.

---

# In-game Community UI verification — 27 October 2026

Installed for testing with the game closed: **pak 1.1.0-preview.20** and
**bridge 0.1.0-preview.7**. The installation verified both archive inventories,
CRC, source/build records and installed hashes, and backed up the previous pak and
bridge. Local evidence: `dist/verification/community/inpanel-install.json`.
Paired bundle: `dist/packages/DenDesigner-Community-1.1.0-preview.20.zip`.

Completed against the final build:

- Blueprint authoring and cook: no compile warnings; 107 cooked assets verified.
- Compiled kit VM: **1,430 checks passed**, including masked key entry/clearing,
  exact saved composition serialization, separate reviewed upload state across
  Browse/Upload/Account switches, retained metadata after cancel/failure, stale
  and deleted selections, changed library identity, disconnected account replies,
  retry, progress without request completion, public URL/share-code extraction,
  background copy commands, panel-close invalidation and the unavailable Den area.
- Python: **76 tests passed**, including service round trip, dependency validation,
  protocol parsing and installer rejection cases. Log:
  `dist/verification/community/python-tests.log`.
- Windows cross-compilation and isolated Wine fake transport passed. Its connection
  endpoint is an HWND_MESSAGE window with **no child controls and no visibility**.
  The exact synthetic UMG-generated `inpanel-publish.sav` exercised disconnected
  account and missing-thumbnail failures, then publication with the UMG title and
  description after supplying a fake cached thumbnail. Native staging tests covered
  retry after thumbnail failure, a lost finalize response, duplicate recovery and
  cancellation. No real key or live upload was used.
- A separate blocked fake-network run deleted its mailbox and exited with Windows
  `ERROR_CANCELLED` (1223; Wine shell status 199), proving cancellation terminates
  active connection work rather than waiting for network completion.
- Installed pak and both native binaries match the packaged hashes. The previous
  installation is retained under `dist/state/community-inpanel-install-*`.

What works in this stage: composition import-by-code/link and existing local card
preview/placement; saved snapshot review and publication metadata in UMG; masked
connection, explicit Remember/Forget, background authenticated staged composition
uploads, conflict/idempotency checks, in-panel progress/errors/results and copy
commands. Only the explicit website account action opens the browser. Native
transport has no desktop form, ShowWindow or foreground activation.

What remains pending: remote gallery browsing (the dedicated Browse area is ready
for that stage), Full Den service upload/capture/revisions and Full Den import.
The Full Den area only offers explicit save-current-as-new-preset and saved-preset
selection; it sends no Den data to composition endpoints. Dependency paths and
unknown pack coverage are reviewed locally, while the service remains authoritative
and may reject unreviewed dependencies. Metadata remains printable ASCII in this
beta. Real Steam sign-in, an approved-account live publish/update, clipboard behavior
and visual layout in the shipped game still require player acceptance; kit VM and
fake transport tests are not claims of those live results.

---

The remaining sections record prior bridge stages and their historical acceptance
boundaries; references to desktop forms below are superseded by the current build.

# Community vertical slice verification

## Shipped-game happy path confirmed

On October 26, the user confirmed that bridge **0.1.0-preview.3** with runtime
**1.1.0-preview.19** successfully fetched and imported the published test
composition, generated its thumbnail, placed it, and retained it after restarting
the game. This is **user-reported shipped-game acceptance**, recorded separately
from the automated kit and native harness results; it was not an agent-observed
UI recording.

The read-only vertical slice is therefore confirmed in the shipped game for
`DenDesignerTest01`. Broader composition/dependency support remains outside its
documented limits. Failure-path coverage is still from the automated/native tests
unless separately recorded as an in-game test. The user did not report manual
offline, malformed-response or oversized-response acceptance checks.

## Shipped request format correction

Bridge **0.1.0-preview.3** accepts both measured SaveGame property tag layouts.
The game successfully started after preview.2, and actual Fetch clicks wrote
requests to the expected private mailbox. The worker rejected them because the
editor fixture's tags contain GUIDs (`flags=2`), while the shipped game strips
those GUIDs (`flags=0`). Both layouts use the same class, property types and
payload schema. The reader now accepts only those two known flags and preserves
the exact local layout in responses, rejecting all unknown flags.

The actual shipped request was captured read-only and tested against native live
HTTPS in the disposable prefix. A normalized regression fixture preserves its
header/tag layout while replacing the correlation token. Truncated requests and
unsupported flags remain rejected. The core pak is unchanged. Native live download plus cancellation/deadline/exit
checks passed with those exact request bytes, and a fresh kit process completed
1,421 checks including reading that response, importing, staging its thumbnail,
placing and undoing the published monitor. Preview.3 was installed with the game
closed; no pak or loader configuration change was needed.

Latest package: `DenDesigner-CommunityBridge-0.1.0-preview.3.zip`, SHA-256
`af4f1832e47ccbb7acabc00fb20b26bdde81b4484b7a82cb38628574f62879f5`.
Subsequent user testing confirmed successful response handling, thumbnail
rendering, placement and persistence after restart inside the shipped game.

## Startup failure and corrected bridge

Bridge **0.1.0-preview.1 is withdrawn** after a real shipped-game startup crash.
The crash occurred at zero seconds with Wine exception `0x80000100`. Its two
exception parameters point into the loaded `d3d12core.dll`; mapping those RVAs
back to the exact DLL yields `VERSION.dll` and `VerQueryValueA`. The original
proxy forwarded the executable's three direct imports but omitted that ANSI
function used by Direct3D and ReShade. This was a proxy compatibility defect,
not evidence of a Blueprint importer failure.

Bridge **0.1.0-preview.2** forwards all 16 public version APIs. A new regression
checks the captured import requirements of the game, ReShade and the actual
game-prefix Direct3D DLL. The native smoke checks all 16 exported names, calls
both ANSI and Unicode `VerQueryValue`, and successfully loads that real Direct3D
DLL with the corrected proxy present. Live download and all lifecycle checks
also passed again. The fix is installed; the pak and request worker are unchanged.
The original package is quarantined under the startup-crash evidence directory.
Subsequent user testing confirmed game startup and Fetch request creation;
preview.3 subsequently passed user-reported in-game response/import testing.

Historical startup-fix bridge archive (superseded by preview.3):
`DenDesigner-CommunityBridge-0.1.0-preview.2.zip`, SHA-256
`0c7f08805be24c5f0dba8b2f6b3d2ece5471f32626e675837e4a3a6942c679a5`.
Crash reports, original bytes, decoded cause and the replacement installation
record are retained in `dist/verification/community/startup-crash/`.

The Community path uses **no UE4SS**. The offline editor remains a content-only
Game Feature. Its optional standalone bridge is a Windows `version.dll` proxy
plus a bundled, short-lived `den-community.exe` request worker. No engine
functions, UObject layouts or game-thread hooks are used. The pak communicates
through its own typed SaveGame mailbox and ordinary composition methods.

## Scope and limitations

This is an experimental vertical slice for the reviewed base-game Control Monitor
A. Native validation supports canonical ASCII schema-1 composition payloads with
integer transforms, up to 128 parts, no media, no material overrides and no prop
packs. Other data fails closed. The broader Python portable-contract client is
reference tooling, not an installed runtime dependency. Publishing and public
uploads are outside this slice; the service's API writes remain disabled.

HTTPS is restricted to `share.zcom.app` and the two constructed `/api/v1/comp/`
routes. Input accepts an opaque code or an approved HTTPS zcom.app composition
link. Redirects, authentication challenges, cookies and compressed responses are
rejected. Metadata is capped at 64 KiB and documents at 4 MiB; no allocation is
sized from downloaded lengths. A worker has a 25-second total deadline covering
DNS, TLS, body reads and parsing. The proxy cancels its owned process when the
request changes/disappears and puts it in a kill-on-close Job object. The pak
checks its independent 65-second deadline before parsing or committing a response.
It parses at most ten value records per tick and rejects stale tokens, malformed
values, unsupported wire schemas, duplicate names and extra trailing content.

No downloaded binary, script, Blueprint or SaveGame is executed/deserialized.
The worker creates its response using the locally generated request's validated,
fixed class/tag schema and bounded text values. Local library saves use the
existing rotating store and readback checks. Import never changes the working Den;
placement uses the existing asynchronous preview and whole-group transaction.

## Observed results

| Layer | Result | What it establishes |
| --- | --- | --- |
| Python and native portable checks | 72 tests passed | Portable contract, approved inputs, fake HTTP framing/error cases, native JSON/GVAS parser including both shipped/editor tags, malformed/truncated data, graphics dependency exports and guarded installer behavior. |
| Blueprint authoring and cooking | 81 specifications, 107 cooked assets; no Blueprint compile warnings | The content-only runtime compiles/cooks in the private UE 5.6.1 kit. |
| Blueprint VM, fresh process | 1,421 checks passed, including exact native response | Request serialization, cancellation, timeout-before-commit, bounded parsing, local import, anchor/material preservation, duplicate protection, published monitor loading, thumbnail staging, placement and undo. |
| Reference HTTPS client | Live resolve and download validated | The deployed service returned the published 1,235-byte document and both integrity checks/dependency preflight passed. This is not the game transport. |
| Windows native transport under Wine | Live HTTPS smoke passed | System version functions forwarded; native worker downloaded and validated the actual test; native GVAS response was read successfully by a separate Unreal process. No game process was used. |
| Native request lifecycle under Wine | Five checks passed against final binaries | Live fetch/forwarding, cancellation, 25-second total deadline, parent exit and kill-on-close cleanup; lifecycle tests substitute an inert waiting worker in a separate test directory. |
| Shipped game | **User confirmed the happy path** | Live fetch/import, rendered thumbnail, placement and persistence after a game restart. This is user-reported acceptance, not an agent UI capture or manual in-game verification of every error path. |

The headless thumbnail checks load and stage real geometry, verify the normal
queue/cache path and clean up temporary actors. Their completion texture is a
fixture; **they do not prove rendered thumbnail pixels or PNG output**. The
runtime calls the existing rendering/capture system when used with rendering
available.

The cross-process test consumed `native-response.sav` produced by the native live
HTTPS worker, then imported and placed the actual published monitor through the
ordinary kit composition workflow. It did not rebuild the response's properties
using Python. The expected correlation token was installed explicitly in the kit
fixture; no Windows worker was running against the kit's SaveGame directory.

Evidence is retained under `dist/verification/community/` and
`dist/build/runtime-logs/native-test.log`. Machine-specific paths and hashes are
in [runtime evidence](community-runtime-evidence.md) and
[its probe](community-runtime-probe.json). These reports distinguish the historical
reflection inventory, current executable bytes and local engine source; native
decompilation was unavailable and is not claimed.

## Published service

The owner approved publication of a single maintainer test record. The existing
Community Worker was deployed as version
`9f670209-8172-401a-b74e-a68bf8f5adde`. Its 31 HTTPS smoke checks passed, including
closed API writes. No account, database migration or R2 upload was added.

- Code: `DenDesignerTest01`
- Page: <https://share.zcom.app/comp/DenDesignerTest01>
- Listing: `/api/v1/comp/DenDesignerTest01`
- Document: `/api/v1/comp/DenDesignerTest01/document`
- Exact document: 1,235 bytes, SHA-256
  `299a9d44f498cea6a7053501c9054779ef26dc4534520cc4b3718420c40977c1`
- Payload SHA-256:
  `995bc4e5c878814326ec10f63a0ed8d2f68ad0877c63315a3ba63a58b456d2d0`

The service extension and reproducible local test fixture are in
`tools/sharing/service_slice/`. It is deliberately an immutable reviewed
publication, not a general-purpose upload implementation.

## Reproduce and finish acceptance

The verified core runtime `1.1.0-preview.19` and optional bridge
`0.1.0-preview.1` were packaged and installed on October 26 with the game closed.
Installed bytes were checked against their archives. The existing Den Designer
files and Lutris configuration were backed up under
`dist/state/community-install-20261026-222051/`. Only the `version: n,b` override
was added; other overrides and ReShade files were preserved. The game was not
started. Exact installation targets and hashes are recorded in
`dist/verification/community/install.json`.

Package SHA-256:

- `DenDesigner-Pak-1.1.0-preview.19.zip`:
  `a917febdfd5877296f7b3a1bf5e63047a4af69cec10fb4d9c38cc0fb81ec15b1`
- `DenDesigner-CommunityBridge-0.1.0-preview.1.zip`:
  `f9c00ee466ff521f63094e122c25b263a930e2cd243e40ec645b6bc91f361f19`

The final native lifecycle record is `native-lifecycle.json` beside the other
local evidence. An initial rerun without `version=n,b` exercised Wine's built-in
DLL rather than the proxy and timed out; it was excluded from passing results.
The configured rerun exercised the final installed binary hashes and passed all
five checks.

```sh
python3 -m unittest discover -s tests/python -p '*_test.py'
bash native/community/smoke-build.sh
bash native/community/lifecycle-smoke-build.sh
# Run the Windows harnesses in a disposable Wine prefix with version=n,b.
# Do not substitute the game prefix for these test harnesses.
DENDESIGNER_NATIVE_RESPONSE="$PWD/dist/verification/community/native-response.sav" \
  bash tools/build/test_native.sh --existing
bash tools/build/build_gf.sh
python3 tools/build/package_gf.py
python3 tools/build/package_community.py
```

`--existing` requires the current assets already authored. Do not run authoring,
cooking or kit tests concurrently against the same project. Native test harness
executables and the inert waiting worker are excluded from the bridge package.
The package contains only the real DLL, real request worker, installation guide,
license and integrity manifest.

For shipped-game acceptance with UE4SS absent, open Compositions, fetch the code,
read the dependency report, reopen the library after restarting, wait for a real
local thumbnail, and place/undo the monitor. Also check cancellation while offline,
unknown codes, bridge absence and a stopped request. Capture the game's bridge log
and rendered thumbnail separately. Do not mark these steps passed from kit tests.

## Remember connection — 27 October 2026

Bridge 0.1.0-preview.6 and runtime build `5aa48b72c3b5` add masked in-game key
entry, explicit Remember connection opt-in, automatic reconnect, session disconnect
and Forget connection. The remembered key is plain local storage in
`Saved/SaveGames/ZComDen/Community/v1/connection.key`; campaign saves and composition
exports do not contain it. See the updated authentication document for tradeoffs.

Verification: 37 Community Python checks and the cross-repository publication/import
check passed; all 1,417 compiled Unreal checks passed. The isolated Wine fake-transport
smoke tested actual file write/read/delete, session-only behavior, remembered reconnect,
revocation removal, malformed-file refusal and publishing retries. The pak cook verified
107 assets. The installed runtime containers and bridge binaries match their package
hashes; the prior install was backed up and the separate dxgi loader preserved. No game
was launched and no campaign saves were changed. Real authenticated player connection
and packaged-game publishing remain acceptance checks. Publishing review retains its
existing native window; connection setup is in-game.

## Cached preview upload rejection — bridge preview.9

The player reached “Uploading cached preview” before the generic failure. Eight
recent local composition-cache files all failed the unchanged service PNG
validator because they contained bytes after a valid IEND. The matching engine
source, `FImageUtils::ExportRenderTarget2DAsPNG`, serializes
`CompressedData.GetAllocatedSize()` rather than the encoded array length.
No suffix contents, credential files, process dumps or raw service error bodies
were retained in diagnostics.

Bridge 0.1.0-preview.9, for the existing pak preview.21, validates PNG signature,
IHDR limits/encoding, chunk boundaries/order and CRCs through IEND, excludes and
zeros the local suffix, then sends the exact encoded cached PNG stream. It never
re-renders or re-encodes the preview. Public/server validation is unchanged and
still rejects trailing bytes. The native source-cache digest preserves the old
idempotency identity so a previously rejected thumbnail can finish its original
staged upload instead of consuming another staging slot.

All eight exact cached PNG streams pass the service validator after normalization;
only metadata/byte counts were recorded in `cached-png-fix.json`. The Python suite
passes **79 tests**. An isolated Wine test used the real UMG-generated request,
a valid synthetic PNG with allocator-like padding, and fake staged HTTP: only
complete PNG bytes reached the thumbnail PUT; the excluded buffer suffix was
zeroed. Existing failed-thumbnail retry, lost-finalize recovery, duplicate recovery,
cancellation and no-visible-controls checks passed. Known service errors now map
to fixed specific UI messages; arbitrary server strings cannot be reflected.

This is a transport-only correction. The preview.21 pak and its successful cooked
verification are unchanged. A live authenticated retry remains player acceptance.

Bridge preview.9 was installed with the game closed; installed hashes and the
previous-bridge backup are recorded in `png-bridge-install.json`.
