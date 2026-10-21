#!/usr/bin/env python3
"""Validate a prop-pack manifest and generate its content-only Game Feature scaffold."""
import argparse
import json
import math
from pathlib import Path
import re

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


def validate(doc):
    require(isinstance(doc,dict),'Manifest must be an object')
    require(type(doc.get('schema')) is int and doc['schema']==1,'Supported schema is 1')
    name=doc.get('plugin','');require(isinstance(name,str) and IDENT.fullmatch(name),'plugin must be 3–64 letters/digits/underscores, beginning with a letter')
    require(name.lower() not in {'dendesignergf','engine','game','gamefeatures','modulargameplay'},'Reserved plugin name')
    ident=doc.get('id','');require(isinstance(ident,str) and PACKID.fullmatch(ident),'id must be a lowercase stable pack ID')
    for field in ['title','author','version']:label(doc.get(field),field)
    entries=doc.get('props');require(isinstance(entries,list) and 1<=len(entries)<=2048,'props must contain 1–2048 entries')
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
    return doc


def text(value):return json.dumps(value,ensure_ascii=False)
def array(values):return '('+','.join(values)+')'


def provider(doc):
    entries=doc['props']
    details=[]
    for e in entries:
        dims=' × '.join(f'{x:g}' for x in e['size'])+' cm'
        details.append((e.get('description','')+'\n' if e.get('description') else '')+dims+('' if e['collision'] else '\nNo collision'))
    defaults={'SchemaVersion':'1','PackID':doc['id'],'Title':doc['title'],'Author':doc['author'],'Version':doc['version'],
        'Paths':array(text(e['mesh']) for e in entries),'Labels':array(text(e['name']) for e in entries),
        'Details':array(map(text,details)),'Dimensions':array('('+','.join(f'{k}={x}' for k,x in zip('XYZ',e['size']))+')' for e in entries),
        'Solid':array('True' if e['collision'] else 'False' for e in entries),'SearchTexts':array(text(e.get('tags','')) for e in entries)}
    return dict(kind='blueprint',path=f"/{doc['plugin']}/BP_PropPack",parent=BASE,defaults=defaults)


def descriptor(doc):
    return {'FileVersion':3,'Version':1,'VersionName':doc['version'],'FriendlyName':doc['title'],'CreatedBy':doc['author'],
        'Description':'Den Designer prop pack: '+doc['id'],'Category':'Game Features','CanContainContent':True,'Installed':False,
        'ExplicitlyLoaded':True,'BuiltInInitialFeatureState':'Active',
        'Plugins':[{'Name':name,'Enabled':True} for name in ['GameFeatures','ModularGameplay','DenDesignerGF']]}


def generate(doc,output,editor_mounted=False):
    doc=validate(doc);output=Path(output)
    # Generated metadata can be regenerated; existing imported assets are never removed.
    output.mkdir(parents=True,exist_ok=True);(output/'Content').mkdir(exist_ok=True);(output/'Authoring').mkdir(exist_ok=True)
    plugin=descriptor(doc)
    if editor_mounted:
        plugin['ExplicitlyLoaded']=False
        plugin['EnabledByDefault']=True
        plugin.pop('BuiltInInitialFeatureState')
    for path,value in [(output/(doc['plugin']+'.uplugin'),plugin),(output/'Authoring/provider.json',provider(doc)),(output/'Authoring/pack.json',doc)]:
        path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('manifest',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--editor-mounted',action='store_true',help='Mount source content at editor startup (SDK/base-modkit Plugins folder); packaging still emits an active Game Feature')
    args=parser.parse_args()
    try:
        doc=validate(json.loads(args.manifest.read_text()))
        if args.editor_mounted and not args.output:raise ValueError('--editor-mounted requires --output')
        if args.output:generate(doc,args.output,args.editor_mounted)
        print(f"Valid prop pack: {doc['title']} ({len(doc['props'])} props)")
    except (ValueError,OSError) as exc:parser.exit(1,str(exc)+'\n')


if __name__=='__main__':main()
