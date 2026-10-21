# SDK and base-modkit authoring verification

Verified on **2026-10-20**, with the locally installed **UE 5.6.1 Linux editor**, Den Designer
`0.9.0-preview.2` and the Arcade & Halloween sample. Both routes authored and cooked the three
meshes, material instances, registration Blueprint and GameFeatureData, then produced the three
independent containers with only the sample's assets. Neither route required a private merged kit,
reconstructed game classes or the full Den Designer editor runtime.

This is **authoring/cook/package verification**, not a new in-game or Windows-editor acceptance run.
The previous in-game sample check used a different development build. Arbitrary custom Windows material
shaders remain a separate requirement; the tested sample uses existing engine material parents.

## Scripted workflow results

| Check | SWZC SDK | Base SWZC Unreal Modkit |
|---|---|---|
| Import FBX and textures; assign materials | Passed | Passed |
| Author provider inheriting the shared pack base | Passed | Passed |
| Preserve exact registration after restarting editor | Passed | Passed |
| Cook and package all three containers | Passed | Passed |
| Container inventory limited to this pack | Passed — 18 entries including header | Passed — 18 entries including header |
| Additional setup | Editor mounting, authoring reference/helper, DLC baseline | Editor mounting, authoring reference/helper, matching editor binaries |

Both public kits need the supplied creator dependencies and a suitable cook baseline. The SDK has
`BitReactorGameState`, but lacks the mod-editor auto-mount route and the trimmed DLC baseline.
The base modkit lacks that class, but can preserve its **soft class path** in the component action.
No replacement native GameState class was added. Registration resolves the real class in game.

## Widget/Python editor workflow (recommended)

The **[Prop Pack Editor](EDITOR-GUIDE.md)** `0.2.0-preview.1` replaces the provisional native module
with a stock Editor Utility Widget and bundled Python. Creators use the Tools menu, with no manual
scripts, external Python installation or custom C++ compilation. It uses Unreal's own Python and
Editor Scripting Utilities plugins, the minimal provider reference and the same cook baseline.

On **2026-10-21**, both prepared public kits passed the real UMG Save callback and asynchronous
Build path using an engine cube: metadata, provider/GameFeature authoring, cooking, namespace audit
and three-container export. A separate editor process in each kit verified saved registration,
including the unresolved game-class soft path in the base modkit. ZComAuthoring and the old native
editor module were disabled. The SDK check also created and mounted a new pack in the same session.

The single content/Python ZIP has no custom native binary or engine BuildId requirement. This does
not repair underlying kit binaries. A relocated SDK test copy needed its engine/project/plugin
binary paths on `LD_LIBRARY_PATH`. Windows editor execution remains unverified.
Python does not provide Windows shader cooking on Linux. A separate graphical check in the base
kit verified the rendered panel and tab-reopen/build-completion lifecycle.

Evidence for this edition is under `dist/python-editor/`: `modkit-build.log`, `sdk-build.log`,
`modkit-verify.log`, `sdk-verify.log` and `python-tests.log`. The earlier native-plugin tests under
`dist/kit-verification/` are historical, not evidence for this implementation.

A subsequent fresh-ZIP check on 2026-10-21 used a new base-kit copy, reusing only its engine-matched
base modules. The real panel callbacks created, validated and exported a two-prop pack after stock
FBX/PNG import, including the restart/mount path for a project directory containing spaces. That
exact export passed discovery, catalog thumbnails, textured placement, saving and a full restart
in the shipping game under Proton. Cached thumbnails retained their hashes and modification times.
ZC Sandbox supplied test control; this does not certify standalone operation or Windows authoring.
Original game data/mods were restored with matching hashes. Evidence and limits are recorded in
[the fresh creator acceptance report](../../docs/verification.md#fresh-creator-zip-and-exported-pack-acceptance--2026-10-21)
and local `dist/creator-acceptance/`. No custom native authoring helper was used.

The remaining instructions describe the retained scripted automation route. Its custom helper is
not needed by the recommended widget/Python workflow.

## Prepare either kit

Close its editor before adding plugins. Use a separate project copy for experimentation.
No game INI changes are needed.

1. Ensure the kit opens against the exact engine build you intend to cook with. In this test,
   the base modkit's prebuilt Linux modules had an older BuildId, so its **test copy** was rebuilt
   from its own sources. Do not bypass this check by editing module BuildIds.
2. Copy **ZComAuthoring** from the creator bundle's `Plugins/ZComAuthoring` into the kit's
   `Plugins` folder. All helper source is included; no other project is needed. Enable
   `ZComAuthoring`, `PythonScriptPlugin` and `EditorScriptingUtilities` in the project descriptor
   or Plugins dialog. With the editor closed, build against that project's matching engine:

   ```sh
   /path/to/UnrealEngine/Engine/Build/BatchFiles/Linux/Build.sh \
     SWZeroCompanyEditor Linux Development \
     -Project="/path/to/kit/SWZeroCompany.uproject" -WaitMutex -NoHotReload
   ```

   The bundled module descriptor targets Linux. Windows compilation is not verified.
3. Copy the bundle's **authoring reference** `Plugins/DenDesignerGF` into the kit's `Plugins`
   folder and enable it. It contains only `BP_DenPropPack`, not the editor runtime or its
   GameFeatureData. Keep it outside `Mods` and `Plugins/GameFeatures`, and do not replace an
   existing real Den Designer plugin. **Never install or ship this reference as a runtime.**
   You do not need to build Den Designer or export anything from another kit.
4. Generate your source pack as an ordinary editor-mounted plugin:

   ```sh
   python3 tools/prop_packs/prop_pack.py path/to/pack.json \
     --output "/path/to/kit/Plugins/YourPack" --editor-mounted
   ```

   Enable `DenDesignerGF` and `YourPack` in the project. The source descriptor mounts content at
   editor startup. The packager regenerates the **shipping** descriptor as an explicitly loaded,
   active Game Feature; it does not ship the editor mounting settings.
5. Import your assets under `/YourPack/` as usual. The creator bundle's template includes no artwork.
   The local development sample has separately credited source art excluded from Git.
6. Supply `Releases/BaseGame/Windows/AssetRegistry.bin`. The base modkit includes the trimmed
   DLC registry; the tested SDK only had `AssetRegistry.bin.orig`, which is the reference catalog.
   Copy the matching **trimmed** baseline from the base modkit into the SDK project. Do not rename
   `.orig` and assume it is equivalent. The Linux helper copies the baseline into the target's
   release directory when that directory lacks it.

## Build and inspect

From the extracted creator bundle, select either project and its engine explicitly:

```sh
SWZC_KIT="/path/to/kit" SWZC_ENGINE="/path/to/UnrealEngine/Engine" \
DEN_PROP_PACK_BUILD_ROOT="$PWD/dist/prop-packs/YourPack-sdk" \
bash tools/prop_packs/build_prop_pack.sh "/path/to/kit/Plugins/YourPack"
```

For maintainers with the local sample artwork, use `DenPropsExample` and append `--sample-art`. Use separate output roots
when comparing kits. Do not author or cook the same project concurrently.

The helper supports source plugins in `Plugins`, `Plugins/GameFeatures` or `Mods`, and validates the
cooked namespace in each case. It assembles an independent runtime manifest and refuses a missing
baseline, ambiguous cook output or Blueprint compile diagnostics. The reference base, authoring
helper and unrelated game/plugin content must never appear in the pack inventory.

A fresh editor process can run `unreal/scripts/verify_prop_pack.py` with `DEN_PROP_PACK` set to the
source plugin directory. It checks saved metadata, loaded meshes/material assignments and the exact
GameState/component soft references, including client/server flags. Use the editor's Python script
runner, or the same `-run=pythonscript -script=...` commandlet route used by the build helper.

When relocating an already-built Linux project, its binary search paths may need updating. The
isolated SDK copy needed `LD_LIBRARY_PATH` to include its and the engine's `Binaries/Linux` folders.
This is a relocation issue, separate from the pack format; rebuilding at the final location is
preferable to copying arbitrary shared libraries between kits.

## Evidence and limits

Local logs and containers are under `dist/kit-verification/`, with `summary.json` recording results,
source-preservation checks and hashes. Original SDK/modkit source, project descriptors and Config
files were left unchanged. The isolated test projects are under the engine volume's
`tmp/DenPackKitVerification-20261020` directory. No game containers, loader state or campaign saves
were changed for this verification.

The test proves the three supplied static meshes and their existing-engine material instances can
be authored and packaged through both prepared kits. It does not certify all SDK proxy classes,
custom shaders, animated assets or arbitrary pack dependencies.
