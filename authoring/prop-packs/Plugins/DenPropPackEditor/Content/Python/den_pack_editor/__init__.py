"""Den Designer's editor-only prop pack tool. No custom native module."""

def open_panel():
    from .panel import open_panel as open_impl
    return open_impl()


def register_menu():
    import unreal as u
    if '-run=' in u.SystemLibrary.get_command_line().lower():return
    menus=u.ToolMenus.get()
    menu=menus.extend_menu('LevelEditor.MainMenu.Tools')
    entry=u.ToolMenuEntry(name='DenDesigner.PropPacks',type=u.MultiBlockType.MENU_ENTRY)
    entry.set_label('Den Designer Prop Packs')
    entry.set_tool_tip('Create, validate and export prop packs inside Unreal Editor.')
    entry.set_string_command(u.ToolMenuStringCommandType.PYTHON,'','import den_pack_editor; den_pack_editor.open_panel()')
    menu.add_menu_entry('DenDesigner',entry)
    menus.refresh_all_widgets()
