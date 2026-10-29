#!/usr/bin/env python3
"""Bundle the verified matching pak and silent Community transport archives."""
import json
from pathlib import Path
from package_gf import archive, package as package_runtime
from package_community import package as package_bridge

ROOT = Path(__file__).resolve().parents[2]


def package():
    package_runtime(ROOT)
    package_bridge(ROOT)
    names = ['DenDesigner-Pak-0.9.20.zip',
             'DenDesigner-CommunityBridge-0.9.20.zip']
    files = {name: (ROOT / 'dist/packages' / name).read_bytes() for name in names}
    files['README.md'] = (ROOT / 'distribution/community/README.md').read_bytes()
    return archive(ROOT / 'dist/packages/DenDesigner-HoloNet-0.9.20.zip', files,
                   {'format': 1, 'runtime': '0.9.20',
                    'bridge': '0.9.20', 'full_den_publishing': False,
                    'verification': 'See docs/community-verification.md; live-account acceptance remains separate.'})


if __name__ == '__main__':
    print(json.dumps(package(), indent=2))
