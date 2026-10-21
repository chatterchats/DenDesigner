# Verification and release gates

## Automated checks

```sh
python3 -m unittest discover -s tests -p '*_test.py'
bash tools/build_gf.sh
bash tools/test_native.sh --existing
python3 tools/gf_build_info.py
python3 tools/package_gf.py
```

Python tests cover migration, safe installation, release acceptance, catalog conversion and prop-pack
manifests, reference export and the standalone creator-bundle inventory. Native tests execute compiled Blueprint functions in the kit, including persistence,
world application, picking, gizmos, editor UI, input, preferences, catalog, thumbnails, compositions
and provider registration. Fixed gizmo cases preserve 360 differential rays from the earlier verified
implementation without retaining that runtime as a dependency.

A passing native suite does not by itself prove correct shipping-game input, rendering or travel.
Likewise, a preview ZIP is not a stable release certificate. Record the exact build and actual results
rather than copying an older test count into a new release.

## Project-refresh results — 2026-10-20

For `0.9.0-preview.2`, the cleaned project passed **54 Python tests** and **1,156 native checks**
on the reauthoring pass, including the layout/draft/preset persistence fixtures. The editor cook
contains 75 runtime/UI specs plus the GameFeatureData asset (**76 cooked assets**). The independent
sample cook contains 18 container entries including its header. Exact-build and archive checks pass.

Local evidence: `dist/python-tests.log`, `dist/gf-logs/native-test.log`, `dist/gf/build-info.json`,
`dist/prop-packs/DenPropsExample/logs/` and `dist/packages.json`. These files are generated outputs,
not required source dependencies. No new shipping-game regression is claimed for this cleanup.

## SDK/base-modkit and repository checks — 2026-10-20

The subsequent creator-tooling pass brought the Python suite to **57 passing tests**. It did not
change the 76-asset runtime build. Both prepared public kits passed sample FBX/texture import,
provider authoring, cooking, independent packaging and fresh-editor reload on Linux UE 5.6.1.
The extracted standalone creator bundle also passed author/cook/package/reload in both kits,
using the already imported sample assets. Each output has 18 entries including its container header;
neither includes the shared authoring reference or helper. See the
[compatibility report](../authoring/prop-packs/kit-compatibility.md) for prerequisites and limits.

Local evidence is in `dist/kit-verification/summary.json` and adjacent logs. The 1,076 SDK and
68 base-modkit source/config/project files recorded before testing retained their hashes. These
checks do not claim a Windows editor build or a new in-game acceptance run. The current runtime
still passes `tools/gf_build_info.py`; the earlier 1,156 native-check result remains scoped to that
runtime build.

## Shipping-game checks

Use the throwaway ZC Sandbox campaign (`BA3302BC4165EB931E86A39BFF208F71`) on the main installation.
Before testing, snapshot the mod's Saved directories, sandbox saves, installed containers and loader
state. Preserve original files and capture hashes. Close the game before changing containers.

For standalone proof, disable the UE4SS loader and verify its absence from the running process.
ZC Sandbox and a Lua inspection console are useful in diagnostic runs, but do not establish standalone
operation. The game can be launched through Lutris and exercised through guarded input. Obtain an
uninterrupted input window; stop input or screenshot capture when the game loses focus.

Exercise startup/close/restart, selection and architecture switches, transforms and all handles,
history, catalog/search/repeated placement, Storeroom, layouts/presets, preferences/rebinding, drafts,
migration, thumbnails, compositions and prop packs. For pack updates/removal, preserve asset paths
and verify that missing content is retained in the layout. Do not infer that check solely from a
successful initial registration.

The optional `tests/integration/native_travel/build.sh` creates a separate **DenTravelQA** feature
for the sandbox's mission-success sequence. It is never installed automatically or shipped. Its F7
completion helper is restricted to the sandbox campaign and `SK_Kaller_020_Root`. Remove it after use.
Never use the real campaign as a disposable test fixture.

Archive test-only layouts and screenshots, restore original sandbox files and loader state, and
verify original mod-data hashes afterward. Do not change INIs or another mod's settings. Installed
mods may be symlinks: never disable them by renaming their source `enabled.txt`.

## Evidence and packaging

`tools/gf_acceptance.py` lists the mandatory gates, including compositions and prop packs. A reviewed
report pins every result to the exact verified build, shipped documentation/tools and hashed evidence.
It rejects incomplete, stale, substituted or non-standalone evidence. Keep screenshots and process
records in local `dist/` output; the public certificate omits private evidence paths and reviewer data.

The historical 0.7.0 release passed full standalone acceptance. Later compositions, thumbnails and
prop packs received focused verification, including user confirmation of the textured sample cabinet
and pumpkins. The 0.9.0 line remains a **preview** until all current gates pass on one candidate build.
The project refresh removes obsolete source and prototype assets; it is not itself a new in-game
acceptance run.
