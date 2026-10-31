"""Menu bar, inspector and settings widgets created for real and attached to the editor host.

Headless: this checks widget state the runtime writes (labels, tints, visibility), not rendering.
"""


def run(unreal, host, get, set_, command, check):
    import ui_templates as editor
    from runtime_editor_assets import UIROOT
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    library = unreal.get_default_object(unreal.load_class(None, '/Script/UMG.WidgetBlueprintLibrary'))

    def create(name):
        return library.call_method('Create', (world, unreal.EditorAssetLibrary.load_blueprint_class(UIROOT + name), None))

    def rounded(color):
        return tuple(round(value, 3) for value in (color.r, color.g, color.b, color.a))

    active_back = tuple(round(value, 3) for value in (*editor.ACCENT, 0.16))
    accent = tuple(round(value, 3) for value in (*editor.ACCENT, 1))

    def on(toolbar, name):
        back = rounded(get(toolbar, name + 'Back').get_editor_property('brush_color'))
        icon = rounded(get(toolbar, name + 'Icon').get_editor_property('color_and_opacity'))
        label = rounded(get(toolbar, name + 'Label').get_editor_property('color_and_opacity').get_editor_property('specified_color'))
        assert (back == active_back) == (icon == accent) == (label == accent), (name, back, icon, label)
        return back == active_back

    def label(toolbar, name):
        return str(get(toolbar, name + 'Label').get_text())

    toolbar, inspector, settings = create('WBP_DenToolbar'), create('WBP_DenTransform'), create('WBP_DenSettings')
    mode = get(host, 'GizmoMode')
    try:
        set_(host, 'Toolbar', toolbar)
        set_(host, 'Inspector', inspector)
        set_(host, 'SettingsPanel', settings)
        texture = get(toolbar, 'MoveIcon').get_editor_property('brush').get_editor_property('resource_object')
        check(texture is not None and texture.get_name() == 'T_Icon_move', 'menu bar icons reference the imported textures')
        buttons = editor.LIBRARY + editor.TOOLS + editor.QUICK_CONTROLS + editor.LAYERS + [row[:4] for row in editor.HOLONET]
        check(all(get(toolbar, name + 'Back') for name, _, _, _ in buttons), 'every rail entry, tool and filter has a tintable backing')

        host.call_method('RefreshEditorUI')
        check(not on(toolbar, 'Snap') and label(toolbar, 'Snap') == 'Off' and label(toolbar, 'Reach') == '20 m',
              'grid off and the range read as short menu-bar values')
        command('snap')
        check(on(toolbar, 'Snap') and label(toolbar, 'Snap') == '5 cm', 'an active grid lights up with its step')
        for _ in range(4):
            command('snap')
        check(get(host, 'GridStep') == 0 and not on(toolbar, 'Snap'), 'turning the grid off clears its highlight')
        check(on(toolbar, 'Lock') and not on(toolbar, 'Floors') and not on(toolbar, 'Walls'),
              'selection filters show their on/off state by colour')

        visible = unreal.SlateVisibility.HIT_TEST_INVISIBLE
        joined = lambda: (get(toolbar, 'RailJoined').get_visibility() == visible, get(toolbar, 'RailAlone').get_visibility() == visible)
        command('catalog')
        check(on(toolbar, 'Catalog') and not any(on(toolbar, name) for name in ['Storeroom', 'Compositions', 'Layouts', 'RailBrowse']),
              'the open library panel lights its rail entry only')
        check(joined() == (True, False), 'the rail joins the open panel beside it')
        command('library_close')
        check(not on(toolbar, 'Catalog') and get(host, 'ActivePanel') == '', "a panel's X closes it and clears its rail entry")
        check(joined() == (False, True), 'the rail stands alone while nothing is open')

        def icon_on(name):
            back = rounded(get(toolbar, name + 'Back').get_editor_property('brush_color'))
            icon = rounded(get(toolbar, name + 'Icon').get_editor_property('color_and_opacity'))
            assert (back == active_back) == (icon == accent), (name, back, icon)
            return back == active_back

        def folded():
            shown = get(toolbar, 'RailIcons').get_visibility() != unreal.SlateVisibility.COLLAPSED
            assert shown == (get(toolbar, 'RailFrame').get_visibility() == unreal.SlateVisibility.COLLAPSED)
            return shown, get(toolbar, 'LibraryTabs').slot.get_offsets().right

        def pinned():
            return get(host, 'PreferencesDocument').call_method('ReadPreference', ('rail_labels',))[0]

        check(folded() == (False, editor.RAIL_WIDTH), 'the rail opens with labels')
        command('rail_fold')
        check(not get(host, 'RailLabels') and folded() == (True, editor.ICON_RAIL_WIDTH) and pinned() == 'false',
              'Fold to icons narrows the rail to its icons and remembers it')
        command('catalog')
        check(icon_on('IconCatalog') and not any(icon_on(editor.icon_entry(name)) for name, _, _, _ in editor.LIBRARY[1:]),
              'the folded rail lights the open entry')
        command('library_close')
        host.call_method('ReadEditorPreferences')
        host.call_method('ApplyEditorPreferences')
        check(not get(host, 'RailLabels'), 'the fold pin is read back from preferences')
        command('rail_code')
        check(get(host, 'RailLabels') and folded() == (False, editor.RAIL_WIDTH) and pinned() == 'true' and get(host, 'RailCodeFocus'),
              'the code icon shows labels and asks for the code field to take focus')
        host.call_method('PollRailCodeFocus')
        check(not get(host, 'RailCodeFocus'), 'the focus request is used once')

        command('mode_select')
        check(get(host, 'GizmoMode') == 0 and on(toolbar, 'SelectMode') and not on(toolbar, 'Move'),
              'the Select tool turns the gizmo off and lights up')
        command('mode_move')
        check(get(host, 'GizmoMode') == 1 and on(toolbar, 'Move') and not on(toolbar, 'SelectMode'), 'tools light up one at a time')

        collapsed = unreal.SlateVisibility.COLLAPSED
        set_(host, 'HasSelection', True)
        host.call_method('RefreshSelectionUI')
        shown = inspector.get_visibility() != collapsed
        command('settings')
        hidden = get(host, 'ActivePanel') == 'settings' and inspector.get_visibility() == collapsed
        command('settings')
        check(shown and hidden and inspector.get_visibility() != collapsed, 'Settings take the inspector dock while open')

        # The kit has no live cinematic subsystem: hiding the game HUD must then do nothing.
        host.call_method('HideGameHUD')
        hidden = get(host, 'HUDHidden')
        host.call_method('RestoreGameHUD')
        check(not hidden and not get(host, 'HUDHidden'), 'game HUD hiding is a no-op without the cinematic subsystem')
    finally:
        set_(host, 'HasSelection', False)
        host.call_method('SetGizmoMode', (mode,))
        for name in ['Toolbar', 'Inspector', 'SettingsPanel']:
            set_(host, name, None)
