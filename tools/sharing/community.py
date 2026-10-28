"""Read-only Community client and optional out-of-process companion.

The game never evaluates this response as code. A transport yields bounded bytes;
validation, dependency preflight and native value conversion do not depend on HTTP.
Reference tooling only: no shipped-game binding or installer is supplied.
Requires Python 3.11+. Run
``python -m tools.sharing.community --mailbox DIR --inventory FILE``.
"""
import argparse
import asyncio
from dataclasses import dataclass
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
from typing import Protocol
from urllib.parse import urlsplit

from . import contract

ORIGIN = 'https://share.zcom.app'
CODE = re.compile(r'[A-Za-z0-9_-]{6,32}\Z', re.ASCII)
TOKEN = re.compile(r'[0-9a-f]{32}\Z', re.ASCII)
MAX_METADATA = 64 * 1024
MAX_RESPONSE = contract.MAX_BYTES
TIMEOUT = 20.0


class CommunityError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def code_from_input(value):
    if type(value) is not str or len(value) > 256:
        raise CommunityError('INVALID_CODE', 'Enter a share code or approved Community link.')
    value = value.strip()
    if CODE.fullmatch(value):
        return value
    # Compare the entire authority, rejecting credentials, ports, escapes and
    # host canonicalization tricks before parsing the path.
    match = re.fullmatch(r'https://(?:share\.)?zcom\.app/comp/([A-Za-z0-9_-]{6,32})/?', value, re.ASCII)
    if not match:
        raise CommunityError('INVALID_URL', 'Only HTTPS zcom.app composition links are accepted.')
    return match[1]


def approved_url(url):
    if type(url) is not str or not re.fullmatch(
            r'https://share\.zcom\.app/api/v1/comp/[A-Za-z0-9_-]{6,32}(?:/document)?', url, re.ASCII):
        raise CommunityError('UNAPPROVED_URL', 'The service URL is not approved.')
    return url


def strict_json(raw, maximum):
    if type(raw) is not bytes or len(raw) > maximum:
        raise CommunityError('TOO_LARGE', 'Response exceeds its byte limit.')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate key')
            result[key] = value
        return result
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite number')))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CommunityError('MALFORMED', 'The service returned malformed JSON.') from exc


class Transport(Protocol):
    async def get(self, url: str, cancel: asyncio.Event) -> bytes:
        """Return bounded JSON bytes, or raise CommunityError/CancelledError."""
        ...


def _http_get(url):
    """Child process: fixed-host HTTPS, no redirect following, no decompression.

    Isolation allows the parent to kill DNS, TLS, headers, or a slow body at its
    total deadline; a socket inactivity timeout alone would not bound all of them.
    """
    approved_url(url)
    path = urlsplit(url).path
    maximum = MAX_RESPONSE if path.endswith('/document') else MAX_METADATA
    connection = http.client.HTTPSConnection('share.zcom.app', timeout=10,
                                             context=ssl.create_default_context())
    try:
        connection.request('GET', path, headers={'Accept': 'application/json',
                           'Accept-Encoding': 'identity', 'User-Agent': 'DenDesignerCommunity/1'})
        response = connection.getresponse()
        if response.status == 404:
            raise CommunityError('NOT_FOUND', 'This composition is missing or unpublished.')
        if response.status != 200:
            raise CommunityError('HTTP_ERROR', 'Community returned HTTP ' + str(response.status) + '.')
        headers = response.headers
        if headers.get_content_type() != 'application/json':
            raise CommunityError('CONTENT_TYPE', 'Expected a JSON response.')
        encodings = headers.get_all('Content-Encoding', [])
        if encodings and encodings != ['identity']:
            raise CommunityError('ENCODING', 'Compressed responses are not accepted.')
        lengths = headers.get_all('Content-Length', [])
        transfer = headers.get_all('Transfer-Encoding', [])
        if len(lengths) > 1 or (lengths and transfer) or (transfer and transfer != ['chunked']):
            raise CommunityError('FRAMING', 'Ambiguous HTTP response framing.')
        if lengths and (not re.fullmatch(r'[0-9]{1,10}', lengths[0]) or int(lengths[0]) > maximum):
            raise CommunityError('TOO_LARGE', 'Response exceeds its byte limit.')
        raw = response.read(maximum + 1)
        if len(raw) > maximum:
            raise CommunityError('TOO_LARGE', 'Response exceeds its byte limit.')
        if lengths and len(raw) != int(lengths[0]):
            raise CommunityError('TRUNCATED', 'The service response was incomplete.')
        return raw
    except CommunityError:
        raise
    except TimeoutError as exc:
        raise CommunityError('TIMEOUT', 'Community request timed out.') from exc
    except (OSError, http.client.HTTPException) as exc:
        raise CommunityError('OFFLINE', 'Community is offline or the connection failed.') from exc
    finally:
        connection.close()


class HttpsTransport:
    def __init__(self, timeout=TIMEOUT):
        if not 0 < timeout <= TIMEOUT:
            raise ValueError('Invalid total timeout')
        self.timeout = timeout

    async def get(self, url, cancel):
        approved_url(url)
        if cancel.is_set():
            raise asyncio.CancelledError
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'tools.sharing.community', '--http-child', url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            cwd=str(Path(__file__).resolve().parents[2]), limit=MAX_RESPONSE + 4096)
        communicate = asyncio.create_task(process.communicate())
        cancelled = asyncio.create_task(cancel.wait())
        try:
            done, _ = await asyncio.wait((communicate, cancelled), timeout=self.timeout,
                                         return_when=asyncio.FIRST_COMPLETED)
            if cancel.is_set():
                raise asyncio.CancelledError
            if communicate not in done:
                raise CommunityError('TIMEOUT', 'Community request timed out. Try again when online.')
            raw, _ = communicate.result()
            if len(raw) > MAX_RESPONSE + 4096:
                raise CommunityError('TOO_LARGE', 'Response exceeds its byte limit.')
            if process.returncode:
                error = strict_json(raw, 4096)
                if type(error) is not dict or set(error) != {'code', 'message'}:
                    raise CommunityError('TRANSPORT', 'The transport failed.')
                raise CommunityError(str(error['code']), safe_text(str(error['message']), 256))
            return raw
        finally:
            if process.returncode is None:
                process.kill()
            await process.wait()
            cancelled.cancel()
            if not communicate.done():
                communicate.cancel()
            await asyncio.gather(communicate, cancelled, return_exceptions=True)


@dataclass
class FetchedComposition:
    code: str
    document: dict
    local: dict
    report: str


def dependency_report(doc, issues=()):
    deps = doc['dependencies']
    packs = ', '.join(p['id'] + '@' + p['version'] for p in deps['packs']) or 'none'
    result = f"Dependencies: {len(deps['assets'])} assets; packs: {packs}."
    if issues:
        result += ' Import blocked: ' + ', '.join(issues)
    return result


async def fetch_composition(value, transport, cancel, inventory):
    """Resolve only versioned approved routes, validate, then preflight atomically."""
    code = code_from_input(value)
    try:
        async with asyncio.timeout(TIMEOUT * 2):
            metadata = strict_json(await transport.get(ORIGIN + '/api/v1/comp/' + code, cancel), MAX_METADATA)
            if cancel.is_set():
                raise asyncio.CancelledError
            if type(metadata) is not dict or metadata.get('api_version') != 'v1':
                raise CommunityError('UNSUPPORTED_API', 'Unsupported Community API response.')
            item = metadata.get('item')
            if type(item) is not dict or item.get('code') != code or item.get('kind') != 'comp':
                raise CommunityError('MALFORMED', 'Listing does not identify this composition.')
            if type(item.get('schema_version')) is not int or item['schema_version'] != 1:
                raise CommunityError('UNSUPPORTED_SCHEMA', 'This composition needs a newer sharing reader.')
            expected = item.get('document_sha256')
            size = item.get('document_bytes')
            if type(expected) is not str or not contract.HASH.fullmatch(expected) or type(size) is not int or not 0 < size <= MAX_RESPONSE:
                raise CommunityError('DOWNLOAD_UNAVAILABLE', 'This listing has no validated downloadable document.')
            raw = await transport.get(ORIGIN + '/api/v1/comp/' + code + '/document', cancel)
            if cancel.is_set():
                raise asyncio.CancelledError
            if type(raw) is not bytes or len(raw) != size or hashlib.sha256(raw).hexdigest() != expected:
                raise CommunityError('INTEGRITY', 'Downloaded document does not match the published listing.')
            try:
                doc = contract.loads(raw)
            except ValueError as exc:
                raise CommunityError('INVALID_DOCUMENT', 'Invalid composition: ' + str(exc)) from exc
            if doc['content_type'] != 'composition':
                raise CommunityError('WRONG_TYPE', 'Only compositions can be imported here.')
            issues = contract.compatibility_issues(doc, inventory['target'],
                         inventory['installed_packs'], inventory['available_assets'])
            report = dependency_report(doc, issues)
            if issues:
                raise CommunityError('DEPENDENCIES', report)
            local = contract.import_layout(doc, inventory['target'], inventory['installed_packs'], inventory['available_assets'])
            return FetchedComposition(code, doc, local, report)
    except TimeoutError as exc:
        raise CommunityError('TIMEOUT', 'Community request timed out.') from exc


def safe_text(value, maximum=1024):
    return ''.join(c if 32 <= ord(c) < 127 else ' ' for c in value).strip()[:maximum]


def response_text(token, result=None, error=None):
    if not TOKEN.fullmatch(token):
        raise ValueError('Invalid token')
    lines = ['ZCOM-COMMUNITY\t1\t' + token]
    if error is not None:
        lines += ['error\t' + safe_text(str(error), 1500), 'end']
    else:
        # A stable code suffix separates equal titles and gives repeat imports
        # the native library's ordinary explicit replacement behavior.
        title = safe_text(result.document['metadata']['title'], 27) or 'Community composition'
        name = title + ' ' + result.code[-12:]
        lines += ['ok', 'name\t' + name, 'report\t' + safe_text(result.report),
                  'anchor\t' + '\t'.join(map(str, result.local['CompositionAnchor']))]
        for part in result.local['Entries']:
            lines.append('part\t' + '\t'.join(map(str, [part['Mesh'], *part['Position'],
                *part['Rotation'], *part['Scale'], part['CollisionMode']])))
            lines.extend('material\t' + path for path in part['Materials'])
        lines.append('end')
    return '\n'.join(lines) + '\n'


def read_inventory(path):
    raw = Path(path).read_bytes()
    inventory = strict_json(raw, MAX_RESPONSE)
    if type(inventory) is not dict or set(inventory) != {'target', 'installed_packs', 'available_assets'}:
        raise ValueError('Inventory must contain target, installed_packs and available_assets')
    target = inventory['target']
    if type(target) is not dict or set(target) != {'game_id','game_version','mod_id','mod_version','native_fingerprint'}:
        raise ValueError('Invalid target compatibility')
    if target.get('mod_id') != 'community.den-designer' or not all(type(v) is str for v in target.values()):
        raise ValueError('Invalid target values')
    if type(inventory['installed_packs']) is not dict or type(inventory['available_assets']) is not dict:
        raise ValueError('Invalid inventory maps')
    for key, version in inventory['installed_packs'].items():
        if not contract.ID.fullmatch(key) or type(version) is not str or not version:
            raise ValueError('Invalid installed pack')
    for path, kind in inventory['available_assets'].items():
        contract.asset(path)
        if kind not in ('mesh', 'material'):
            raise ValueError('Invalid inventory asset kind')
    return inventory


def atomic_response(mailbox, body):
    temporary = mailbox / 'response.tmp'
    temporary.write_text(body, encoding='ascii')
    os.replace(temporary, mailbox / 'response.txt')


async def serve(mailbox, inventory, transport=None):
    """Poll a fixed local mailbox. Removing/replacing a request cancels all work.

    No service URL or filesystem target ever comes from downloaded content. A
    response is published only while its exact fresh request remains current.
    """
    mailbox = Path(mailbox)
    mailbox.mkdir(parents=True, exist_ok=True)
    request_path = mailbox / 'request.json'
    transport = transport or HttpsTransport()
    task = None
    cancel = None
    current = None
    async def perform(request):
        token = request['token']
        try:
            result = await fetch_composition(request['input'], transport, cancel, inventory)
            body = response_text(token, result)
        except CommunityError as exc:
            body = response_text(token, error=exc)
        except (ValueError, KeyError, TypeError):
            body = response_text(token, error='Malformed Community response or local inventory.')
        # No await between freshness check and atomic publication.
        try:
            fresh = request_path.stat()
            matches = (fresh.st_size <= 1024 and
                       0 <= time.time() - fresh.st_mtime < TIMEOUT * 2 + 5 and
                       strict_json(request_path.read_bytes(), 1024) == request)
        except (OSError, ValueError):
            matches = False
        if current == request and matches:
            atomic_response(mailbox, body)
    try:
        while True:
            request = None
            try:
                stat = request_path.stat()
                if 0 <= time.time() - stat.st_mtime < TIMEOUT * 2 + 5 and stat.st_size <= 1024:
                    raw = request_path.read_bytes()
                    parsed = strict_json(raw, 1024)
                    if type(parsed) is dict and set(parsed) == {'token', 'input'} and type(parsed['token']) is str and TOKEN.fullmatch(parsed['token']) and type(parsed['input']) is str:
                        request = parsed
            except (OSError, ValueError):
                pass
            if request != current:
                if task:
                    cancel.set()
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                current = request
                task = None
                if request:
                    cancel = asyncio.Event()
                    task = asyncio.create_task(perform(request))
            await asyncio.sleep(.1)
    finally:
        if task:
            cancel.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mailbox', type=Path)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--http-child', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.http_child:
        try:
            sys.stdout.buffer.write(_http_get(args.http_child))
        except CommunityError as exc:
            sys.stdout.write(json.dumps({'code': exc.code, 'message': str(exc)}))
            return 1
        return 0
    if args.mailbox is None or args.inventory is None:
        parser.error('--mailbox and --inventory are required')
    try:
        asyncio.run(serve(args.mailbox, read_inventory(args.inventory)))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
