"""Author one independent pack's registration BP and Game Feature data, in the kit only."""
import json
import os
from pathlib import Path
import unreal
import zcom_authoring

folder=Path(os.environ['DEN_PROP_PACK'])
doc=json.loads((folder/'Authoring/pack.json').read_text());name=doc['plugin']
unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous(["/DenDesignerGF", "/"+name], True)
lib=unreal.EditorAssetLibrary
if os.environ.get('DEN_PROP_PACK_SOURCE'):
    assert name=='DenPropsExample'
    import sys
    sys.path.insert(0,str(Path(__file__).parent))
    from import_prop_pack_sample import run
    run()
ok=zcom_authoring.build([folder/'Authoring/provider.json'])
if ok:
    for e in doc['props']:
        asset=lib.load_asset(e['mesh'])
        if not isinstance(asset,unreal.StaticMesh):
            unreal.log_error('DENPACK missing or non-static mesh: '+e['mesh']);ok=False
if ok:
    path=f'/{name}/{name}'
    data=lib.load_asset(path) if lib.does_asset_exist(path) else None
    if data is None:
        factory=unreal.DataAssetFactory();factory.set_editor_property('data_asset_class',unreal.GameFeatureData)
        data=unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,'/'+name,unreal.GameFeatureData,factory)
    action=unreal.find_object(data,'RegisterPropPack') or unreal.new_object(unreal.load_class(None,'/Script/GameFeatures.GameFeatureAction_AddComponents'),outer=data,name='RegisterPropPack')
    for obj,field,value in [(action,'ComponentList',f'((ActorClass="/Script/BitReactorGame.BitReactorGameState",ComponentClass="/{name}/BP_PropPack.BP_PropPack_C",bClientComponent=True,bServerComponent=True))'),(data,'Actions',f'("{action.get_path_name()}")')]:
        error=unreal.ZComAuthoringLibrary.set_property_from_text(obj,field,value)
        if error:unreal.log_error(error);ok=False
    lib.save_loaded_asset(data,only_if_is_dirty=False)
unreal.log('DENPACK_RESULT '+('ok' if ok else 'failed'))
