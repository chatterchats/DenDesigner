"""Community transport, validation and cancellation checks; no live service calls."""
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.sharing import community as c
from tools.sharing import contract


class FakeTransport:
    def __init__(self, doc=None):
        self.document = doc or json.loads((ROOT/'tests/fixtures/sharing/composition-v1.json').read_text())
        self.raw = contract.canonical(self.document)
        self.metadata = {'api_version':'v1', 'item':{'code':'TestCode01', 'kind':'comp',
            'schema_version':1, 'document_sha256':hashlib.sha256(self.raw).hexdigest(),
            'document_bytes':len(self.raw)}}
        self.calls = []
        self.failure = None
    async def get(self, url, cancel):
        c.approved_url(url)
        self.calls.append(url)
        if self.failure:
            raise self.failure
        return self.raw if url.endswith('/document') else json.dumps(self.metadata).encode()


def inventory(doc):
    return {'target':dict(doc['compatibility']),
        'installed_packs':{p['id']:p['version'] for p in doc['dependencies']['packs']},
        'available_assets':{a['path']:a['kind'] for a in doc['dependencies']['assets']}}


class CommunityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.transport = FakeTransport()
        self.cancel = asyncio.Event()
        self.inventory = inventory(self.transport.document)

    async def fetch(self):
        return await c.fetch_composition('TestCode01', self.transport, self.cancel, self.inventory)

    async def test_validated_native_values_and_dependencies(self):
        result = await self.fetch()
        self.assertEqual(len(self.transport.calls), 2)
        self.assertEqual(self.transport.calls[1], c.ORIGIN+'/api/v1/comp/TestCode01/document')
        self.assertEqual(result.local['CompositionAnchor'], [500,600,0])
        self.assertEqual(result.local['Entries'][0]['Materials'][0], '')
        self.assertTrue(all(e['Source'] == '' for e in result.local['Entries']))
        self.assertIn('finishes-pack@2.0.0', result.report)
        self.assertNotIn('StorageKey', result.local)
        wire = c.response_text('a'*32, result)
        self.assertTrue(wire.startswith('ZCOM-COMMUNITY\t1\t'+'a'*32+'\nok\n'))
        self.assertIn('material\t\n', wire)
        self.assertTrue(wire.endswith('\nend\n'))
        self.assertTrue(wire.isascii())

    async def test_dependency_failure_reports_and_returns_no_values(self):
        self.inventory['installed_packs'] = {}
        with self.assertRaises(c.CommunityError) as raised:
            await self.fetch()
        self.assertEqual(raised.exception.code, 'DEPENDENCIES')
        self.assertIn('pack:finishes-pack', str(raised.exception))
        wire = c.response_text('b'*32, error=raised.exception)
        self.assertNotIn('\npart\t', wire)
        self.assertNotIn('\nanchor\t', wire)

    async def test_missing_offline_and_timeout_have_structured_errors(self):
        for code in ('NOT_FOUND', 'OFFLINE', 'TIMEOUT'):
            self.transport.failure = c.CommunityError(code, code)
            with self.assertRaises(c.CommunityError) as raised:
                await self.fetch()
            self.assertEqual(raised.exception.code, code)
            self.assertEqual(len(self.transport.calls), 1)
            self.transport.calls.clear()

    async def test_schema_and_metadata_reject_before_download(self):
        for value in (2, True, '1', None):
            self.transport.metadata['item']['schema_version'] = value
            with self.assertRaises(c.CommunityError) as raised:
                await self.fetch()
            self.assertEqual(raised.exception.code, 'UNSUPPORTED_SCHEMA')
            self.assertEqual(len(self.transport.calls), 1)
            self.transport.calls.clear()
        self.transport.metadata['item']['schema_version'] = 1
        del self.transport.metadata['item']['document_sha256']
        with self.assertRaises(c.CommunityError) as raised:
            await self.fetch()
        self.assertEqual(raised.exception.code, 'DOWNLOAD_UNAVAILABLE')

    async def test_listing_identity_api_and_full_document_integrity(self):
        for field, value, expected in [('code','DifferentCode','MALFORMED'),
                                     ('kind','den','MALFORMED'),
                                     ('document_bytes',1,'INTEGRITY'),
                                     ('document_sha256','0'*64,'INTEGRITY')]:
            original = self.transport.metadata['item'][field]
            self.transport.metadata['item'][field] = value
            with self.assertRaises(c.CommunityError) as raised:
                await self.fetch()
            self.assertEqual(raised.exception.code, expected)
            self.transport.metadata['item'][field] = original
        self.transport.metadata['api_version'] = 'v2'
        with self.assertRaises(c.CommunityError) as raised:
            await self.fetch()
        self.assertEqual(raised.exception.code, 'UNSUPPORTED_API')

    async def test_bad_payload_with_correct_download_digest_still_rejected(self):
        self.transport.document['payload']['entries'][0]['Mesh'] = '/tmp/evil.py'
        self.transport.raw = contract.canonical(self.transport.document)
        item = self.transport.metadata['item']
        item['document_bytes'] = len(self.transport.raw)
        item['document_sha256'] = hashlib.sha256(self.transport.raw).hexdigest()
        with self.assertRaises(c.CommunityError) as raised:
            await self.fetch()
        self.assertEqual(raised.exception.code, 'INVALID_DOCUMENT')

    async def test_cancel_during_resolution_never_downloads(self):
        original = self.transport.get
        async def cancelled(url, event):
            raw = await original(url, event)
            event.set()
            return raw
        self.transport.get = cancelled
        with self.assertRaises(asyncio.CancelledError):
            await self.fetch()
        self.assertEqual(len(self.transport.calls), 1)

    async def test_process_is_terminated_on_total_deadline_and_cancel(self):
        real_spawn = asyncio.create_subprocess_exec
        children = []
        async def spawn(*args, **kwargs):
            process = await real_spawn(sys.executable, '-c', 'import time; time.sleep(60)',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            children.append(process)
            return process
        with patch.object(c.asyncio, 'create_subprocess_exec', spawn):
            with self.assertRaises(c.CommunityError) as raised:
                await c.HttpsTransport(.05).get(c.ORIGIN+'/api/v1/comp/TestCode01', self.cancel)
            self.assertEqual(raised.exception.code, 'TIMEOUT')
            self.assertIsNotNone(children[-1].returncode)
            task = asyncio.create_task(c.HttpsTransport().get(c.ORIGIN+'/api/v1/comp/TestCode01', self.cancel))
            await asyncio.sleep(.05)
            self.cancel.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertIsNotNone(children[-1].returncode)

    async def test_mailbox_publishes_complete_response_and_removal_cancels(self):
        with tempfile.TemporaryDirectory() as folder:
            mailbox = Path(folder)
            path = mailbox/'request.json'
            task = asyncio.create_task(c.serve(mailbox, self.inventory, self.transport))
            try:
                path.write_text(json.dumps({'token':'a'*32, 'input':'TestCode01'}))
                for _ in range(30):
                    if (mailbox/'response.txt').exists(): break
                    await asyncio.sleep(.02)
                self.assertIn('\nok\n', (mailbox/'response.txt').read_text())
                path.unlink()
                await asyncio.sleep(.15)
                self.assertEqual(len(self.transport.calls), 2)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


    async def test_removed_pending_request_cancels_without_late_response(self):
        started, stopped = asyncio.Event(), asyncio.Event()
        class WaitingTransport:
            async def get(self, url, cancel):
                started.set()
                try:
                    await asyncio.sleep(60)
                except asyncio.CancelledError:
                    stopped.set()
                    raise
        with tempfile.TemporaryDirectory() as folder:
            mailbox = Path(folder)
            path = mailbox/'request.json'
            path.write_text(json.dumps({'token':'c'*32, 'input':'TestCode01'}))
            task = asyncio.create_task(c.serve(mailbox, self.inventory, WaitingTransport()))
            try:
                await asyncio.wait_for(started.wait(), 1)
                path.unlink()
                await asyncio.wait_for(stopped.wait(), 1)
                self.assertFalse((mailbox/'response.txt').exists())
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


class ParsingTests(unittest.TestCase):
    def test_only_approved_links_and_codes(self):
        for value in ('ABC_123-', 'https://zcom.app/comp/ABC_123-',
                      'https://share.zcom.app/comp/ABC_123-/'):
            self.assertEqual(c.code_from_input(value), 'ABC_123-')
        for value in ('abc','file:///comp/ABC123','http://zcom.app/comp/ABC123',
                      'https://share.zcom.app.evil.test/comp/ABC123',
                      'https://evil.test@share.zcom.app/comp/ABC123',
                      'https://share.zcom.app:443/comp/ABC123',
                      'https://zcom.app/comp/ABC123?x=1',
                      'https://zcom.app/comp/ABC123#x',
                      'https://zcom.app/comp/%41BC123',
                      'https://zcom.app/den/ABC123', '\u0430bc123'):
            with self.subTest(value=value), self.assertRaises(c.CommunityError):
                c.code_from_input(value)
        for url in ('https://zcom.app/api/v1/comp/ABC123',
                    c.ORIGIN+'/api/v2/comp/ABC123',
                    c.ORIGIN+'/api/v1/comp/ABC123/document?url=evil',
                    c.ORIGIN+'/api/v1/comp/ABC123/../../other'):
            with self.assertRaises(c.CommunityError): c.approved_url(url)

    def test_strict_json_rejects_duplicate_nonfinite_and_encoding(self):
        for raw in (b'{"a":1,"a":2}', b'{"n":NaN}', b'\xff', b'{', b'['*1100):
            with self.assertRaises(c.CommunityError): c.strict_json(raw, 4096)
        with self.assertRaises(c.CommunityError): c.strict_json(b' '*20, 10)

    def test_http_redirect_compression_framing_size_and_truncation_rejected(self):
        from email.message import Message
        class Response:
            status = 200
            headers = Message()
            def read(self, size): return b'{}'
        class Connection:
            def __init__(self, *args, **kwargs): pass
            def request(self, *args, **kwargs): pass
            def getresponse(self): return response
            def close(self): pass
        cases = [(302, {'Content-Type':'application/json'}, 'HTTP_ERROR'),
                 (404, {}, 'NOT_FOUND'), (200, {'Content-Type':'text/html'}, 'CONTENT_TYPE'),
                 (200, {'Content-Type':'application/json','Content-Encoding':'gzip'}, 'ENCODING'),
                 (200, {'Content-Type':'application/json','Content-Length':str(c.MAX_RESPONSE+1)}, 'TOO_LARGE'),
                 (200, {'Content-Type':'application/json','Content-Length':'3'}, 'TRUNCATED'),
                 (200, {'Content-Type':'application/json','Transfer-Encoding':'gzip'}, 'FRAMING'),
                 (200, {'Content-Type':'application/json','Content-Length':'2','Transfer-Encoding':'chunked'}, 'FRAMING')]
        for status, headers, expected in cases:
            response = Response(); response.status = status; response.headers = Message()
            for key, value in headers.items(): response.headers[key] = value
            with patch.object(c.http.client, 'HTTPSConnection', Connection), self.assertRaises(c.CommunityError) as raised:
                c._http_get(c.ORIGIN+'/api/v1/comp/TestCode01/document')
            self.assertEqual(raised.exception.code, expected)


if __name__ == '__main__':
    unittest.main()
