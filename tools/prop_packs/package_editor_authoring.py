#!/usr/bin/env python3
"""Maintainer packager for the in-editor widget/Python authoring bundle."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def package(root=ROOT):
    source=root/'authoring/prop-packs'
    plugin=source/'Plugins/DenPropPackEditor'
    descriptor=json.loads((plugin/'DenPropPackEditor.uplugin').read_text())
    assert not descriptor.get('Modules'), 'The authoring bundle must not require a custom native module'
    files={'LICENSE':root/'LICENSE','README.md':source/'EDITOR-GUIDE.md'}
    for name in ('DenPropPackEditor.uplugin','README.md','Content/UI/EUW_PropPacks.uasset'):
        files['Plugins/DenPropPackEditor/'+name]=plugin/name
    for path in (plugin/'Content/Python').rglob('*.py'):
        files['Plugins/DenPropPackEditor/'+path.relative_to(plugin).as_posix()]=path
    reference=source/'Plugins/DenDesignerGF'
    for name in ('DenDesignerGF.uplugin','authoring-reference.json','README.txt','Content/Runtime/BP_DenPropPack.uasset'):
        files['Plugins/DenDesignerGF/'+name]=reference/name
    meta=json.loads((reference/'authoring-reference.json').read_text())
    assert hashlib.sha256((reference/'Content/Runtime/BP_DenPropPack.uasset').read_bytes()).hexdigest()==meta['sha256']
    output=root/'dist/packages'/f'DenDesigner-PropPack-Editor-{descriptor["VersionName"]}.zip'
    output.parent.mkdir(parents=True,exist_ok=True)
    metadata={'format':2,'kind':'editor_only_prop_pack_authoring','version':descriptor['VersionName'],
              'platform':'EditorContent','engine_version':'5.6.1','engine_build_id':None,
              'provider_runtime_version':meta['runtime_version'],'bundled_python':True,
              'requires_external_python':False,'requires_manual_scripts':False,'requires_custom_native_module':False,
              'files':{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in sorted(files.items())}}
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,path in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            archive.writestr(info,path.read_bytes())
        archive.writestr('manifest.json',json.dumps(metadata,indent=2)+'\n')
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert all(hashlib.sha256(archive.read(n)).hexdigest()==h for n,h in metadata['files'].items())
    output.with_suffix('.zip.sha256').write_text(hashlib.sha256(output.read_bytes()).hexdigest()+'  '+output.name+'\n')
    return output


if __name__=='__main__':print(package())
