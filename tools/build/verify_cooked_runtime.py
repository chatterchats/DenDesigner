#!/usr/bin/env python3
"""Deserialize every cooked runtime export and Blueprint script before packaging.

Editor compilation and VM tests do not validate the shipping serialized stream.
CUE4Parse logs export errors even when its CLI exits zero; reject those too.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from gf_build_info import ROOT, verify


def check(root=ROOT):
    build = verify(root)
    parser = Path(os.environ.get('ZC_PARSE', str(root.parent.parent / 'ZCRE/bin/zcparse')))
    game = Path(os.environ.get('SWZC_GAME', '/run/media/chats/e0057d4a-fe46-43eb-a837-db51979c500f/Games/STAR WARS Zero Company (2026)/Star Wars Zero Company'))
    base = game / 'SWZeroCompany/Content/Paks'
    containers = root / 'dist/build/runtime/SWZeroCompany/Content/Paks/~mods'
    evidence = root / 'dist/verification/community/cooked-runtime'
    evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cooked-', dir=evidence) as folder:
        work = Path(folder); mounted = work / 'containers'; mounted.mkdir(); output = work / 'exports'; output.mkdir()
        for source in [base, containers]:
            for p in source.iterdir():
                if p.is_file() and p.suffix in ('.pak', '.utoc', '.ucas'):
                    (mounted / p.name).symlink_to(p.resolve())
        env = dict(os.environ, ZC_PAKS=str(mounted), ZC_SCRIPT='1')
        result = subprocess.run([str(parser), 'json', 'DenDesignerGF', str(output)], env=env, text=True, capture_output=True, timeout=180)
        log = result.stdout + result.stderr
        (evidence / 'parse.log').write_text(log)
        if result.returncode or any(word in log for word in (' ERR]', 'Could not read ', 'Unsupported serialized property', 'Bad name index', 'Failed to serialize script bytecode')):
            raise ValueError('Cooked runtime deserialization failed; see ' + str(evidence / 'parse.log'))
        failed = output / '_failed.json.tsv'
        if failed.exists() and failed.read_text().strip():
            raise ValueError('Cooked packages failed to parse: ' + failed.read_text()[:2000])
        count = len(list(output.rglob('*.json')))
        if count != build['cooked_assets']:
            raise ValueError(f'Parsed {count} packages; expected {build["cooked_assets"]}')
    report = {'format': 1, 'version': build['version'], 'containers': build['containers'], 'parsed_packages': count, 'errors': 0, 'script_data': True}
    (evidence / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
