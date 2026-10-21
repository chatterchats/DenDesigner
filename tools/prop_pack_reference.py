#!/usr/bin/env python3
"""Export the minimal DenDesignerGF editor reference for independent pack authoring.

Output must be a new directory, normally <kit>/Plugins/DenDesignerGF. This is not
an installable replacement for Den Designer and is never included in a pack.
"""
import argparse
import json
from pathlib import Path
import shutil
from gf_build_info import ROOT, verify, require, sha


def export(output,root=ROOT):
    build=verify(root)
    source=root/'unreal/DenDesignerGF/Content/Runtime/BP_DenPropPack.uasset'
    require(source.is_file(),'Author the current runtime before exporting its provider reference')
    output=Path(output)
    require(not output.exists(),'Refusing to replace an existing plugin: '+str(output))
    descriptor={'FileVersion':3,'Version':1,'VersionName':build['version']+'-authoring',
                'FriendlyName':'Den Designer pack authoring reference (DO NOT SHIP)',
                'Description':'Editor-only content reference. Install the real Den Designer in the game.',
                'CanContainContent':True,'EnabledByDefault':True,'ExplicitlyLoaded':False,'Installed':False}
    (output/'Content/Runtime').mkdir(parents=True)
    shutil.copy2(source,output/'Content/Runtime/BP_DenPropPack.uasset')
    (output/'DenDesignerGF.uplugin').write_text(json.dumps(descriptor,indent=2)+'\n')
    metadata={'format':1,'runtime_version':build['version'],'asset':'/DenDesignerGF/Runtime/BP_DenPropPack',
              'sha256':sha(source),'editor_reference_only':True}
    (output/'authoring-reference.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (output/'README.txt').write_text('Editor authoring reference only. Keep this plugin in Plugins/DenDesignerGF, not Mods or Plugins/GameFeatures. Do not install or ship it with your pack. The real Den Designer supplies this class in game.\n')
    return metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:print(json.dumps(export(args.output),indent=2))
    except (ValueError,OSError) as exc:parser.exit(1,str(exc)+'\n')


if __name__=='__main__':main()
