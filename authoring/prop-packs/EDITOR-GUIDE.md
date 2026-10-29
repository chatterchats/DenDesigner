# Den Designer Prop Pack Editor

Create, edit, validate and export prop packs through **Tools → Den Designer Prop Packs** in Unreal
Editor. The panel is an Editor Utility Widget powered by bundled Python. Unreal supplies the Python
interpreter: creators need no separate Python installation, terminal commands or C++ compilation.
Players install only the finished content pack alongside Den Designer 0.9.0 or later.

This guide covers **DenDesigner-PropPack-Editor-0.2.0-preview.1.zip**. This single content/Python
bundle replaces the earlier Source and Linux binary archives. The authoring tool and game runtime
(currently **0.9.0-preview.2**) have independent versions.

## Installation

1. Close the public **SWZC SDK or base SWZC Unreal Modkit** editor. Use a kit that already opens with
   its matching Unreal Engine 5.6.1 installation. No private Merged Kit is needed.
2. Copy the archive's `Plugins/DenPropPackEditor` and `Plugins/DenDesignerGF` folders into your
   project's `Plugins` folder. When upgrading the old native tool, replace the entire
   `DenPropPackEditor` folder so its old `Binaries`, `Intermediate` and `Source` are removed.
3. Keep the minimal `DenDesignerGF` reference outside `Mods` and `Plugins/GameFeatures`. If you
   already have the full Den Designer source plugin, keep that instead of overwriting it with
   the minimal reference.
4. Open the project. Enable **Den Designer Prop Pack Editor**, **Python Editor Script Plugin** and
   **Editor Scripting Utilities** in the Plugins dialog if needed, then restart. GameFeatures,
   ModularGameplay and DenDesignerGF are also declared dependencies.
5. Open **Tools → Den Designer Prop Packs**. Use this menu to launch/populate the panel; running
   its widget asset directly opens only the empty shell.

There is no custom native module to compile or match to an engine BuildId. The kit and Unreal's
own plugins still need to be compatible with each other. The Linux workflow is verified in both
prepared public kits; Windows execution remains unverified. The same bundle contains the Windows
build path, without a separate DLL.

## Create and edit

1. Choose **New pack**. Enter a unique plugin name (`MyFurniture`), permanent lowercase pack ID
   (`my-furniture`), title, author and version. Choose **Save pack**.
   Once your pack has a Nexus Mods page, add it as **Nexus page**, for example
   `https://www.nexusmods.com/games/starwarszerocompany/mods/123`. HoloNet shows
   it on builds that use your pack. Leave it empty until then: HoloNet links to a
   Nexus search for your pack's title instead. Only Star Wars Zero Company pages on
   nexusmods.com are accepted.
2. If the panel requests a restart to mount the new content folder, restart the editor and reopen
   the pack from the dropdown. This is required when a new pack's filesystem path contains spaces.
3. Choose **Show content**. Import your static meshes, textures and materials into that pack's
   content folder using the usual Content Browser import tools.
4. Select meshes in the Content Browser and choose **Add selected meshes**. Names, dimensions and
   a collision default are filled automatically. Duplicates, non-mesh assets and assets owned by
   another plugin are skipped.
5. Edit each row's name, tags, description, dimensions in centimetres and **Solid** checkbox.
   **Remove** deletes the registration row, not the imported asset. Edit materials and collision
   geometry in Unreal's normal asset editors.
6. Choose **Save pack** to save metadata. Plugin name and pack ID stay fixed after creation.
   To reopen an existing pack, choose it in the dropdown and select **Open pack**. **Refresh**
   rescans source packs under this project's `Plugins` directory. Schema-1 packs from the older
   scripted workflow can be opened there too.

Metadata lives in the pack's `Authoring/pack.json`; you never need to edit it manually. Switching
packs asks before discarding unsaved metadata. Saving metadata leaves unrelated assets alone;
building saves assets belonging to the pack. Closing/reopening the panel in the same editor session
preserves its form and active build. Save before closing the editor itself.

## Validate and build

**Validate** checks metadata, unique mesh paths, dimensions, material slots and package dependencies.
It warns when a prop marked solid lacks simple collision. Fix missing references and dependencies
in unrelated plugins before building. A pack may use its own assets and existing game/engine assets;
custom dependencies belonging to another plugin must be moved into the pack.

**Build pack** generates the provider Blueprint and GameFeatureData, saves this pack's assets and
runs Unreal's cook/package tools in a background process. The editor remains usable; the pack form
is locked until the task finishes. Use **Open build logs** to inspect `cook.log`, `container-list.log`
and `pak.log`. Completion or failure appears in the panel; **Open export folder** becomes available
on success. A namespace audit rejects unrelated cooked assets and missing registered meshes.

Unique builds are kept below `Saved/DenPropPackEditor/Builds/<PluginName>/<BuildID>/` in the project.
Each successful `Export` contains:

```text
Content/Paks/~mods/MyFurniture_P.pak
Content/Paks/~mods/MyFurniture_P.ucas
Content/Paks/~mods/MyFurniture_P.utoc
README.txt
```

The shipping manifest has runtime Game Feature activation settings, independently of editor mounting.
Nothing is automatically installed into the game. Failed jobs retain their logs and incomplete work,
but publish no `Export` folder. Previous successful exports are kept.

Distribute the three matching containers with your artwork credits. Do not ship the authoring plugin,
its Python files, or the minimal DenDesignerGF reference.

## Updating a pack

Open its source pack from the dropdown, edit metadata or assets, and build again. Keep plugin name,
pack ID and existing mesh paths stable: layouts and compositions refer to those paths. Back up the
source plugin's `Authoring` and `Content` folders. A cooked export is not an editable source backup.

Close the game before replacing all three containers with files from the same successful export.
Restart to discover changes. If a mesh changes at the same path, its cached PNG under
`Saved/ZComDen/thumbs` may need removal to regenerate the preview. Test existing layouts as well as
new placements before publishing an update.

## Cooking requirements

Cooking needs the matching trimmed `Releases/BaseGame/<Platform>/AssetRegistry.bin`. The tested
SDK needs that baseline from the matching base modkit. `.bin.orig` is not a substitute. When the Linux
baseline is absent, the tool copies the existing trimmed Windows baseline within the project.
No game INI or game registry is edited.

The target follows the host editor: Windows on Windows, Linux on Linux. Python removes the custom
plugin compilation requirement; it does **not** add Windows shader cooking to a Linux editor.
Custom Windows material shaders still need a Windows cook. Existing engine material parents worked
in the earlier sample, but every new export needs an in-game check for discovery, thumbnails,
materials, placement and layout reload before distribution.

Windows batch tooling currently rejects project/engine paths containing shell expansion characters
such as `%`, `!`, `&` or `^`; ordinary spaces are supported for builds of mounted packs.

## Troubleshooting

- **Tools entry missing:** enable Python Editor Script Plugin, Editor Scripting Utilities and
  DenPropPackEditor, then restart. Check the Output Log for Python initialization errors.
- **Old module compatibility warning:** remove the old DenPropPackEditor folder and install the
  complete 0.2 bundle. This edition declares no custom native module. Other kit modules still need
  their own matching engine build.
- **Blank restored panel:** reopen it through **Tools → Den Designer Prop Packs**.
- **Pack missing from dropdown:** its source plugin must be directly under this project's `Plugins`
  directory and contain `Authoring/pack.json`. Choose Refresh; cooked exports cannot be edited.
- **Restart requested:** save the new pack, restart once, then choose it from the dropdown. Its source
  plugin is enabled in the project descriptor so the content mounts on startup.
- **Foreign dependency or missing material:** import the needed custom assets into the pack and
  repair references in the normal asset editors.
- **Missing baseline:** supply the matching trimmed registry described above. Renaming `.orig`
  does not create a valid baseline.
- **Build failed:** inspect the panel message and Open build logs, correct the issue and retry.
  Use a successful `Export`, never an incomplete build directory.

The [compatibility report](https://github.com/chatterchats/DenDesigner/blob/main/authoring/prop-packs/kit-compatibility.md) in the repository records checks and limitations.
The older [scripted authoring route](https://github.com/chatterchats/DenDesigner/blob/main/authoring/prop-packs/SCRIPTED-AUTHORING.md) remains available separately for
maintainer automation. It is not called by this panel. Sample artwork is excluded from the bundle.
