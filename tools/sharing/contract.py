"""Portable, data-only Den Designer contract. No network or public upload operations."""
import copy
import hashlib
import json
import math
import re

MAX_BYTES = 4 * 1024 * 1024
MAX_ENTRIES = 4096
ASSET = re.compile(r'/[A-Za-z0-9_]+/(?:[A-Za-z0-9_-]+/)*([A-Za-z0-9_-]+)\.\1\Z')
NATIVE = re.compile(r'/[A-Za-z0-9_]+/(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+\.[A-Za-z0-9_]+:PersistentLevel\.[A-Za-z0-9_.]+\Z')
ID = re.compile(r'[a-z][a-z0-9_-]{2,95}\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')
TYPES = ('den', 'composition', 'character')  # Character is reserved; no schema yet.
ENTRY_FIELDS = ('Kind', 'Key', 'Mesh', 'Position', 'Rotation', 'Scale', 'HasPosition',
                'HasRotation', 'HasScale', 'Hidden', 'CollisionMode', 'Materials',
                'HasFingerprint', 'FingerprintMesh', 'FingerprintPosition')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fields(obj, names):
    require(type(obj) is dict and set(obj) == set(names.split()), 'Unexpected or missing fields: ' + names)


def text(value, maximum=96, empty=False):
    require(type(value) is str and len(value) <= maximum and (empty or bool(value))
            and value == value.strip() and all(ord(c) >= 32 for c in value), 'Invalid text')


def asset(value, empty=False):
    require(type(value) is str and ((empty and value == '') or
            (len(value) <= 1023 and ASSET.fullmatch(value))), 'Invalid Unreal asset path')


def vector(value, positive=False):
    require(type(value) is list and len(value) == 3 and all(type(n) in (int, float)
            and math.isfinite(n) and (0 < n <= 1e7 if positive else -1e7 <= n <= 1e7)
            for n in value), 'Invalid transform vector')


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                          allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError('Not JSON data') from exc


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def loads(raw):
    require(type(raw) in (str, bytes) and len(raw if isinstance(raw, bytes) else raw.encode()) <= MAX_BYTES,
            'Payload exceeds byte limit')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON')))
        return validate(value)
    except (RecursionError, UnicodeError) as exc:
        raise ValueError('Invalid JSON encoding or nesting') from exc


def validate_entry(e, composition=False):
    fields(e, ' '.join(ENTRY_FIELDS))
    require(type(e['Kind']) is int and e['Kind'] in (0, 1, 2), 'Invalid entry kind')
    native = e['Kind'] == 2
    text(e['Key'], 1023)
    if native:
        require(NATIVE.fullmatch(e['Key']) and 'UEDPIE_' not in e['Key'], 'Native identity must be a cooked world object path')
    else:
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,96}', e['Key']), 'Invalid portable prop identity')
    asset(e['Mesh'], empty=native)
    for key in ('Position', 'Rotation', 'FingerprintPosition'):
        vector(e[key])
    vector(e['Scale'], positive=True)
    for key in ('HasPosition', 'HasRotation', 'HasScale', 'Hidden', 'HasFingerprint'):
        require(type(e[key]) is bool, 'Invalid boolean')
    require(type(e['CollisionMode']) is int and e['CollisionMode'] in (0, 1, 2), 'Invalid collision mode')
    require(type(e['Materials']) is list and len(e['Materials']) <= 64, 'Too many material slots')
    for path in e['Materials']:
        asset(path, empty=True)  # Empty slot means retain mesh default, not missing asset.
    asset(e['FingerprintMesh'], empty=not native)
    require(e['HasFingerprint'] == native, 'Native entries require fingerprints; props must not carry them')
    if not native:
        require(e['FingerprintMesh'] == '' and e['FingerprintPosition'] == [0, 0, 0], 'Unexpected prop fingerprint')
    if composition:
        require(e['Kind'] == 0 and not e['Hidden'] and all(e[k] for k in
                ('HasPosition', 'HasRotation', 'HasScale')), 'Composition parts must be visible, complete placed values')


def references(payload):
    result = {}
    for e in payload['entries']:
        for path, kind in [(e['Mesh'], 'mesh'), (e['FingerprintMesh'], 'mesh')] + [(p, 'material') for p in e['Materials']]:
            if path:
                require(path not in result or result[path] == kind, 'Asset used as both mesh and material')
                result[path] = kind
    return result


def validate(doc):
    require(len(canonical(doc)) <= MAX_BYTES, 'Payload exceeds byte limit')
    fields(doc, 'format schema_version content_type metadata compatibility dependencies payload integrity')
    require(doc['format'] == 'zcom-share' and type(doc['schema_version']) is int
            and doc['schema_version'] == 1, 'Unsupported sharing schema; preserve original')
    require(doc['content_type'] in TYPES[:2], 'Unsupported content type (character is reserved)')
    m = doc['metadata']
    fields(m, 'title description author media')
    text(m['title'], 120); text(m['description'], 4000, empty=True)
    fields(m['author'], 'id display_name')
    text(m['author']['id'], 128); text(m['author']['display_name'], 96)
    require(type(m['media']) is list and len(m['media']) <= 8, 'Too many media items')
    for media in m['media']:
        fields(media, 'id mime width height bytes sha256 alt')
        require(type(media['id']) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', media['id']), 'Invalid media ID')
        require(media['mime'] in ('image/png', 'image/jpeg', 'image/webp'), 'Unsupported media MIME')
        for k, limit in [('width', 8192), ('height', 8192), ('bytes', 10 * 1024 * 1024)]:
            require(type(media[k]) is int and 1 <= media[k] <= limit, 'Invalid media dimensions/size')
        require(type(media['sha256']) is str and HASH.fullmatch(media['sha256']), 'Invalid media hash')
        text(media['alt'], 512, empty=True)
    c = doc['compatibility']
    fields(c, 'game_id game_version mod_id mod_version native_fingerprint')
    for key in ('game_id', 'game_version', 'mod_id', 'mod_version'):
        text(c[key], 96)
    require(c['mod_id'] == 'community.den-designer', 'Wrong mod')
    require(type(c['native_fingerprint']) is str and (HASH.fullmatch(c['native_fingerprint'])
            if doc['content_type'] == 'den' else c['native_fingerprint'] == ''), 'Invalid native compatibility fingerprint')
    p = doc['payload']
    fields(p, 'entries anchor' if doc['content_type'] == 'composition' else 'entries')
    require(type(p['entries']) is list and len(p['entries']) <= (128 if doc['content_type'] == 'composition' else MAX_ENTRIES)
            and (bool(p['entries']) or doc['content_type'] == 'den'), 'Invalid entry count')
    if doc['content_type'] == 'composition':
        fields(p['anchor'], 'position convention')
        require(p['anchor']['convention'] == 'bounds-bottom-center', 'Unknown anchor convention')
        vector(p['anchor']['position'])
    seen = set()
    for e in p['entries']:
        validate_entry(e, doc['content_type'] == 'composition')
        identity = (2 if e['Kind'] == 2 else 0, e['Key'])
        require(identity not in seen, 'Duplicate placed/stored/native identity'); seen.add(identity)
    refs = references(p)
    deps = doc['dependencies']
    fields(deps, 'packs assets unknown_assets')
    require(type(deps['packs']) is list and len(deps['packs']) <= 32, 'Invalid packs')
    packs = {}
    for pack in deps['packs']:
        fields(pack, 'id version')
        require(type(pack['id']) is str and ID.fullmatch(pack['id']) and pack['id'] != 'game' and pack['id'] not in packs, 'Invalid/duplicate pack ID')
        text(pack['version']); packs[pack['id']] = pack['version']
    require(type(deps['assets']) is list and type(deps['unknown_assets']) is list, 'Invalid asset dependencies')
    found, used, identities = {}, set(), set()
    for a in deps['assets']:
        fields(a, 'path kind owner asset_id')
        asset(a['path']); text(a['asset_id'], 96)
        require(a['kind'] in ('mesh', 'material'), 'Invalid asset kind')
        require(type(a['owner']) is str and (a['owner'] == 'game' or a['owner'] in packs), 'Missing asset owner pack')
        require((a['owner'], a['asset_id']) not in identities, 'Duplicate asset identity')
        identities.add((a['owner'], a['asset_id']))
        require(a['path'] not in found, 'Duplicate asset dependency')
        found[a['path']] = a['kind']
        if a['owner'] != 'game': used.add(a['owner'])
    for a in deps['unknown_assets']:
        fields(a, 'path kind')
        asset(a['path']); require(a['path'] not in found, 'Duplicate unknown asset')
        found[a['path']] = a['kind']
    require(found == refs and used == set(packs), 'Dependencies must exactly cover referenced meshes and overrides')
    fields(doc['integrity'], 'algorithm payload_sha256')
    require(doc['integrity'] == {'algorithm': 'sha256', 'payload_sha256': digest(p)}, 'Payload integrity mismatch')
    return doc


def dependencies(payload, manifests, game_assets):
    """Ownership is explicit, never inferred from an installed plugin or mount prefix."""
    from tools.prop_packs.prop_pack import validate as validate_pack
    owners, versions, owned_paths = {}, {}, set()
    for a in game_assets:
        fields(a, 'id path kind')
        require(a['path'].casefold() not in owned_paths, 'Ambiguous asset ownership')
        owned_paths.add(a['path'].casefold())
        owners[a['path']] = dict(path=a['path'], kind=a['kind'], owner='game', asset_id=a['id'])
    for manifest in manifests:
        validate_pack(manifest)
        ident = manifest['id']
        require(ident != 'game' and ident not in versions, 'Conflicting installed pack IDs')
        versions[ident] = manifest['version']
        # Legacy schema 1 meshes have deterministic stable ownership IDs. Explicit
        # assets additionally describe materials and allow IDs to survive renames.
        assets = manifest.get('assets', [dict(id='legacy-' + hashlib.sha256(e['mesh'].encode()).hexdigest(), path=e['mesh'], kind='mesh') for e in manifest['props']])
        for a in assets:
            require(a['path'].casefold() not in owned_paths, 'Ambiguous asset ownership')
            owned_paths.add(a['path'].casefold())
            owners[a['path']] = dict(path=a['path'], kind=a['kind'], owner=ident, asset_id=a['id'])
    known, unknown, used = [], [], set()
    for path, kind in sorted(references(payload).items()):
        if path in owners:
            a = owners[path]
            require(a['kind'] == kind, 'Asset ownership type mismatch')
            known.append(a)
            if a['owner'] != 'game': used.add(a['owner'])
        else:
            unknown.append(dict(path=path, kind=kind))
    return dict(packs=[dict(id=i, version=versions[i]) for i in sorted(used)], assets=known, unknown_assets=unknown)


def native_fingerprint(native_inventory):
    """Inventory rows: cooked Key, original mesh and original position, not current pose."""
    rows = []
    seen = set()
    for row in native_inventory:
        fields(row, 'key mesh position')
        require(type(row['key']) is str and NATIVE.fullmatch(row['key']) and 'UEDPIE_' not in row['key']
                and row['key'] not in seen, 'Invalid/duplicate native identity')
        seen.add(row['key']); asset(row['mesh']); vector(row['position'])
        rows.append(row)
    return digest(sorted(rows, key=lambda r: r['key']))


def export_layout(local, content_type, metadata, compatibility, manifests=(), game_assets=(), anchor=None):
    """Migrate native SaveGame schema 1 through an allowlist; never serialize the save."""
    require(type(local.get('SchemaVersion')) is int and local['SchemaVersion'] == 1, 'Unsupported native save schema')
    require(content_type in TYPES[:2], 'Unsupported content type')
    entries = []
    for i, old in enumerate(local['Entries']):
        require(all(k in old for k in ENTRY_FIELDS), 'Incomplete native entry')
        e = {k: copy.deepcopy(old[k]) for k in ENTRY_FIELDS}
        # Local placed IDs and source labels have no portable meaning.
        if e['Kind'] in (0, 1): e['Key'] = 'prop-' + str(i)
        entries.append(e)
    p = dict(entries=entries)
    if content_type == 'composition':
        # Legacy saved compositions lost the capture anchor. Never guess it.
        if anchor is None and local.get('HasCompositionAnchor') is True:
            anchor = local.get('CompositionAnchor')
        require(anchor is not None, 'Composition export requires an explicit capture anchor')
        p['anchor'] = dict(position=copy.deepcopy(anchor), convention='bounds-bottom-center')
    doc = dict(format='zcom-share', schema_version=1, content_type=content_type,
               metadata=copy.deepcopy(metadata), compatibility=copy.deepcopy(compatibility), payload=p,
               dependencies=dependencies(p, manifests, game_assets),
               integrity=dict(algorithm='sha256', payload_sha256=digest(p)))
    return validate(doc)


def compatibility_issues(doc, target, installed_packs, available_assets):
    """Pure preflight. Assets must be verified loadable with the stated kind by the host."""
    validate(doc)
    issues = []
    for key, expected in doc['compatibility'].items():
        if expected and target.get(key) != expected: issues.append('compatibility:' + key)
    for p in doc['dependencies']['packs']:
        if installed_packs.get(p['id']) != p['version']: issues.append('pack:' + p['id'])
    for a in doc['dependencies']['assets'] + doc['dependencies']['unknown_assets']:
        if available_assets.get(a['path']) != a['kind']: issues.append('asset:' + a['path'])
    issues.extend('unknown-owner:' + a['path'] for a in doc['dependencies']['unknown_assets'])
    return issues


def import_layout(doc, target, installed_packs, available_assets):
    issues = compatibility_issues(doc, target, installed_packs, available_assets)
    require(not issues, 'Import blocked: ' + ', '.join(issues))
    # Fresh local document: routing/recovery metadata are supplied by the native store.
    local = dict(SchemaVersion=1, Entries=[dict(copy.deepcopy(e), Source='') for e in doc['payload']['entries']])
    if doc['content_type'] == 'composition':
        local.update(HasCompositionAnchor=True, CompositionAnchor=copy.deepcopy(doc['payload']['anchor']['position']))
    return local
