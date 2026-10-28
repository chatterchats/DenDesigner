// Reviewed, data-only maintainer publication. There is no public upload path.
// Generated from composition.json and listing.json; served bytes are immutable.
export const publishedTestDocument = "{\"compatibility\":{\"game_id\":\"steam:2075800\",\"game_version\":\"25898267\",\"mod_id\":\"community.den-designer\",\"mod_version\":\"1.1.0-preview.19\",\"native_fingerprint\":\"\"},\"content_type\":\"composition\",\"dependencies\":{\"assets\":[{\"asset_id\":\"den-control-monitor-a\",\"kind\":\"mesh\",\"owner\":\"game\",\"path\":\"/Game/Game/Environments/Strategy/HQ/Props/Control/Control_Monitor_A.Control_Monitor_A\"}],\"packs\":[],\"unknown_assets\":[]},\"format\":\"zcom-share\",\"integrity\":{\"algorithm\":\"sha256\",\"payload_sha256\":\"995bc4e5c878814326ec10f63a0ed8d2f68ad0877c63315a3ba63a58b456d2d0\"},\"metadata\":{\"author\":{\"display_name\":\"Den Designer\",\"id\":\"den-designer-maintainer\"},\"description\":\"Maintainer test composition: one Den control monitor. No prop packs required.\",\"media\":[],\"title\":\"Community test monitor\"},\"payload\":{\"anchor\":{\"convention\":\"bounds-bottom-center\",\"position\":[0,0,0]},\"entries\":[{\"CollisionMode\":0,\"FingerprintMesh\":\"\",\"FingerprintPosition\":[0,0,0],\"HasFingerprint\":false,\"HasPosition\":true,\"HasRotation\":true,\"HasScale\":true,\"Hidden\":false,\"Key\":\"prop-0\",\"Kind\":0,\"Materials\":[],\"Mesh\":\"/Game/Game/Environments/Strategy/HQ/Props/Control/Control_Monitor_A.Control_Monitor_A\",\"Position\":[0,0,0],\"Rotation\":[0,0,0],\"Scale\":[1,1,1]}]},\"schema_version\":1}";
export const publishedTestItem = Object.freeze({"code":"DenDesignerTest01","kind":"comp","title":"Community test monitor","description":"Maintainer test composition: one Den control monitor. No prop packs required.","schema_version":1,"published_at":"2026-10-26T00:00:00Z","document_sha256":"299a9d44f498cea6a7053501c9054779ef26dc4534520cc4b3718420c40977c1","document_bytes":1235});

export function findPublishedTest(kind, code) {
  return kind === 'comp' && code === publishedTestItem.code ? publishedTestItem : null;
}

export function publishedTestDocumentResponse(path, headers) {
  const match = path.match(/^\/api\/v1\/comp\/([^/]+)\/document$/);
  if (!match) return null;
  if (!/^[A-Za-z0-9_-]{6,32}$/.test(match[1])) {
    return new Response(JSON.stringify({api_version:'v1', error:{code:'INVALID_CODE', message:'Invalid share code.'}}),
      {status:400, headers:{...headers, 'Content-Type':'application/json; charset=utf-8', 'Cache-Control':'no-store'}});
  }
  if (match[1] !== publishedTestItem.code) {
    return new Response(JSON.stringify({api_version:'v1', error:{code:'SHARE_NOT_FOUND', message:'This composition is unavailable or has not been published.'}}),
      {status:404, headers:{...headers, 'Content-Type':'application/json; charset=utf-8', 'Cache-Control':'no-store'}});
  }
  return new Response(publishedTestDocument, {status:200, headers:{...headers,
    'Content-Type':'application/json; charset=utf-8', 'Content-Length':String(publishedTestItem.document_bytes),
    'Cache-Control':'no-store', 'ETag':'"'+publishedTestItem.document_sha256+'"'}});
}
