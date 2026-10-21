#!/usr/bin/env python3
"""Stage Lua-edition JSON layouts as native Den Designer saves, preserving originals.

Usage: python migrate_layouts.py --source /path/to/Saved/ZComDen --output /new/staging-folder
No game files are installed or overwritten. Requires only Python 3.10+.
"""
import argparse
import hashlib
import json
import math
import re
import shutil
import time
import uuid
from pathlib import Path

from den_save import Codec, MAX_BYTES, MAX_ITEMS

ROOT='/DenDesignerGF/Runtime/'
LAYOUT=ROOT+'BP_DenLayoutSave.BP_DenLayoutSave_C'
LIBRARY=ROOT+'BP_DenPresetLibrary.BP_DenPresetLibrary_C'
CAMPAIGN=re.compile(r'[0-9A-Fa-f]{32}')
ASSET=re.compile(r'/[A-Za-z0-9_]+/[^.\x00-\x1f]+\.[A-Za-z0-9_-]+')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def text(value, label, nonempty=False):
    require(isinstance(value,str) and '\0' not in value and (value or not nonempty), label+': expected a string')
    value.encode('utf-16-le')  # Reject unpaired surrogates from malformed JSON.
    return value


def obj(value, allowed, label):
    require(isinstance(value,dict),label+': expected an object')
    require(not (set(value)-set(allowed)),label+': unsupported fields '+', '.join(sorted(set(value)-set(allowed))))
    return value


def vector(value, label, positive=False):
    require(isinstance(value,list) and len(value)==3 and
            all(type(v) in (int,float) and math.isfinite(v) and abs(v)<=1e7 and (not positive or v>0) for v in value),
            label+': expected three '+('positive ' if positive else '')+'finite numbers within 10,000,000')
    return value


def asset(value,label):
    text(value,label,True)
    require(ASSET.fullmatch(value) is not None,label+': invalid asset path')
    return value


def parse_json(data, label):
    require(len(data)<=MAX_BYTES,label+': file too large')
    def pairs(items):
        result={}
        for k,v in items:
            require(k not in result,label+': duplicate JSON key '+k)
            result[k]=v
        return result
    def constant(value):
        raise ValueError(label+': nonfinite JSON value '+value)
    try:
        return json.loads(data.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=constant)
    except (UnicodeError,json.JSONDecodeError,RecursionError) as exc:
        raise ValueError(label+': invalid JSON: '+str(exc)) from exc


def convert(doc):
    obj(doc,{'format','game','placed','stored','vanilla','draft_at'},'layout')
    require(type(doc.get('format')) is int and doc['format']==1,'layout: only format 1 is supported')
    version=text(doc.get('game',''),'game')
    if 'draft_at' in doc:text(doc['draft_at'],'draft_at')
    entries=[]
    ids=set()
    for kind,section in enumerate(['placed','stored']):
        rows=doc.get(section,[])
        require(isinstance(rows,list) and len(rows)<=MAX_ITEMS,section+': expected an array')
        for index,row in enumerate(rows):
            label=f'{section}[{index}]'
            obj(row,{'id','mesh','t','r','s','solid','mats','from'},label)
            key=text(row.get('id'),label+'.id',True)
            require(key not in ids,label+': duplicate placed/stored id '+key)
            ids.add(key)
            if 'solid' in row:require(type(row['solid']) is bool,label+'.solid: expected boolean')
            mats=row.get('mats',[])
            require(isinstance(mats,list) and len(mats)<=MAX_ITEMS,label+'.mats: expected an array')
            for m in mats:
                if m!='':asset(m,label+'.mats')
            entries.append(dict(Kind=kind,Key=key,Mesh=asset(row.get('mesh'),label+'.mesh'),
                Position=vector(row.get('t'),label+'.t'),Rotation=vector(row.get('r',[0,0,0]),label+'.r'),
                Scale=vector(row.get('s',[1,1,1]),label+'.s',True),HasPosition=True,HasRotation=True,HasScale=True,
                CollisionMode=0 if 'solid' not in row else 1 if row['solid'] else 2,Materials=mats,
                Source=text(row.get('from',''),label+'.from')))
    rows=doc.get('vanilla',{})
    require(isinstance(rows,dict) and len(rows)<=MAX_ITEMS,'vanilla: expected an object')
    for key,row in sorted(rows.items()):
        text(key,'vanilla key',True)
        require(key.startswith('/') and ':' in key,'vanilla: invalid object path '+key)
        obj(row,{'hidden','t','r','s','fp'},'vanilla '+key)
        if 'hidden' in row:require(type(row['hidden']) is bool,'vanilla.hidden: expected boolean')
        require(row.get('hidden',False) or any(n in row for n in ['t','r','s']),'vanilla '+key+': empty edit')
        entry=dict(Kind=2,Key=key,Hidden=row.get('hidden',False))
        for old,new in [('t','Position'),('r','Rotation'),('s','Scale')]:
            entry['Has'+new]=old in row
            if old in row:entry[new]=vector(row[old],'vanilla '+key+'.'+old,old=='s')
        if 'fp' in row:
            obj(row['fp'],{'mesh','at'},'fingerprint')
            entry.update(HasFingerprint=True,FingerprintMesh=asset(row['fp'].get('mesh'),'fingerprint.mesh'),
                         FingerprintPosition=vector(row['fp'].get('at'),'fingerprint.at'))
        entries.append(entry)
    require(len(entries)<=MAX_ITEMS,'layout: too many entries')
    return dict(GameVersion=version,Entries=entries)


def campaign_id(name):
    require(CAMPAIGN.fullmatch(name) is not None and int(name,16)!=0,'invalid campaign id '+name)
    return name.upper()


def preset_name(name):
    text(name,'preset name',True)
    clean=name.strip()
    require(0<len(clean.encode('utf-16-le'))//2<=40 and all(ord(c)>=32 and ord(c)!=127 for c in clean),'invalid preset name '+repr(name))
    return clean


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stage(source, output):
    source=Path(source).resolve(strict=True)
    output=Path(output).absolute()
    require(source.is_dir(),'source must be a directory')
    require(not output.exists() and not output.is_symlink(),'output must be a new directory')
    require(not output.resolve().is_relative_to(source),'output must be outside the source directory')
    codec=Codec()
    files={}
    omitted=[]
    # Preserve every file in the layout directories, including .tmp, corrupt and
    # dropped backups. Thumbnail caches and unrelated directories are not migrated.
    for child in sorted(source.iterdir()):
        require(not child.is_symlink(),'source contains a symlink: '+child.name)
        if child.is_file():
            paths=[child]
        elif child.name in ('campaigns','presets','backups') and child.is_dir():
            paths=sorted(child.rglob('*'))
        else:
            omitted.append(child.name)
            continue
        for p in paths:
            require(not p.is_symlink(),'source contains a symlink: '+str(p.relative_to(source)))
            if p.is_dir():continue
            require(p.is_file(),'unsupported source file '+str(p))
            require(p.stat().st_size<=MAX_BYTES,'source file too large: '+str(p))
            files[p.relative_to(source).as_posix()]=(p.read_bytes(),int(p.stat().st_mtime))
    manifest={'format':1,'created_at':int(time.time()),'originals':{},'saves':{},'warnings':[],
              'omitted_directories':omitted,'draft_baseline':'unknown; legacy drafts have no recorded baseline identity'}
    saves={}
    def read(name):
        return parse_json(files[name][0],name)
    def write(key,values,revision,source_name,draft=False,library=False):
        identity=str(uuid.uuid4())
        values=dict(values,SchemaVersion=1,StorageKey=key,Revision=revision,ContentID=identity,WriteCompleteID=identity,
                    EntryCount=len(values['Entries']),WrittenAt=str(files[source_name][1]),IsDraft=draft)
        values.update(DraftBaseRevision=0,DraftBaseID='')
        bank=(revision-1)%(2 if draft else 6)
        filename=f'{key}-{"draft" if draft else "layout"}-{bank}.sav'
        require(filename not in saves,'duplicate output save '+filename)
        data=codec.encode(LIBRARY if library else LAYOUT,values)
        saves[filename]=data
        manifest['saves'][filename]={'sha256':sha(data),'source':source_name,'revision':revision,'entries':len(values['Entries']),
                                     'draft':draft,'baseline_known':False if draft else None}
        if draft:
            manifest['saves'][filename]['legacy_draft_at']=read(source_name).get('draft_at','')
    layouts={}
    if 'home.json' in files or 'home.draft.json' in files:layouts['home']=('home.json','home','')
    for name in files:
        p=Path(name)
        if len(p.parts)==2 and p.parts[0]=='campaigns' and p.suffix=='.json':
            stem=p.stem.removesuffix('.draft')
            cid=campaign_id(stem)
            key='campaign-'+cid
            canonical='campaigns/'+stem+'.json'
            require(key not in layouts or layouts[key][0]==canonical,'campaign filenames collide after normalization')
            layouts[key]=(canonical,'campaign',cid)
    for key,(name,scope,cid) in sorted(layouts.items()):
        metadata=dict(Scope=scope,CampaignID=cid,Enabled=True)
        revision=0
        if name in files:
            # Source backup 1 is newest. Import oldest first so revisions preserve ordering.
            # Legacy campaign filenames can contain lower-case IDs.
            legacy_key='home' if scope=='home' else 'campaign-'+Path(name).stem
            for n in range(5,0,-1):
                backup=f'backups/{legacy_key}.{n}.json'
                if backup not in files:continue
                try:values=convert(read(backup))
                except (ValueError,UnicodeError) as exc:
                    manifest['warnings'].append(backup+': preserved but not converted: '+str(exc))
                    continue
                revision+=1
                write(key,dict(values,**metadata),revision,backup)
            revision+=1
            write(key,dict(convert(read(name)),**metadata),revision,name)
        draft=name.removesuffix('.json')+'.draft.json'
        if draft in files:
            write(key,dict(convert(read(draft)),**metadata),1,draft,True)
            manifest['warnings'].append(draft+': imported with unknown baseline; offer explicit recovery, never apply automatically')
    preset_paths=[n for n in files if len(Path(n).parts)==2 and Path(n).parts[0]=='presets' and n.endswith('.json') and Path(n).name!='index.json']
    presets=[]
    names=set()
    for path in sorted(preset_paths):
        name=preset_name(Path(path).stem)
        # Conservative collision rule; never silently overwrite one imported preset.
        require(name.casefold() not in names,'duplicate preset name ignoring case: '+name)
        names.add(name.casefold())
        presets.append(dict(convert(read(path)),Name=name))
    if presets:
        write('presets',dict(Scope='preset-library',Entries=presets),1,preset_paths[0],library=True)
        manifest['saves']['presets-layout-0.sav']['sources']=sorted(preset_paths)
    for name,(data,_) in files.items():manifest['originals'][name]={'sha256':sha(data),'bytes':len(data)}
    require(saves,'no layouts, drafts or presets found to migrate')
    # Stage into an exclusively-created directory. Clean up only our new output
    # if any write/verification fails; no game/source path is ever mutated.
    output.mkdir(parents=False,exist_ok=False)
    try:
        for name,(data,_) in files.items():
            dest=output/'originals'/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(data)
            require(dest.read_bytes()==data,'original-copy verification failed: '+name)
        native=output/'SaveGames/ZComDen/Native/v1'
        native.mkdir(parents=True)
        for name,data in saves.items():
            dest=native/name
            dest.write_bytes(data)
            require(dest.read_bytes()==data,'native-copy verification failed: '+name)
            codec.decode(data)
        for name,(data,_) in files.items():
            require((source/name).read_bytes()==data,'source changed during migration: '+name)
        (output/'migration.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    except BaseException:
        shutil.rmtree(output)
        raise
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=stage(args.source,args.output)
    except (ValueError,OSError,UnicodeError) as exc:
        parser.exit(1,'Migration stopped: '+str(exc)+'\n')
    print(f"Staged {len(result['saves'])} native saves and preserved {len(result['originals'])} original files in {args.output}")
    for warning in result['warnings']:print('Warning: '+warning)
    print('No game files were installed or overwritten. Keep originals and migration.json with the staged saves.')
