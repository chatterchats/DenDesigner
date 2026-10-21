#!/usr/bin/env python3
"""Export migration schema from published specs and a real headless-test GVAS header."""
import json
import sys
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'tools/migration'))
sys.path.insert(0,str(REPO/'unreal/specs'))
from den_save import Reader
from runtime import specs,ROOT
r=Reader((REPO/'dist/verification/native/migration-fixtures/layout.sav').read_bytes())
assert r.take(4)==b'GVAS' and r.number('i')==3
assert r.number('ii')==[522,1017]
assert r.number('HHHI')==[5,6,1,0]
assert r.string()=='UE5'
assert r.number('i')==3
count=r.number('i'); assert 0<count<1000
prefix=r.data[:r.pos]
versions=[r.take(20) for _ in range(count)]
header=(prefix+b"".join(sorted(versions))).hex()
assert r.string()==ROOT+'BP_DenLayoutSave.BP_DenLayoutSave_C'
selected={ROOT+n for n in ['ST_DenEntry','ST_DenPresetValue','BP_DenLayoutSave','BP_DenPresetLibrary']}
result={'version':1,'engine':'5.6.1','header':header,'types':{},'classes':{}}
result['compatible_headers']=json.loads((REPO/'tools/migration/den_save_headers.json').read_text())
for _,s in specs():
 if s['path'] not in selected:continue
 is_struct=s['kind']=='struct'
 fields=[]
 for f in s['fields' if is_struct else 'variables']:
  kind=f['type']; default=f.get('default','')
  if kind.endswith('[]'):default=[]
  elif kind=='bool':default=default=='true'
  elif kind in ('int','int64'):default=int(default or 0)
  elif kind in ('vector','rotator'):default=[float(v) for v in (default or '0,0,0').split(',')]
  fields.append(dict(name=f['name'],serialized=f['name']+'_0_'+f['guid'].replace('-','').upper() if is_struct else f['name'],type=kind,default=default))
 if is_struct:result['types'][s['path']]={'guid':s['guid'],'fields':fields}
 else:result['classes'][s['path']+'.'+s['path'].rsplit('/',1)[1]+'_C']={'fields':fields}
(REPO/'tools/migration/den_save_schema.json').write_text(json.dumps(result,indent=2)+'\n')
