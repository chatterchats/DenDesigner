#!/usr/bin/env python3
"""Prepare a reviewable Community worker extension; never writes the source service."""
import argparse
import difflib
import hashlib
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent


def patched_worker(source):
    edits = [
        ("import { securityHeaders } from './security.js';", "import { securityHeaders } from './security.js';\nimport { publishedTestItem, findPublishedTest, publishedTestDocumentResponse } from './published-composition.js';"),
        ("async function findShare(env, kind, code, fixture) {", "async function findShare(env, kind, code, fixture) {\n if (!fixture) { const item = findPublishedTest(kind, code); if (item) return item; }"),
        (" const category = Object.entries(categories).find", " const document = publishedTestDocumentResponse(path, securityHeaders);\n if (document) return document;\n const category = Object.entries(categories).find"),
        ("   return json({api_version:'v1', items, fixture, publishing_enabled:false, limit:24});", "   if (!fixture && kind === 'comp') {\n     const duplicate = items.findIndex(item => item.code === publishedTestItem.code);\n     if (duplicate >= 0) items.splice(duplicate, 1);\n     items.unshift(publishedTestItem);\n     items.length = Math.min(items.length, 24);\n   }\n   return json({api_version:'v1', items, fixture, publishing_enabled:false, limit:24});"),
    ]
    for before, after in edits:
        if source.count(before) != 1:
            raise ValueError('Worker changed; review integration manually: ' + before)
        source = source.replace(before, after, 1)
    return source


def prepare(service, output):
    service = service.resolve()
    output = output.resolve()
    if output.exists():
        raise ValueError('Use a new output directory')
    source = (service / 'src/worker.js').read_text()
    changed = patched_worker(source)
    output.mkdir(parents=True)
    (output / 'worker.js').write_text(changed)
    shutil.copyfile(HERE / 'published-composition.js', output / 'published-composition.js')
    patch = ''.join(difflib.unified_diff(source.splitlines(True), changed.splitlines(True), fromfile='a/src/worker.js', tofile='b/src/worker.js'))
    upstream_test = (service / 'test/worker.test.js').read_text()
    updated_test = upstream_test.replace("import { detail } from '../src/views.js';", "import { detail } from '../src/views.js';\nimport { publishedTestItem } from '../src/published-composition.js';")
    updated_test = updated_test.replace('galleries are empty, bounded, and expose no private object keys', 'galleries include only the reviewed test plus published data, bounded with no private object keys')
    updated_test = updated_test.replace('assert.deepEqual(b.items,[]);', "assert.deepEqual(b.items,path === 'compositions' ? [publishedTestItem] : []);")
    updated_test = updated_test.replace('assert.deepEqual((await prod.json()).items,[]);', 'assert.deepEqual((await prod.json()).items,[publishedTestItem]);')
    if updated_test == upstream_test:
        raise ValueError('Upstream test changed; review tests manually')
    (output / 'upstream-worker.test.js').write_text(updated_test)
    patch += ''.join(difflib.unified_diff(upstream_test.splitlines(True), updated_test.splitlines(True), fromfile='a/test/worker.test.js', tofile='b/test/worker.test.js'))
    verifier = (service / 'scripts/verify.mjs').read_text()
    updated_verifier = verifier.replace("['/api/v1/compositions',200,'\"items\":[]']", "['/api/v1/compositions',200,'DenDesignerTest01']")
    updated_verifier = updated_verifier.replace('assert.deepEqual(fixture.items,[]);', "assert.equal(fixture.items.some(item=>item.code==='DenDesignerTest01'),true);")
    if updated_verifier == verifier:
        raise ValueError('Upstream verifier changed; review verification manually')
    (output / 'verify.mjs').write_text(updated_verifier)
    patch += ''.join(difflib.unified_diff(verifier.splitlines(True), updated_verifier.splitlines(True), fromfile='a/scripts/verify.mjs', tofile='b/scripts/verify.mjs'))
    (output / 'worker.patch').write_text(patch)
    (output / 'source.sha256').write_text(hashlib.sha256(source.encode()).hexdigest() + '  src/worker.js\n')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(prepare(args.service, args.output))
