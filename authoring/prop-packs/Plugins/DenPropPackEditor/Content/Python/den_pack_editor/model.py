"""Platform-independent schema validation for the in-editor authoring tool."""
import copy
import json
import math
from pathlib import Path
import re
import os

BASE='/DenDesignerGF/Runtime/BP_DenPropPack'
IDENT=re.compile(r'[A-Za-z][A-Za-z0-9_]{2,63}\Z')
PACKID=re.compile(r'[a-z][a-z0-9_-]{2,95}\Z')
ASSET=re.compile(r'/[A-Za-z0-9_]+/(?:[A-Za-z0-9_-]+/)*([A-Za-z0-9_-]+)\.\1\Z')


def require(ok,message):
    if not ok:raise ValueError(message)


def label(value,name,maximum=96,required=True):
    require(isinstance(value,str),name+' must be text')
    require(value==value.strip() and (bool(value) or not required) and len(value)<=maximum,name+' is empty, padded or too long')
    require(all(ord(c)>=32 for c in value),name+' contains control characters')
    return value

# A pack's Nexus Mods page. HoloNet uses it only if it is an HTTPS Nexus Mods
# page for Star Wars Zero Company; otherwise it links to a Nexus search for the
# pack's title. Checked here so authors find out before they publish.
NEXUS=re.compile(r'https://www\.nexusmods\.com/(?:games/)?starwarszerocompany/mods/[0-9]+/?\Z')
NEXUS_SEARCH='https://www.nexusmods.com/games/starwarszerocompany/mods?title='


def nexus_url(doc):
    value=doc.get('nexus_url','')
    require(isinstance(value,str) and (value=='' or NEXUS.fullmatch(value)),
            'nexus_url must be your pack\'s Nexus Mods page for Star Wars Zero Company, like '
            'https://www.nexusmods.com/games/starwarszerocompany/mods/123. Leave it empty and '
            'HoloNet links to a Nexus search for the pack title instead.')
    return value


def nexus_link(doc):
    """The link HoloNet shows for this pack."""
    from urllib.parse import quote
    return nexus_url(doc) or NEXUS_SEARCH+quote(doc['title'],safe='')


def validate(doc, allow_empty=False):
    require(isinstance(doc,dict),'Manifest must be an object')
    require(type(doc.get('schema')) is int and doc['schema']==1,'Supported schema is 1')
    name=doc.get('plugin','');require(isinstance(name,str) and IDENT.fullmatch(name),'plugin must be 3–64 letters/digits/underscores, beginning with a letter')
    require(name.lower() not in {'dendesignergf','denproppackeditor','zcomauthoring','engine','game','gamefeatures','modulargameplay'},'Reserved plugin name')
    ident=doc.get('id','');require(isinstance(ident,str) and PACKID.fullmatch(ident),'id must be a lowercase stable pack ID')
    for field in ['title','author','version']:label(doc.get(field),field)
    nexus_url(doc)
    entries=doc.get('props');require(isinstance(entries,list) and (0 if allow_empty else 1)<=len(entries)<=2048,'props must contain 1–2048 entries')
    seen=set()
    for i,e in enumerate(entries):
        require(isinstance(e,dict),f'props[{i}] must be an object')
        label(e.get('name'),f'props[{i}].name')
        mesh=e.get('mesh','');require(isinstance(mesh,str) and ASSET.fullmatch(mesh) and len(mesh)<=1023,f'props[{i}].mesh must be a full asset path')
        require(mesh.startswith('/'+name+'/'),f'props[{i}].mesh must belong to /{name}/; ship your own assets, not catalog aliases')
        require(mesh.casefold() not in seen,f'Duplicate mesh: {mesh}');seen.add(mesh.casefold())
        size=e.get('size');require(isinstance(size,list) and len(size)==3 and all(type(x) in (int,float) and math.isfinite(x) and 0<=x<=100000 for x in size),f'props[{i}].size must be three finite dimensions in cm')
        require(type(e.get('collision')) is bool,f'props[{i}].collision must be true or false')
        label(e.get('tags',''),f'props[{i}].tags',512,False)
        label(e.get('description',''),f'props[{i}].description',256,False)
    # Optional explicit ownership inventory; materials can belong to a pack even
    # when they are not catalog props. IDs remain stable across asset renames.
    if 'assets' in doc:
        assets=doc['assets'];require(isinstance(assets,list) and len(assets)<=8192,'assets must contain at most 8192 ownership records')
        ids=set();paths=set();meshes=set()
        for a in assets:
            require(isinstance(a,dict) and set(a)=={'id','path','kind'},'asset ownership requires id, path and kind')
            label(a['id'],'asset id')
            require(PACKID.fullmatch(a['id']) and a['id'] not in ids,'Invalid or duplicate stable asset ID');ids.add(a['id'])
            path=a['path'];require(isinstance(path,str) and len(path)<=1023 and ASSET.fullmatch(path) and path.startswith('/'+name+'/'),'Owned asset must belong to this plugin')
            require(path.casefold() not in paths,'Duplicate owned asset');paths.add(path.casefold())
            require(a['kind'] in ('mesh','material'),'Owned asset kind must be mesh or material')
            if a['kind']=='mesh':meshes.add(path.casefold())
        require(seen<=meshes,'Explicit ownership must include every catalog mesh')
    return doc



def sharing_manifest(doc):
    """Allowlisted ownership sidecar shipped beside a pack's containers."""
    import hashlib
    validate(doc)
    result={k:doc[k] for k in ('schema','plugin','id','title','author','version')}
    if doc.get('nexus_url'):result['nexus_url']=doc['nexus_url']
    result['props']=[{k:e[k] for k in ('name','mesh','size','collision','tags','description') if k in e} for e in doc['props']]
    result['assets']=doc.get('assets',[dict(id='legacy-'+hashlib.sha256(e['mesh'].encode()).hexdigest(),path=e['mesh'],kind='mesh') for e in doc['props']])
    return result


def blank():
    return dict(schema=1, plugin='', id='', title='', author='', version='1.0.0', props=[])


def descriptor(doc, shipping=False):
    result = {'FileVersion': 3, 'Version': 1, 'VersionName': doc['version'],
              'FriendlyName': doc['title'], 'CreatedBy': doc['author'],
              'Description': 'Den Designer prop pack: '+doc['id'], 'Category': 'Game Features',
              'CanContainContent': True, 'Installed': False, 'ExplicitlyLoaded': shipping,
              'Plugins': [{'Name': n, 'Enabled': True} for n in ('GameFeatures','ModularGameplay','DenDesignerGF')]}
    if shipping: result['BuiltInInitialFeatureState'] = 'Active'
    else: result['EnabledByDefault'] = True
    return result


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    os.replace(temp, path)


def owned_folder(project, name):
    require(isinstance(name,str) and IDENT.fullmatch(name), 'Invalid plugin name')
    plugins = (Path(project)/'Plugins').resolve()
    folder = plugins/name
    require(folder.resolve().parent == plugins, "Pack folder must be inside this project's Plugins folder")
    return folder


def read(folder):
    doc = json.loads((Path(folder)/'Authoring/pack.json').read_text(encoding='utf-8-sig'))
    validate(doc, allow_empty=True)
    return doc


def save(project, doc, previous=None):
    validate(doc, allow_empty=True)
    folder = owned_folder(project, doc['plugin'])
    if previous is None:
        require(not folder.exists(), 'That folder exists. Open the existing pack instead.')
        require(not any(p.name.casefold()==folder.name.casefold() for p in folder.parent.iterdir()),
                'A plugin with this name already exists (case-insensitive).')
    else:
        require(Path(previous).resolve()==folder.resolve(), 'Plugin name cannot change after creation')
        old=read(folder)
        require(old['plugin']==doc['plugin'] and old['id']==doc['id'], 'Pack ID and plugin name cannot change after creation')
    (folder/'Content').mkdir(parents=True,exist_ok=True)
    atomic_json(folder/'Authoring/pack.json', doc)
    atomic_json(folder/(doc['plugin']+'.uplugin'), descriptor(doc))
    return folder


def inventory(listing, doc):
    items=re.findall(r'Display: "([^"\r\n]+)" offset:', listing)
    require(bool(items), 'Cooked inventory is empty')
    name=doc['plugin']
    prefixes=[f'../../../SWZeroCompany/{loc}/{name}/' for loc in ('Mods','Plugins','Plugins/GameFeatures')]
    for item in items:
        require(item=='<ContainerHeader>' or any(item.startswith(p) for p in prefixes), 'Cook included content outside this pack: '+item)
    assets=[name,'BP_PropPack']+[p['mesh'].split('.',1)[0][len(name)+2:] for p in doc['props']]
    assets += [a['path'].split('.',1)[0][len(name)+2:] for a in doc.get('assets',[])]
    for asset in assets:
        require(any(i.endswith('/Content/'+asset+'.uasset') for i in items), 'Cook omitted asset: '+asset)
    return items
