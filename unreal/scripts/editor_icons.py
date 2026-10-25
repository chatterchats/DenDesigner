"""Import the editor UI's icon textures (rendered by tools/build/render_icons.sh) before the widgets that use them."""
import os
from pathlib import Path

import unreal

ICONS = "/DenDesignerGF/Editor/Icons"


def import_icons():
    tasks = []
    for png in sorted(Path(os.environ["DENDESIGNERGF_ICONS"]).glob("*.png")):
        task = unreal.AssetImportTask()
        for key, value in (("filename", str(png)), ("destination_path", ICONS), ("destination_name", "T_Icon_" + png.stem),
                           ("automated", True), ("replace_existing", True), ("save", False)):
            task.set_editor_property(key, value)
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    for task in tasks:
        paths = task.get_editor_property("imported_object_paths")
        texture = unreal.load_asset(paths[0]) if paths else None
        if not isinstance(texture, unreal.Texture2D):
            unreal.log_error(f"DENDESIGNERGF icon import failed: {task.get_editor_property('filename')}")
            return False
        for key, value in (("compression_settings", unreal.TextureCompressionSettings.TC_EDITOR_ICON),
                           ("lod_group", unreal.TextureGroup.TEXTUREGROUP_UI),
                           ("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_SIMPLE_AVERAGE),
                           ("srgb", True), ("never_stream", True)):
            texture.set_editor_property(key, value)
        unreal.EditorAssetLibrary.save_loaded_asset(texture, only_if_is_dirty=False)
    unreal.log(f"DENDESIGNERGF icons {len(tasks)}")
    return bool(tasks)
