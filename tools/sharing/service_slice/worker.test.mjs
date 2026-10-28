import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import worker from './worker.js';
import {publishedTestItem, publishedTestDocument} from './published-composition.js';

const env = {DB:{prepare(){return {bind(){return this;},async first(){return null;},async all(){return {results:[]};}};}}, ASSETS:{async fetch(){return new Response('absent',{status:404});}}};
const base='https://share.zcom.app';
const get=(path,method='GET')=>worker.fetch(new Request(base+path,{method}),env);

test('versioned listing, download bytes and immutable digest match', async()=>{
 const r=await get('/api/v1/comp/DenDesignerTest01');
 assert.equal(r.status,200);
 const body=await r.json();
 assert.equal(body.api_version,'v1');assert.equal(body.fixture,false);
 assert.deepEqual(body.item,publishedTestItem);
 const download=await get('/api/v1/comp/DenDesignerTest01/document');
 assert.equal(download.status,200);assert.match(download.headers.get('content-type'),/^application\/json/);
 const bytes=Buffer.from(await download.arrayBuffer());
 assert.deepEqual(bytes,await readFile(new URL('./composition.json',import.meta.url)));
 assert.equal(bytes.length,body.item.document_bytes);
 assert.equal(download.headers.get('content-length'),String(bytes.length));
 assert.equal(createHash('sha256').update(bytes).digest('hex'),body.item.document_sha256);
 assert.equal(bytes.toString(),publishedTestDocument);
});

test('listing is discoverable in composition gallery and public detail',async()=>{
 const list=await (await get('/api/v1/compositions')).json();
 assert.equal(list.items[0].code,publishedTestItem.code);
 assert.equal(list.publishing_enabled,false);assert.equal(list.fixture,false);
 assert.equal((await (await get('/comp/DenDesignerTest01')).text()).includes(publishedTestItem.title),true);
 assert.equal((await (await get('/api/v1/dens')).json()).items.length,0);
});

test('HEAD preserves metadata while omitting document bytes',async()=>{
 const r=await get('/api/v1/comp/DenDesignerTest01/document','HEAD');
 assert.equal(r.status,200);assert.equal(await r.text(),'');
 assert.equal(r.headers.get('content-length'),String(publishedTestItem.document_bytes));
});

test('missing codes, wrong kind and malformed codes fail closed',async()=>{
 for(const path of ['/api/v1/comp/AbsentTest01','/api/v1/comp/AbsentTest01/document','/api/v1/den/DenDesignerTest01','/api/v1/den/DenDesignerTest01/document','/api/v2/comp/DenDesignerTest01/document']){
  const r=await get(path);assert.equal(r.status,404,path);
 }
 for(const path of ['/api/v1/comp/bad','/api/v1/comp/bad/document','/api/v1/comp/code%20bad/document']){
  assert.equal((await get(path)).status,400,path);
 }
});

test('all public mutations remain closed, including document and test listing',async()=>{
 for(const method of ['POST','PUT','PATCH','DELETE','OPTIONS']){
  for(const path of ['/api/v1/comp/DenDesignerTest01','/api/v1/comp/DenDesignerTest01/document','/api/v1/publish','/api/v1/uploads']){
   const r=await get(path,method);assert.equal(r.status,403);
   assert.equal((await r.json()).error.code,'WRITES_DISABLED');
  }
 }
});
