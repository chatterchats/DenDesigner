import assert from 'node:assert/strict';
const base=process.argv[2]||'http://127.0.0.1:8787';
const cases=[['/',200,'ZCom Community'],['/compositions',200,'No public compositions'],['/dens',200,'No public dens'],['/characters',200,'No public characters'],['/about',200,'independent fan project'],['/comp/missing123',404,'out of range'],['/den/missing123',404,'out of range'],['/char/missing123',404,'out of range'],['/comp/bad',400,'incomplete'],['/account',501,'future transmission'],['/publish',501,'future transmission'],['/moderation',501,'future transmission'],['/missing-page',404,'off the map'],['/assets/site.css',200,'color-scheme:dark'],['/assets/gallery.js',200,'fixture'],['/api/v1/health',200,'"status":"ok"'],['/api/v1/compositions',200,'"items":[]'],['/api/v1/dens',200,'"items":[]'],['/api/v1/characters',200,'"items":[]'],['/api/v1/comp/missing123',404,'SHARE_NOT_FOUND'],['/api/v1/den/missing123',404,'SHARE_NOT_FOUND'],['/api/v1/char/missing123',404,'SHARE_NOT_FOUND'],['/api/v1/char/bad',400,'INVALID_CODE'],['/api/v2/health',404,'NOT_FOUND'],['/api/v1/uploads',501,'NOT_IMPLEMENTED']];
for(const [path,status,text] of cases){
 const r=await fetch(base+path);assert.equal(r.status,status,`${path} status`);assert.ok((await r.text()).includes(text),`${path} content`);assert.equal(r.headers.get('x-content-type-options'),'nosniff',`${path} security header`);console.log('PASS',status,path);
}
for(const method of ['POST','PUT','PATCH','DELETE']){
 const r=await fetch(base+'/api/v1/publish',{method,body:'{}'});assert.equal(r.status,403);console.log('PASS writes closed',method);
}
const fixture=await (await fetch(base+'/api/v1/compositions?fixture=true')).json();assert.equal(fixture.fixture,false);assert.deepEqual(fixture.items,[]);
const head=await fetch(base+'/api/v1/health',{method:'HEAD'});assert.equal(head.status,200);assert.equal(await head.text(),'');
console.log(`Verified ${cases.length+6} checks against ${base}`);
