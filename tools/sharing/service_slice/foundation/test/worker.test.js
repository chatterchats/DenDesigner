import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../src/worker.js';
import { fixtureEnabled } from '../src/catalog.js';
import { detail } from '../src/views.js';
const env = {
 ENVIRONMENT:'production', FIXTURE_MODE:'false',
 DB:{prepare(sql){assert.ok(!/INSERT|UPDATE|DELETE/i.test(sql));return {bind(){return this;},async all(){return {results:[]};},async first(){return null;}};}},
 ASSETS:{async fetch(){return new Response('missing',{status:404});}}
};
const get=(path,options={},bindings=env)=>worker.fetch(new Request('https://share.zcom.app'+path,options),bindings);
test('health probes D1, reports closed writes and missing R2',async()=>{
 const r=await get('/api/v1/health'); assert.equal(r.status,200);const b=await r.json();assert.equal(b.status,'ok');assert.equal(b.writes_enabled,false);assert.equal(b.services.files,'not-configured');
});
test('galleries are empty, bounded, and expose no private object keys',async()=>{
 for(const path of ['compositions','dens','characters']){const r=await get('/api/v1/'+path);assert.equal(r.status,200);const b=await r.json();assert.deepEqual(b.items,[]);assert.equal(b.fixture,false);assert.equal(b.limit,24);}
});
test('every API mutation is blocked before DB access',async()=>{
 for(const method of ['POST','PUT','PATCH','DELETE','OPTIONS']) for(const path of ['/api/v1/publish','/api/v1/uploads','/api/v1/health','/api/v1/compositions','/api/anything']){const r=await get(path,{method},{...env,DB:null});assert.equal(r.status,403);assert.equal((await r.json()).error.code,'WRITES_DISABLED');}
});
test('fixtures require explicit development mode AND loopback host',async()=>{
 for(const host of ['share.zcom.app','zcom-share.ryan-64b.workers.dev','localhost.evil.example']) assert.equal(fixtureEnabled(new Request('https://'+host),{ENVIRONMENT:'development',FIXTURE_MODE:'true'}),false);
 assert.equal(fixtureEnabled(new Request('http://localhost'),{ENVIRONMENT:'production',FIXTURE_MODE:'true'}),false);
 const r=await worker.fetch(new Request('http://localhost/api/v1/compositions'),{...env,ENVIRONMENT:'development',FIXTURE_MODE:'true'});
 const b=await r.json();assert.equal(b.fixture,true);assert.equal(b.items.length,1);assert.match(b.items[0].description,/not a community upload/);
 const prod=await get('/api/v1/compositions?fixture=true',{},{...env,FIXTURE_MODE:'true'});assert.deepEqual((await prod.json()).items,[]);
});
test('detail routes distinguish invalid codes, missing shares and reserved routes',async()=>{
 for(const kind of ['comp','den','char']){assert.equal((await get('/'+kind+'/abc')).status,400);assert.equal((await get('/'+kind+'/absent123')).status,404);assert.equal((await get('/api/v1/'+kind+'/abc')).status,400);assert.equal((await get('/api/v1/'+kind+'/absent123')).status,404);}
 for(const path of ['/account','/publish','/moderation','/api/v1/accounts','/api/v1/uploads','/api/v1/moderation'])assert.equal((await get(path)).status,501);
 assert.equal((await get('/unmapped')).status,404);assert.equal((await get('/api/v2/health')).status,404);
});
test('published metadata only; draft data never requested; HTML escapes stored text',async()=>{
 const item={kind:'comp',code:'valid123',title:'<script>alert(1)</script>',description:'<img src=x onerror=alert(1)>',schema_version:1};
 const db={prepare(sql){assert.match(sql,/status = 'published'/);return {bind(kind,code){assert.equal(kind,'comp');assert.equal(code,'valid123');return this;},async first(){return item;}};}};
 const r=await get('/comp/valid123',{}, {...env,DB:db});assert.equal(r.status,200);const body=await r.text();assert.ok(!body.includes('<script>alert'));assert.match(body,/&lt;script&gt;/);assert.ok(!detail(item,false).includes('<img src=x'));
});
test('database failures return safe 503 responses, never stack traces or empty success',async()=>{
 const broken={...env,DB:{prepare(){throw new Error('SECRET INTERNAL ERROR');}}};
 for(const path of ['/api/v1/health','/api/v1/compositions','/comp/valid123']) {const r=await get(path,{},broken);assert.equal(r.status,503);assert.ok(!(await r.text()).includes('SECRET INTERNAL'));}
});
test('HEAD has GET status and security headers with no body',async()=>{
 const r=await get('/api/v1/health',{method:'HEAD'});assert.equal(r.status,200);assert.equal(await r.text(),'');assert.equal(r.headers.get('x-content-type-options'),'nosniff');assert.match(r.headers.get('content-security-policy'),/frame-ancestors 'none'/);
});
