"""Unreal's built-in Python API is the only editor bridge used by this tool."""
from pathlib import Path
import copy
import json
import os
import shutil
import subprocess
import sys
import uuid
import unreal as u
from . import model

BASE = '/DenDesignerGF/Runtime/BP_DenPropPack.BP_DenPropPack_C'


def project_dir():
    return Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).resolve()


def scan(name):
    u.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous(['/'+name, '/DenDesignerGF'], True)


_live_mounts = set()


def mount(doc, folder):
    name=doc['plugin']
    existing=u.PluginBlueprintLibrary.get_plugin_base_dir(name)
    if existing:
        model.require(Path(u.Paths.convert_relative_path_to_full(existing)).resolve()==folder.resolve(),
                      'Another installed plugin owns this name.')
    project=Path(u.Paths.convert_relative_path_to_full(u.Paths.get_project_file_path()))
    state=json.loads(project.read_text(encoding='utf-8-sig'))
    plugins=state.setdefault('Plugins',[])
    item=next((p for p in plugins if p['Name']==name),None)
    if item is None:
        plugins.append({'Name':name,'Enabled':True});model.atomic_json(project,state)
    elif not item.get('Enabled',False):
        item['Enabled']=True;model.atomic_json(project,state)
    if name in _live_mounts or u.PluginBlueprintLibrary.is_plugin_mounted(name):
        scan(name);return True
    content=os.path.relpath(folder/'Content',u.Paths.convert_relative_path_to_full('.')).replace('\\','/')+'/'
    # Unreal's console mount command does not parse quoted arguments. A new
    # plugin in a path containing whitespace mounts normally on the next launch.
    if any(c.isspace() or c=='"' for c in content):return False
    u.SystemLibrary.execute_console_command(None,f'PackageName.RegisterMountPoint /{name}/ {content}')
    _live_mounts.add(name);scan(name)
    return True


def require_mount(doc,folder):
    model.require(mount(doc,folder),'Pack saved. Restart the editor once to mount this new plugin, then reopen it from the pack list.')


def save(doc, previous=None):
    model.validate(doc, allow_empty=True)
    existing = u.PluginBlueprintLibrary.get_plugin_base_dir(doc['plugin'])
    if existing and previous is None:
        raise ValueError('That plugin name is already installed. Open its pack instead.')
    folder = model.save(project_dir(), doc, previous)
    mount(doc, folder)
    return folder


def open_pack(name):
    folder = model.owned_folder(project_dir(), name)
    doc = model.read(folder)
    model.require(doc['plugin']==name, 'Pack metadata does not match its folder')
    mount(doc, folder)
    return doc, folder


def list_packs():
    return sorted(p.parent.parent.name for p in (project_dir()/'Plugins').glob('*/Authoring/pack.json'))


def add_meshes(doc, assets=None):
    model.require(bool(doc['plugin']), 'Save the new pack first')
    assets = u.EditorUtilityLibrary.get_selected_assets() if assets is None else assets
    seen = {p['mesh'].casefold() for p in doc['props']}
    added = skipped = 0
    sm = (u.get_editor_subsystem(u.StaticMeshEditorSubsystem) or u.get_default_object(u.StaticMeshEditorSubsystem))
    for mesh in assets:
        path = mesh.get_path_name()
        if (not isinstance(mesh,u.StaticMesh) or not path.startswith('/'+doc['plugin']+'/') or
                path.casefold() in seen or len(doc['props'])>=2048):
            skipped += 1
            continue
        bounds = mesh.get_bounds().box_extent
        doc['props'].append(dict(mesh=path, name=mesh.get_name().removeprefix('SM_'), description='', tags='',
                                 size=[bounds.x*2,bounds.y*2,bounds.z*2], collision=sm.get_simple_collision_count(mesh)>0))
        seen.add(path.casefold())
        added += 1
    return added, skipped


def validate(doc):
    model.validate(doc)
    registry = u.AssetRegistryHelpers.get_asset_registry()
    options = u.AssetRegistryDependencyOptions(include_soft_package_references=True, include_hard_package_references=True)
    warnings = []
    for prop in doc['props']:
        mesh = u.load_asset(prop['mesh'])
        model.require(isinstance(mesh,u.StaticMesh), 'Cannot load mesh: '+prop['mesh'])
        slots = mesh.get_editor_property('static_materials')
        model.require(bool(slots) and all(s.material_interface for s in slots), 'Missing material slot: '+prop['name'])
        if prop['collision'] and (u.get_editor_subsystem(u.StaticMeshEditorSubsystem) or u.get_default_object(u.StaticMeshEditorSubsystem)).get_simple_collision_count(mesh)==0:
            warnings.append(prop['name']+': marked solid but has no simple collision; check collision settings.')
        queue = [prop['mesh'].split('.',1)[0]]
        visited = set()
        while queue:
            current = queue.pop()
            if current in visited: continue
            visited.add(current)
            for dependency in registry.get_dependencies(current, options) or []:
                dep = str(dependency)
                if dep.startswith('/'+doc['plugin']+'/'): queue.append(dep)
                else: model.require(dep.startswith(('/Engine/','/Game/','/Script/')), 'Move external dependency into this pack: '+dep)
    return warnings


def author(doc, folder):
    validate(doc)
    require_mount(doc, folder)
    tools = u.AssetToolsHelpers.get_asset_tools()
    lib = u.EditorAssetLibrary
    name = doc['plugin']
    parent = u.load_class(None, BASE)
    model.require(parent is not None, 'Enable the DenDesignerGF authoring reference')
    path = '/'+name+'/BP_PropPack'
    bp = u.load_object(None,path+'.BP_PropPack') if lib.does_asset_exist(path) else None
    if bp is None:
        factory = u.BlueprintFactory()
        factory.set_editor_property('parent_class',parent)
        bp = tools.create_asset('BP_PropPack','/'+name,u.Blueprint,factory)
    model.require(isinstance(bp,u.Blueprint), 'Provider path is occupied by another asset')
    model.require(u.MathLibrary.class_is_child_of(bp.generated_class(),parent), 'Provider has the wrong parent')
    u.BlueprintEditorLibrary.compile_blueprint(bp)
    cdo = u.get_default_object(bp.generated_class())
    values = dict(SchemaVersion=1,PackID=doc['id'],Title=doc['title'],Author=doc['author'],Version=doc['version'])
    values.update(Paths=[p['mesh'] for p in doc['props']],Labels=[p['name'] for p in doc['props']],
                  Dimensions=[u.Vector(*p['size']) for p in doc['props']],Solid=[p['collision'] for p in doc['props']],
                  SearchTexts=[p.get('tags','') for p in doc['props']],
                  Details=[(p.get('description','')+'\n' if p.get('description') else '')+
                           ' × '.join(f'{v:g}' for v in p['size'])+' cm'+('' if p['collision'] else '\nNo collision') for p in doc['props']])
    for key,value in values.items(): cdo.set_editor_property(key,value)
    model.require(lib.save_loaded_asset(bp,only_if_is_dirty=False), 'Could not save provider Blueprint')
    path = f'/{name}/{name}'
    data = u.load_object(None,path+'.'+name) if lib.does_asset_exist(path) else None
    if data is None:
        factory = u.DataAssetFactory()
        factory.set_editor_property('data_asset_class',u.GameFeatureData)
        data = tools.create_asset(name,'/'+name,u.GameFeatureData,factory)
    model.require(isinstance(data,u.GameFeatureData), 'Registration path is occupied by another asset')
    action_class = u.load_class(None,'/Script/GameFeatures.GameFeatureAction_AddComponents')
    action = u.find_object(data,'RegisterPropPack') or u.new_object(action_class,outer=data,name='RegisterPropPack')
    model.require(action.get_class()==action_class, 'Registration action name is occupied by another type')
    # This non-BlueprintType engine struct has no named Python wrapper. Resizing
    # the reflected array gives a correctly typed entry; built-in import_text
    # preserves unresolved soft paths even in the base kit without game classes.
    entries = action.get_editor_property('ComponentList')
    entries.resize(1)
    entry = entries[0]
    model.require(entry.import_text(f'(ActorClass="/Script/BitReactorGame.BitReactorGameState",ComponentClass="/{name}/BP_PropPack.BP_PropPack_C",bClientComponent=True,bServerComponent=True)'), 'Cannot set registration')
    entries[0]=entry
    action.set_editor_property('ComponentList',entries)
    data.set_editor_property('Actions',[action])
    model.require(lib.save_loaded_asset(data,only_if_is_dirty=False), 'Cannot save GameFeatureData')
    model.require(lib.save_directory('/'+name,only_if_is_dirty=True,recursive=True), 'Cannot save this pack\'s assets')
    return bp, data


def verify_registration(doc):
    name = doc['plugin']
    scan(name)
    bp = u.load_object(None,f'/{name}/BP_PropPack.BP_PropPack')
    cdo = u.get_default_object(bp.generated_class())
    for key,expected in dict(SchemaVersion=1,PackID=doc['id'],Title=doc['title'],Author=doc['author'],Version=doc['version']).items():
        model.require(cdo.get_editor_property(key)==expected, 'Provider field did not persist: '+key)
    arrays=dict(Paths=[p['mesh'] for p in doc['props']],Labels=[p['name'] for p in doc['props']],
                SearchTexts=[p.get('tags','') for p in doc['props']],Solid=[p['collision'] for p in doc['props']],
                Details=[(p.get('description','')+'\n' if p.get('description') else '')+
                         ' × '.join(f'{v:g}' for v in p['size'])+' cm'+('' if p['collision'] else '\nNo collision') for p in doc['props']])
    for key,expected in arrays.items():
        model.require(list(cdo.get_editor_property(key))==expected, 'Provider array did not persist: '+key)
    dimensions=list(cdo.get_editor_property('Dimensions'))
    model.require(len(dimensions)==len(doc['props']), 'Provider dimensions have the wrong length')
    for actual,prop in zip(dimensions,doc['props']):
        model.require(all(abs(a-b)<0.01 for a,b in zip((actual.x,actual.y,actual.z),prop['size'])), 'Provider dimensions did not persist')
    data = u.load_object(None,f'/{name}/{name}.{name}')
    text = data.get_editor_property('Actions')[0].get_editor_property('ComponentList')[0].export_text()
    for required in ('/Script/BitReactorGame.BitReactorGameState',f'/{name}/BP_PropPack.BP_PropPack_C','bClientComponent=True','bServerComponent=True'):
        model.require(required in text, 'Registration did not persist: '+required)
    return True


def prepare_build(doc, folder):
    """Only call on the editor thread. Returned job contains no UObject references."""
    save(doc, folder)
    author(doc, folder)
    verify_registration(doc)
    project = project_dir()
    platform = 'Windows' if sys.platform=='win32' else 'Linux'
    baseline = project/'Releases/BaseGame'/platform/'AssetRegistry.bin'
    if not baseline.exists():
        source = project/'Releases/BaseGame/Windows/AssetRegistry.bin'
        model.require(source.is_file(), 'Missing trimmed BaseGame AssetRegistry.bin; install the matching base-modkit release registry. .bin.orig is not a substitute.')
        baseline.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,baseline)
    output = project/'Saved/DenPropPackEditor/Builds'/doc['plugin']/uuid.uuid4().hex
    output.mkdir(parents=True)
    engine = Path(u.Paths.convert_relative_path_to_full(u.Paths.engine_dir())).resolve()
    return dict(doc=copy.deepcopy(doc),folder=str(folder),project=str(Path(u.Paths.convert_relative_path_to_full(u.Paths.get_project_file_path()))),
                output=str(output),engine=str(engine),platform=platform)


def run_tool(args, log, env=None):
    with Path(log).open('w',encoding='utf-8') as stream:
        result = subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT, env=env,
                                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
    model.require(result.returncode==0, f'Build tool failed ({result.returncode}). See {log}')


def build(job):
    """Worker thread: filesystem and child processes only, never Unreal objects."""
    doc = job['doc']; name=doc['plugin']; platform=job['platform']
    folder=Path(job['folder']); engine=Path(job['engine']); output=Path(job['output'])
    args=[f'-ScriptsForProject={job["project"]}', 'BuildCookRun', f'-project={job["project"]}', '-nop4','-utf8output',
          '-unattended','-nocompileeditor','-skipbuildeditor','-platform='+('Win64' if platform=='Windows' else 'Linux'),
          '-clientconfig=Shipping','-cook','-stage','-pak','-iostore','-dlcname='+name,'-DLCPakPluginFile',
          '-basedonreleaseversion=BaseGame','-AdditionalCookerOptions=-AllowUncookedAssetReferences -DisablePython',
          '-archive','-archivedirectory='+str(output)]
    batch=engine/'Build/BatchFiles'/('RunUAT.bat' if platform=='Windows' else 'RunUAT.sh')
    if platform=='Windows':
        # A batch file needs cmd. Refuse shell expansion characters in user paths
        # rather than letting project metadata become shell syntax.
        model.require(not any(c in str(batch)+job['project']+str(output) for c in '%!\r\n"&|<>^'), 'Project paths contain characters unsupported by Windows batch tools')
        wrapper=output/'run-cook.cmd'
        wrapper.write_text('@echo off\ncall '+ ' '.join('"'+arg+'"' for arg in [str(batch),*args])+'\nexit /b %errorlevel%\n',encoding='utf-8')
        command=['cmd.exe','/d','/c',str(wrapper)]
    else: command=[str(batch),*args]
    env=os.environ.copy();env['NuGetAudit']='false'
    run_tool(command,output/'cook.log',env)
    containers=list(output.rglob(name+'SWZeroCompany-'+platform+'.utoc'))
    registries=list((folder/'Saved/Cooked'/platform).rglob('AssetRegistry.bin'))
    model.require(len(containers)==1 and len(registries)==1, 'Missing or ambiguous cooked container/registry')
    pak=engine/'Binaries'/('Win64/UnrealPak.exe' if platform=='Windows' else 'Linux/UnrealPak')
    run_tool([str(pak),str(containers[0]),'-List'],output/'container-list.log')
    model.inventory((output/'container-list.log').read_text(encoding='utf-8',errors='replace'),doc)
    work=output/'Manifest';work.mkdir()
    descriptor=model.descriptor(doc,shipping=True)
    model.atomic_json(work/(name+'.uplugin'),descriptor)
    mount=f'../../../SWZeroCompany/Plugins/GameFeatures/{name}'
    model.atomic_json(work/(name+'.upluginmanifest'),{'Contents':[{'File':f'{mount}/{name}.uplugin','Descriptor':descriptor}]})
    lines=[(work/(name+'.upluginmanifest'),f'../../../SWZeroCompany/Plugins/{name}.upluginmanifest'),
           (work/(name+'.uplugin'),f'{mount}/{name}.uplugin'),(registries[0],mount+'/AssetRegistry.bin')]
    response=work/'pak.txt';response.write_text(''.join(f'"{a}" "{b}" -compress\n' for a,b in lines),encoding='utf-8')
    pending=output/'Export.pending';target=pending/'Content/Paks/~mods';target.mkdir(parents=True)
    for ext in ('utoc','ucas'): shutil.copy2(containers[0].with_suffix('.'+ext),target/(name+'_P.'+ext))
    run_tool([str(pak),str(target/(name+'_P.pak')),'-create='+str(response),'-platform='+platform,
              '-compressionformats=Oodle','-compresslevel=4','-compressmethod=Kraken'],output/'pak.log')
    (pending/'README.txt').write_text(f'Den Designer prop pack: {doc["title"]}\nRequires Den Designer 0.9.0 or later. Close the game, then copy Content into SWZeroCompany. Keep all three containers together. Test in game before sharing.\n',encoding='utf-8')
    model.atomic_json(target/(name+'.pack.json'),model.sharing_manifest(doc))
    pending.rename(output/'Export')
    return str(output/'Export')
