# Den Designer Prop Pack Editor

Editor Utility Widget plus bundled Python for **Tools → Den Designer Prop Packs**. Create and edit
pack metadata, add selected meshes, validate, cook and export inside Unreal Editor.

Requires Unreal's Python Editor Script Plugin, Editor Scripting Utilities and the supplied minimal
DenDesignerGF reference. There is no custom native module, external Python installation or manual
script step. Unreal's own cook tools and the matching trimmed DLC baseline are still required.

See the bundle's root README or `authoring/prop-packs/EDITOR-GUIDE.md` in the repository. Replace the
whole old DenPropPackEditor directory when upgrading from the native edition. Use the Tools menu to
open the panel; its widget asset alone is an empty shell populated by Python.

Linux UE 5.6.1 is tested in both public kits. Windows execution remains unverified. Python does not
provide Windows shader cooking on Linux. Never install this authoring plugin into the game or ship
it with a prop pack.
