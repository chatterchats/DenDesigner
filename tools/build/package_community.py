#!/usr/bin/env python3
"""Package the optional HoloNet bridge (one version.dll); never install implicitly."""
import hashlib
import json
from pathlib import Path
from package_gf import archive

ROOT = Path(__file__).resolve().parents[2]
VERSION = '0.9.20'


def package(root=ROOT):
    native = root / 'dist/build/community-native'
    report = json.loads((native / 'build.json').read_text())
    sources = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted((root / 'native/community').iterdir()) if p.is_file()}
    if report['sources'] != sources:
        raise ValueError('Native source changed since its recorded build')
    files = {}
    for name in ['version.dll']:
        data = (native / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != report['binaries'][name]:
            raise ValueError('Native binary does not match completed build: ' + name)
        files['Binaries/Win64/' + name] = data
    files['COMMUNITY-BRIDGE.md'] = (root / 'distribution/community/README.md').read_bytes()
    files['LICENSE'] = (root / 'LICENSE').read_bytes()
    return archive(root / 'dist/packages' / ('DenDesigner-CommunityBridge-' + VERSION + '.zip'), files,
        {'format':1, 'version':VERSION, 'requires_runtime':'0.9.20',
         'requires_ue4ss':False, 'requires_python':False,
         'supported_executable_sha256':'aa3ff2e0759c90bae58054f2a68398e5b705fdfd05659242404d8c3602c6f36e',
         'native_build':report,
         'verification':'See docs/community-verification.md; packaging is not shipped-game acceptance.'})


if __name__ == '__main__':
    print(json.dumps(package(), indent=2))
