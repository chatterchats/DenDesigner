"""Run only in isolated public-kit copies; creates a DenPythonTest pack from an engine cube."""
import unreal as u
from pathlib import Path
import sys,traceback
import os,time,json
from den_pack_editor import model,service
from den_pack_editor.panel import Panel
assert not hasattr(u,'DenPropPackDefinition') and not hasattr(u,'ZComAuthoringLibrary')
u.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous(['/DenPropPackEditor','/DenDesignerGF'],True)
bp=u.load_object(None,'/DenPropPackEditor/UI/EUW_PropPacks.EUW_PropPacks')
assert bp
u.log('DENPY_ASSET_READY')
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
widget=u.get_default_object(u.load_class(None,'/Script/UMG.WidgetBlueprintLibrary')).call_method('Create',(world,bp.generated_class(),None))
panel=Panel(widget)
mode=os.environ.get('DENPACK_EDITOR_TEST_MODE','smoke')
if mode=='verify':
    doc,folder=service.open_pack('DenPythonTest')
    assert service.verify_registration(doc)
    u.log('DENPACK_PYTHON_VERIFY ok')
else:
    u.log('DENPY_PANEL_READY')
    for name,value in dict(plugin='DenPythonTest',id='den-python-test',title='Python test',author='Test',version='1.0.0').items():panel.fields[name].set_text(value)
    if service.model.owned_folder(service.project_dir(),'DenPythonTest').exists():
     doc,folder=service.open_pack('DenPythonTest');panel.doc=doc;panel.folder=folder;panel.render()
    panel.save_pack()
    u.log('DENPY_SAVE_OK')
    meshpath='/DenPythonTest/SM_Cube'
    mesh=u.load_object(None,meshpath+'.SM_Cube')
    if mesh is None:mesh=u.EditorAssetLibrary.duplicate_asset('/Engine/BasicShapes/Cube',meshpath)
    assert mesh
    assert service.add_meshes(panel.doc,[mesh])[0] in (0,1)
    panel.render();panel.save_pack()
    assert panel.collect()['props'][0]['mesh']==meshpath+'.SM_Cube'
    service.author(panel.doc,panel.folder)
    assert service.verify_registration(panel.doc)
    panel.validate_pack()
    # Drive the actual button delegate, then inspect the result through the panel.
    panel.buttons[3].on_clicked.broadcast()
    assert model.read(panel.folder)==panel.collect()
    if mode=='build':
        panel.start_build()
        assert panel.future is not None
        deadline=time.monotonic()+900
        while not panel.future.done() and time.monotonic()<deadline:time.sleep(.5)
        assert panel.future.done(),'Cook timed out'
        panel.poll_build(0)
        assert panel.output, str(panel.status.get_text())
        export=Path(panel.output)
        assert len(list((export/'Content/Paks/~mods').glob('DenPythonTest_P.*')))==3
        (service.project_dir()/'Saved/DenPropPackEditor/python-test-result.json').write_text(json.dumps({'ok':True,'export':str(export),'status':str(panel.status.get_text()),'native_helpers':False},indent=2))
        u.log('DENPACK_PYTHON_BUILD ok '+str(export))
    u.log('DENPACK_PYTHON_SMOKE ok')
