"""Import the credited cabinet/pumpkin sample into its own plugin; no game assets are copied."""
import json
import os
from pathlib import Path
import unreal


def run():
    source=Path(os.environ['DEN_PROP_PACK_SOURCE']);items=json.loads((source/'materials.json').read_text())
    lib=unreal.EditorAssetLibrary;assets=unreal.AssetToolsHelpers.get_asset_tools()
    def imported(filename,folder,name,options=None):
        task=unreal.AssetImportTask();task.filename=str(filename);task.destination_path=folder;task.destination_name=name
        task.automated=True;task.replace_existing=True;task.save=True
        if options:task.options=options
        assets.import_asset_tasks([task]);obj=lib.load_asset(folder+'/'+name)
        assert obj is not None,(filename,task.imported_object_paths)
        return obj
    textures={}
    for filename in sorted({s['texture'] for m in items for s in m['sections'] if s.get('texture')}):
        texture=imported(source/filename,'/DenPropsExample/Art','T_'+Path(filename).stem)
        texture.set_editor_property('compression_settings',unreal.TextureCompressionSettings.TC_EDITOR_ICON)
        texture.set_editor_property('mip_gen_settings',unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        texture.set_editor_property('never_stream',True);texture.set_editor_property('srgb',True)
        lib.save_loaded_asset(texture,only_if_is_dirty=False);textures[filename]=texture
    for item in items:
        options=unreal.FbxImportUI();options.import_mesh=True;options.import_materials=False;options.import_textures=False;options.import_as_skeletal=False
        options.mesh_type_to_import=unreal.FBXImportType.FBXIT_STATIC_MESH;options.automated_import_should_detect_type=False
        options.static_mesh_import_data.normal_import_method=unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS
        options.static_mesh_import_data.combine_meshes=True;options.static_mesh_import_data.auto_generate_collision=True
        mesh=imported(source/(item['name']+'.fbx'),'/DenPropsExample/Props',item['name'],options)
        settings=mesh.get_editor_property('nanite_settings');settings.enabled=False;mesh.set_editor_property('nanite_settings',settings)
        slots=mesh.get_editor_property('static_materials')
        assert len(slots)==len(item['sections']), (item['name'],len(slots))
        # Use material instances of shaders already shipped by the game; no custom shader compilation.
        for i,s in enumerate(item['sections']):
            if s.get('texture'):
                assert str(slots[i].material_slot_name)==s['name'], (item['name'],i,slots[i].material_slot_name,s['name'])
            name='MI_'+item['name'].removeprefix('SM_')+'_'+str(i);path='/DenPropsExample/Art/'+name
            material=lib.load_asset(path) if lib.does_asset_exist(path) else assets.create_asset(name,'/DenPropsExample/Art',unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
            if s.get('texture'):
                # Cabinet surfaces must write depth: the translucent widget parent
                # draws its front and controls through the solid side panels.
                parent=lib.load_asset('/Engine/EngineMaterials/Widget3DPassThrough_Opaque')
                parameter='SlateUI';texture=textures[s['texture']]
                assignments={'TextureParameterValues':f'((ParameterInfo=(Name="{parameter}"),ParameterValue="{texture.get_path_name()}"))',
                    'ScalarParameterValues':'((ParameterInfo=(Name="OpacityFromTexture"),ParameterValue=1))',
                    'VectorParameterValues':'((ParameterInfo=(Name="TintColorAndOpacity"),ParameterValue=(R=1,G=1,B=1,A=1)))'}
            else:
                parent=lib.load_asset('/Engine/BasicShapes/BasicShapeMaterial');r,g,b,a=s['color']
                assignments={'VectorParameterValues':f'((ParameterInfo=(Name="Color"),ParameterValue=(R={r},G={g},B={b},A={a})))'}
            assert parent is not None
            material.set_editor_property('parent',parent)
            for key,value in assignments.items():
                error=unreal.ZComAuthoringLibrary.set_property_from_text(material,key,value)
                assert not error,error
            lib.save_loaded_asset(material,only_if_is_dirty=False)
            mesh.set_material(i,material)
        lib.save_loaded_asset(mesh,only_if_is_dirty=False)
        unreal.log('DENPACK_MESH '+item['name']+' '+str(mesh.get_bounds().box_extent))
