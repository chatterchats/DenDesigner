"""Maintainer-only generation of the stock Editor Utility Widget shell; no native helper."""
import unreal as u

u.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous(['/DenPropPackEditor'],True)
settings=u.get_default_object(u.load_class(None,'/Script/Blutility.EditorUtilityWidgetProjectSettings'))
previous=settings.get_editor_property('bUseWidgetTemplateSelector')
settings.set_editor_property('bUseWidgetTemplateSelector',False)
try:
    path='/DenPropPackEditor/UI/EUW_PropPacks'
    bp=u.load_object(None,path+'.EUW_PropPacks') if u.EditorAssetLibrary.does_asset_exist(path) else None
    if bp is None:
        bp=u.AssetToolsHelpers.get_asset_tools().create_asset('EUW_PropPacks','/DenPropPackEditor/UI',u.EditorUtilityWidgetBlueprint,u.EditorUtilityWidgetBlueprintFactory())
finally:
    settings.set_editor_property('bUseWidgetTemplateSelector',previous)
u.BlueprintEditorLibrary.compile_blueprint(bp)
u.get_default_object(bp.generated_class()).set_editor_property('TabDisplayName','Den Designer Prop Packs')
assert u.EditorAssetLibrary.save_loaded_asset(bp,False)
u.log('DENPACK_PANEL_ASSET ok')
