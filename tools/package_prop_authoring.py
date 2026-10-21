#!/usr/bin/env python3
"""Package the public creator tools, without the private kit or sample artwork."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def package(root=ROOT):
    source = root / 'authoring/prop-packs'
    files = {'LICENSE': root / 'LICENSE'}
    for name in ['README.md', 'kit-compatibility.md', 'template.json', 'example/CREDITS.md']:
        files['authoring/prop-packs/' + name] = source / name
    # Never sweep local editor binaries/caches into the creator handoff.
    for plugin, names in {
        'DenDesignerGF': ['README.txt', 'authoring-reference.json', 'DenDesignerGF.uplugin',
                          'Content/Runtime/BP_DenPropPack.uasset'],
        'ZComAuthoring': ['README.md', 'ZComAuthoring.uplugin', 'Content/Python/zcom_authoring.py'],
    }.items():
        for name in names:
            files[f'Plugins/{plugin}/{name}'] = source / 'Plugins' / plugin / name
    for path in (source / 'Plugins/ZComAuthoring/Source').rglob('*'):
        if path.is_file() and path.suffix in {'.cpp', '.h', '.cs'}:
            files[path.relative_to(source).as_posix()] = path
    for name in ['prop_pack.py', 'build_prop_pack.sh']:
        files['tools/' + name] = root / 'tools' / name
    for name in ['build_prop_pack.py', 'verify_prop_pack.py']:
        files['unreal/scripts/' + name] = root / 'unreal/scripts' / name
    metadata = json.loads((source / 'Plugins/DenDesignerGF/authoring-reference.json').read_text())
    reference = source / 'Plugins/DenDesignerGF/Content/Runtime/BP_DenPropPack.uasset'
    assert hashlib.sha256(reference.read_bytes()).hexdigest() == metadata['sha256'], 'Reference hash mismatch'
    output = root / 'dist' / ('DenDesigner-PropPack-Authoring-' + metadata['runtime_version'] + '.zip')
    output.parent.mkdir(parents=True, exist_ok=True)
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sorted(files.items())}
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            archive.write(path, name)
        archive.writestr('README.txt', 'Start with authoring/prop-packs/README.md. Plugins contains editor prerequisites, NOT game mods. SDK or base modkit required; no private merged kit required. Linux UE 5.6.1 verified.\n')
        archive.writestr('SHA256SUMS.json', json.dumps(hashes, indent=2) + '\n')
    return output


if __name__ == '__main__':
    print(package())
