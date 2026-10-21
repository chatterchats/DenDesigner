"""Reload and verify a saved prop pack in a fresh editor process (DEN_PROP_PACK)."""
import json
import os
from pathlib import Path
import unreal

folder=Path(os.environ['DEN_PROP_PACK']);doc=json.loads((folder/'Authoring/pack.json').read_text());name=doc['plugin']
unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous(['/DenDesignerGF','/'+name],True)
lib=unreal.EditorAssetLibrary
klass=lib.load_blueprint_class(f'/{name}/BP_PropPack');assert klass is not None
cdo=unreal.get_default_object(klass)
assert cdo.get_editor_property('SchemaVersion')==doc['schema']
for field,key in [('PackID','id'),('Title','title'),('Author','author'),('Version','version')]:
    assert cdo.get_editor_property(field)==doc[key],field
assert list(cdo.get_editor_property('Paths'))==[e['mesh'] for e in doc['props']]
assert list(cdo.get_editor_property('Labels'))==[e['name'] for e in doc['props']]
assert list(cdo.get_editor_property('Solid'))==[e['collision'] for e in doc['props']]
for size,e in zip(cdo.get_editor_property('Dimensions'),doc['props']):
    assert all(abs(a-b)<.001 for a,b in zip((size.x,size.y,size.z),e['size']))
for e in doc['props']:
    mesh=lib.load_asset(e['mesh']);assert isinstance(mesh,unreal.StaticMesh),e['mesh']
    slots=mesh.get_editor_property('static_materials')
    assert slots and all(s.material_interface is not None for s in slots),e['mesh']
feature=lib.load_asset(f'/{name}/{name}');actions=feature.get_editor_property('Actions');assert len(actions)==1
action=actions[0];assert action.get_class().get_path_name()=='/Script/GameFeatures.GameFeatureAction_AddComponents'
entries=action.get_editor_property('ComponentList');assert len(entries)==1
entry=entries[0].export_text()
for expected in ['ActorClass="/Script/BitReactorGame.BitReactorGameState"',f'ComponentClass="/{name}/BP_PropPack.BP_PropPack_C"','bClientComponent=True','bServerComponent=True']:
    assert expected in entry,(expected,entry)
unreal.log('DENPACK_VERIFY '+json.dumps({'pack_id':doc['id'],'props':len(doc['props']),'registration':entry,'materials_assigned':True}))
unreal.log('DENPACK_VERIFY_RESULT ok')
