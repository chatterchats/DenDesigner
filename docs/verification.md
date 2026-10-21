# Verification and release gates

## Automated checks

```sh
python3 -m unittest discover -s tests/python -p '*_test.py'
bash tools/build/build_gf.sh
bash tools/build/test_native.sh --existing
python3 tools/build/gf_build_info.py
python3 tools/build/package_gf.py
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

Historical evidence paths in the dated sections below describe their original runs. Those local
outputs are not source dependencies and may have been removed during cleanup. Current commands
and output locations are listed in the [development guide](development.md).

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
still passes `tools/build/gf_build_info.py`; the earlier 1,156 native-check result remains scoped to that
runtime build.

## Retired native prop-pack editor — 2026-10-20 (historical)

The editor-only plugin's **four native automation groups** passed in isolated SDK and base-modkit
projects: metadata parsing, validation, Slate panel construction, and the panel's actual Save/Build
callbacks through asynchronous UAT completion. The tests create a new pack from an engine cube,
validate its export and reopen its metadata. Python is explicitly disabled with `-DisablePython`;
ZComAuthoring is disabled too. Some engine plugins still mount PythonScriptPlugin as a dependency,
but its interpreter is disabled and no creator scripts are called.

Both kits also rebuilt the existing three-prop development sample through the native commandlet
and checked saved provider fields and GameState registration in a fresh editor process. The panel
and commandlet share the same authoring/export backend. The source/binary archive tests bring the
Python suite to **59 passing tests**. The game runtime remains the verified 76-asset build.

Evidence: `dist/kit-verification/native-editor-summary.json`, `*-native-tests.log`,
`*-native-build.log` and `*-native-verify.log`. Unreal's `-TestExit` forced shutdown returns status 1
on this host even when all four automation results are Success; the evidence records that separately
from the test results. Earlier headless harness failures are not counted as successful checks.
These are headless Slate and editor-service checks, not a manual visual signoff, a Windows build,
or a new shipping-game acceptance run. The former Source/Linux bundles have been replaced by the
widget/Python edition below.

## Widget/Python prop-pack editor — 2026-10-21

Prop Pack Editor **0.2.0-preview.1** replaces the custom C++ module. Both prepared public kits passed
real UMG panel construction, Save callbacks, provider/GameFeature authoring and the asynchronous
Build callback through cook, namespace audit and three-container export. A fresh process in each
kit verified serialized provider paths and exact GameState/component soft references with both
client/server flags. The SDK run created and hot-mounted a new pack. Custom native helpers were
explicitly disabled; Unreal's own Python interpreter was enabled.

The Python suite has **66 passing tests**, including metadata identity, symlink escape rejection,
foreign asset/inventory rejection, complete bundle hashes and exclusion of old binaries/source.
Logs are in `dist/python-editor/{modkit,sdk}-{build,verify}.log` and `python-tests.log`. The runtime
was not rebuilt or changed by this authoring-tool replacement.

A graphical check also opened the dockable panel in a dedicated Xvfb display using software Vulkan,
inspected the rendered layout, and confirmed that closing/reopening retains form edits and the
pending build future, then displays completion through Slate ticks. Evidence: `ui-check.log` and
`panel-preview.png`; maintainer script: `tests/unreal/test_pack_editor_ui.py`. Early attempts with
hardware Vulkan/NullRHI failed at the virtual-display layer and are not passing evidence.

These editor checks do not establish Windows execution or custom Windows shader compatibility.
The same Python bundle implements a Windows cook path, which still needs verification in a working
Windows editor. The stopped source-engine VM build is not a passing check.

## Fresh creator ZIP and exported-pack acceptance — 2026-10-21

The packaged **0.2.0-preview.1** widget/Python ZIP passed a separate installation check in a fresh
base-modkit copy. Only the base kit's previously built, engine-matched modules were reused; the
authoring plugin and minimal reference came from the ZIP, with manifest hashes checked. No private
Merged Kit or custom native authoring helper was installed. The project path contained spaces,
exercising the panel's new-pack restart/mount workflow.

A maintainer driver exercised the real panel's Save, Add selected meshes, Validate and Build
callbacks, using stock FBX/PNG import to create a checker-textured cube and an orange pumpkin.
The asynchronous cook and namespace audit produced an independent three-container pack. A fresh
editor process verified registration, material slots and the serialized texture override. This
automated panel check complements the rendered-panel check above; it is not manual Windows signoff.

That exact export was installed alongside the unchanged **0.9.0-preview.2** runtime in the shipping
Windows game under Proton, with UE4SS running only ZC Sandbox for test control. The game discovered
the provider without registration errors. Physical catalog/search/placement input displayed both
cards, generated their thumbnails and placed both props with the expected materials. The Save
button committed two entries. After a full process restart and sandbox Den load, both actors
returned at the recorded transforms; the committed document was unchanged, and both thumbnail
files retained their hashes and modification times while displaying correctly in the catalog.

Local evidence: `dist/creator-acceptance/summary.json`, `editor-{create,build,verify}.log`,
`export.json`, `game-{first-session,restart}.txt`, `committed-{before,after}.json`,
`thumbnail-{before,after}.json`, `catalog-pack.png`, `save-retry.png`, `restart-placed.png` and
`restart-catalog.png`. `setup.json` pins the tested ZIP hash; `preservation.json` records restoration
of the original saves, caches, containers and loader, with matching hashes. All 165 recorded
original kit source/config inputs also retained their hashes. The game was left closed.

This is focused exported-pack acceptance with assisted control, not a new standalone runtime
release certificate. Neither fixture had simple collision; solid collision and arbitrary custom
material shaders are outside this check. Windows editor execution remains pending independent
testing. No creator-plugin or runtime code fix was required by this pass.

## Repository organization check — 2026-10-21

After grouping tools by purpose, separating Python/Unreal tests and moving generated JSON to
`unreal/generated/runtime/`, all **66 Python tests** and **1,145 native Blueprint checks** passed.
All 75 generated specifications remained byte-identical. The runtime was authored and cooked through
the relocated build command, and the exact-build validator confirmed **76 cooked assets**.

Runtime/migration packaging passed in a separate smoke-test directory. The extracted scripted
creator bundle passed manifest validation and shell syntax checks without relying on the checkout.
All 39 local Markdown links resolved. The existing runtime ZIP was retained, and the previously
verified widget/Python creator ZIP retained its exact hash; rebuilding the runtime for path checks
does not replace their earlier in-game evidence. No game files were changed by this cleanup.

Current evidence: `dist/verification/reorganization/summary.json`, `package-smoke.json` and
`dist/build/runtime-logs/{author,cook,native-test}.log`.

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

`tools/build/gf_acceptance.py` lists the mandatory gates, including compositions and prop packs. A reviewed
report pins every result to the exact verified build, shipped documentation/tools and hashed evidence.
It rejects incomplete, stale, substituted or non-standalone evidence. Keep screenshots and process
records in local `dist/` output; the public certificate omits private evidence paths and reviewer data.

The historical 0.7.0 release passed full standalone acceptance. Later compositions, thumbnails and
prop packs received focused verification, including user confirmation of the textured sample cabinet
and pumpkins. The 0.9.0 line remains a **preview** until all current gates pass on one candidate build.
The project refresh removes obsolete source and prototype assets; it is not itself a new in-game
acceptance run.
