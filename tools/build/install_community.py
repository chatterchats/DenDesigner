#!/usr/bin/env python3
"""Install the optional Community bridge after validating its archive and game.

This does not configure Wine/Lutris DLL overrides or install the pak runtime.
Unknown proxies are never overwritten. No files are written before preflight.
"""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

SUPPORTED_EXE = 'aa3ff2e0759c90bae58054f2a68398e5b705fdfd05659242404d8c3602c6f36e'
FILES = {'Binaries/Win64/version.dll', 'Binaries/Win64/den-community.exe', 'COMMUNITY-BRIDGE.md', 'LICENSE'}
BINARIES = ('version.dll', 'den-community.exe')
RECORD = 'DenCommunityBridge.install.json'
HEX = re.compile(r'[0-9a-f]{64}\Z')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    with path.open('rb') as source:
        result = hashlib.sha256()
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
        return result.hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def game_running(proc=Path('/proc')):
    if os.name == 'nt':
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq SWZeroCompany.exe', '/FO', 'CSV', '/NH'],
                                capture_output=True, text=True, timeout=10, check=True)
        return any(row and row[0].casefold() == 'swzerocompany.exe' for row in csv.reader(io.StringIO(result.stdout)))
    require(proc.is_dir(), 'Cannot inspect running game processes')
    for directory in proc.iterdir():
        if not directory.name.isdigit():
            continue
        try:
            args = (directory / 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        basename = lambda arg: arg.replace(b'\\', b'/').rsplit(b'/', 1)[-1].lower()
        first = basename(args[0]) if args else b''
        candidates = args if first in (b'wine', b'wine64', b'wine-preloader', b'wine64-preloader') else args[:1]
        if any(basename(arg) == b'swzerocompany.exe' for arg in candidates):
            return True
    return False


def validated_archive(path, supported_exe=SUPPORTED_EXE):
    require(path.stat().st_size <= 128 * 1024 * 1024, 'Archive exceeds size limit')
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        require(len(infos) == len(FILES) + 1 and {i.filename for i in infos} == FILES | {'manifest.json'}, 'Unexpected archive inventory')
        require(all(not i.is_dir() and not i.flag_bits & 1 and i.file_size <= 32 * 1024 * 1024
                    and (i.external_attr >> 16) & 0o170000 in (0, 0o100000) for i in infos), 'Unsafe archive member')
        require(sum(i.file_size for i in infos) <= 96 * 1024 * 1024, 'Expanded archive exceeds size limit')
        require(archive.testzip() is None, 'Archive CRC check failed')
        require(archive.getinfo('manifest.json').file_size <= 1024 * 1024, 'Manifest exceeds size limit')
        manifest = json.loads(archive.read('manifest.json'), object_pairs_hook=unique)
        require(type(manifest) is dict and type(manifest.get('format')) is int and manifest['format'] == 1, 'Unsupported bridge manifest')
        require(manifest.get('supported_executable_sha256') == supported_exe and HEX.fullmatch(supported_exe), 'Unsupported executable compatibility declaration')
        require(manifest.get('requires_runtime') == '0.9.20'
                and manifest.get('requires_ue4ss') is False and manifest.get('requires_python') is False, 'Unexpected bridge requirements')
        require(type(manifest.get('version')) is str and re.fullmatch(r'[0-9A-Za-z._-]{1,64}', manifest['version']), 'Invalid bridge version')
        require(type(manifest.get('files')) is dict and set(manifest['files']) == FILES, 'Manifest inventory differs')
        payloads = {name: archive.read(name) for name in FILES}
        for name, data in payloads.items():
            row = manifest['files'][name]
            require(type(row) is dict and type(row.get('bytes')) is int and row['bytes'] == len(data)
                    and row.get('sha256') == digest(data), 'Archive hash/length mismatch: ' + name)
    return manifest, payloads, file_digest(path)


def install(archive, game, *, running=game_running, supported_exe=SUPPORTED_EXE):
    manifest, payloads, archive_sha = validated_archive(Path(archive), supported_exe)
    game = Path(game).resolve()
    target = game / 'SWZeroCompany/Binaries/Win64'
    executable = target / 'SWZeroCompany.exe'
    require(target.resolve().is_relative_to(game) and executable.is_file() and not executable.is_symlink(), 'Expected game directory containing SWZeroCompany/Binaries/Win64/SWZeroCompany.exe')
    require(file_digest(executable) == supported_exe, 'Shipped executable is not the supported bridge build')
    require(not running(), 'Refusing installation: SWZeroCompany.exe is running; close the game first')
    record = target / RECORD
    require(not record.is_symlink(), 'Refusing symlink installation record')
    prior = {}
    if record.exists():
        require(record.is_file() and record.stat().st_size <= 65536, 'Invalid previous installation record')
        prior = json.loads(record.read_text(), object_pairs_hook=unique)
        require(type(prior) is dict and prior.get('product') == 'DenCommunityBridge' and prior.get('format') == 1
                and type(prior.get('binaries')) is dict and set(prior['binaries']) == set(BINARIES)
                and all(type(v) is str and HEX.fullmatch(v) for v in prior['binaries'].values()), 'Unknown installation record')
    hashes = {name: digest(payloads['Binaries/Win64/' + name]) for name in BINARIES}
    for name in BINARIES:
        path = target / name
        require(not path.is_symlink(), 'Refusing symlink binary: ' + name)
        if path.exists():
            require(path.is_file() and file_digest(path) in (hashes[name], prior.get('binaries', {}).get(name)),
                    'Refusing to overwrite unknown existing proxy/binary: ' + name)
    installed = {'format': 1, 'product': 'DenCommunityBridge', 'version': manifest['version'],
                 'requires_runtime': manifest['requires_runtime'], 'supported_executable_sha256': supported_exe,
                 'archive_sha256': archive_sha, 'binaries': hashes}
    data = {name: payloads['Binaries/Win64/' + name] for name in BINARIES}
    data[RECORD] = (json.dumps(installed, indent=2) + '\n').encode()
    require(not running(), 'Refusing installation: game started during preflight')
    staged = []
    try:
        for name, content in data.items():
            with tempfile.NamedTemporaryFile(prefix='.den-community-', dir=target, delete=False) as output:
                staged.append((Path(output.name), target / name))
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
        for source, destination in staged:
            os.replace(source, destination)
    finally:
        for source, _ in staged:
            source.unlink(missing_ok=True)
    return installed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--game', type=Path, required=True, help='Directory containing SWZeroCompany')
    args = parser.parse_args()
    print(json.dumps(install(args.archive, args.game), indent=2))
