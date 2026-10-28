import { categories, codePattern, fixtures, fixtureEnabled } from './catalog.js';
import { message, detail } from './views.js';
import { securityHeaders } from './security.js';

const fields = 'code, kind, title, description, schema_version, published_at';
function json(data, status = 200, extra = {}) {
 return new Response(JSON.stringify(data), { status, headers: { ...securityHeaders, 'Content-Type':'application/json; charset=utf-8', 'Cache-Control':'no-store', ...extra } });
}
const error = (status, code, text) => json({ api_version: 'v1', error: { code, message: text } }, status);
function html(body, status = 200) { return new Response(body, {status, headers:{ ...securityHeaders, 'Content-Type':'text/html; charset=utf-8', 'Cache-Control':'no-store' }}); }
async function findShare(env, kind, code, fixture) {
 if (fixture) return fixtures.find(i => i.kind === kind && i.code === code) || null;
 return env.DB.prepare(`SELECT ${fields} FROM shares WHERE kind = ? AND code = ? AND status = 'published'`).bind(kind, code).first();
}
async function api(request, env, path, fixture) {
 if (!['GET','HEAD'].includes(request.method)) {
   // No configuration switch can enable production mutations in this stage.
   return error(403, 'WRITES_DISABLED', 'Publishing is closed until authentication and upload validation are implemented.');
 }
 if (path === '/api/v1/health') {
   try { await env.DB.prepare('SELECT code FROM shares LIMIT 1').all(); }
   catch { return error(503,'DATABASE_UNAVAILABLE','Metadata storage is temporarily unavailable. Please try again later.'); }
   return json({ api_version:'v1', status:'ok', stage:'foundation', writes_enabled:false, fixture_mode:fixture, services:{ metadata:'ready', files:env.FILES ? 'bound-private' : 'not-configured' } });
 }
 if (path === '/api/v1') return json({api_version:'v1', endpoints:['/api/v1/health','/api/v1/compositions','/api/v1/dens','/api/v1/characters'], writes_enabled:false});
 if (/^\/api\/v1\/(accounts?|auth|publish|uploads?|moderation)(\/|$)/.test(path)) return error(501,'NOT_IMPLEMENTED','This route is reserved for a future sharing stage.');
 const category = Object.entries(categories).find(([,c])=>'/api/v1'+c.path === path);
 if (category) {
   const [kind] = category;
   const items=fixture ? fixtures.filter(i=>i.kind===kind) : (await env.DB.prepare(`SELECT ${fields} FROM shares WHERE kind = ? AND status = 'published' ORDER BY published_at DESC, id DESC LIMIT 24`).bind(kind).all()).results;
   return json({api_version:'v1', items, fixture, publishing_enabled:false, limit:24});
 }
 const match=path.match(/^\/api\/v1\/(comp|den|char)\/([^/]+)$/);
 if(match) {
   if(!codePattern.test(match[2])) return error(400,'INVALID_CODE','Share codes contain 6–32 letters, numbers, underscores or hyphens.');
   const item=await findShare(env,match[1],match[2],fixture);
   return item ? json({api_version:'v1',item,fixture}) : error(404,'SHARE_NOT_FOUND','This share is unavailable or has not been published.');
 }
 return error(404,'NOT_FOUND','This API endpoint does not exist. Try /api/v1.');
}
async function handle(request, env) {
 const url = new URL(request.url), path=url.pathname.replace(/\/+$/,'') || '/';
 const fixture=fixtureEnabled(request,env);
 if(path === '/api' || path.startsWith('/api/')) return api(request,env,path,fixture);
 if(!['GET','HEAD'].includes(request.method)) return html(message('This action is unavailable.','Publishing is closed while accounts and secure uploads are being built.','405 / METHOD NOT ALLOWED'),405);
 if(/^\/(accounts?|auth|publish|moderation)(\/|$)/.test(path)) return html(message('Coming in a future transmission.','Accounts, publishing and moderation are reserved for a future update. Public sharing is not open yet.'),501);
 const match=path.match(/^\/(comp|den|char)\/([^/]+)$/);
 if(match) {
   if(!codePattern.test(match[2])) return html(message('This share code looks incomplete.','Check the link and try again. Share codes use 6–32 letters, numbers, underscores or hyphens.','400 / INVALID SHARE CODE',match[1]),400);
   const item=await findShare(env,match[1],match[2],fixture);
   return item ? html(detail(item,fixture)) : html(message('This creation is out of range.','It may not have been published, or the link may have changed. Check the share code or explore the collection.','404 / SHARE NOT FOUND',match[1]),404);
 }
 if(path === '/comp' || path === '/den' || path === '/char') return Response.redirect(new URL(categories[path.slice(1)].path,url),308);
 // Existing static files are normally served before the Worker. This fallback
 // also supports tests and requests explicitly routed to the Worker.
 const asset=await env.ASSETS.fetch(request);
 if(asset.status!==404) return asset;
 return html(message('You’ve drifted off the map.','This page does not exist. Head back to the community to find your next destination.','404 / SIGNAL NOT FOUND'),404);
}
export default {
 async fetch(request,env) {
   let response;
   try { response=await handle(request,env); }
   catch { response=new URL(request.url).pathname.startsWith('/api') ? error(503,'SERVICE_UNAVAILABLE','The archive is temporarily unavailable. Please try again later.') : html(message('The archive is temporarily offline.','Please try again shortly. Your link may still be valid.','503 / PLEASE STAND BY'),503); }
   return request.method==='HEAD' ? new Response(null,{status:response.status,headers:response.headers}) : response;
 }
};
