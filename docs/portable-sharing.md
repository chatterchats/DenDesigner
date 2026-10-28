# Portable sharing contract v1

This repository owns the data boundary between Den Designer and ZCom Community. The
implementation is `tools/sharing/contract.py`; `registry.py` and `registry.sql` are an
offline SQLite reference for Community persistence. The optional
[Community bridge](../distribution/community/README.md) now supplies a narrow read-only
test import; `community.py` is a broader reference client, not a player dependency.
There is **no public upload route or automatic publishing**. The future service must
authenticate authors, authorize listing edits, moderate media and rate-limit access.
The offline `publish` method is an internal persistence operation, not an authorization API.

Validate a portable file from the repository root:

```sh
python3 -m tools.sharing tests/fixtures/sharing/den-v1.json
python3 -m unittest discover -s tests/python -p '*_test.py'
```

## Source model and migration

The format follows `unreal/specs/runtime.py`'s `ST_DenEntry`, rather than serializing
SaveGame objects. `Kind=0` is a placed prop, `Kind=1` is a stored placed prop, and
`Kind=2` is a native scenery override. `runtime_storeroom.py` restores stored props
and hidden native scenery differently; these distinctions survive sharing.

`export_layout` migrates a **native schema 1 value snapshot** into portable schema 1.
The bridge supplies dictionaries with runtime field names and three-number lists
for vectors/rotators. Rotators use **Pitch, Yaw, Roll**, vectors use X, Y, Z; positions
are Unreal centimeters, angles degrees, scales dimensionless. This is a value bridge,
not a reader for binary `.sav` files. `import_layout` creates a fresh local schema 1
value snapshot after preflight; it does not apply world mutations or write save slots.
The native store remains responsible for routing, validation, local IDs and atomic saves.

Only the following entry fields cross the boundary:

- Kind, Key, Mesh, Position, Rotation, Scale
- HasPosition, HasRotation, HasScale, Hidden, CollisionMode, Materials
- HasFingerprint, FingerprintMesh, FingerprintPosition

Source labels are dropped and placed/stored keys are reassigned to deterministic,
payload-local IDs. Native identities are retained as cooked Unreal world object
paths, including actor/component suffixes after `:PersistentLevel.`. PIE paths are
rejected. Entry identity cannot overlap between placed and stored props. Native
entries require their original mesh and original position fingerprint. Native
fingerprints are meaningful even for hidden scenery with no transform overrides.
No campaign IDs, storage scope/keys, bank revisions, draft bases, recovery metadata,
local filesystem paths, credentials or preferences are copied. Unknown wire fields
are rejected recursively at each defined object boundary. Author IDs are public
Community identities; bridges must never substitute an account token or credential.

Native composition capture (`runtime_compositions.py`) takes visible copies of
selected components, including material slots, and subtracts the group bounds'
bottom-center anchor from each position. Rotation and scale stay on each part.
New captures persist `HasCompositionAnchor` and `CompositionAnchor` through native
clone/readback and `ST_DenPresetValue` library saves. These are additive native schema 1
fields, defaulting to false/zero for old saves. Old libraries load with no known
anchor; portable export requires a caller-supplied anchor or recapture, never guesses
one from offsets. Import restores the original anchor and relative parts; placement
can choose a different anchor using the existing preview transform pipeline.

## Envelope

All fields are mandatory, with exact key sets enforced by `validate` and `loads`.
The complete representative files are in `tests/fixtures/sharing/`.

| Field | Meaning |
|---|---|
| format | `zcom-share` |
| schema_version | Integer `1`, independent of native save and pack schemas |
| content_type | `den` or `composition`; `character` is reserved and rejected today |
| metadata | title, description, author `{id, display_name}`, media array |
| compatibility | game_id, game_version, mod_id, mod_version, native_fingerprint |
| dependencies | packs, assets, unknown_assets |
| payload | entries; compositions also include anchor |
| integrity | algorithm `sha256`, payload_sha256 |

`payload.anchor` is `{position: [x,y,z], convention: "bounds-bottom-center"}`.
Composition entries must all be kind 0, visible, with all transform flags true;
no native identities or fingerprints survive capture. Dens may have zero entries
(an unmodified Den), native overrides, placed props and stored props. Hidden flags
are preserved. Collision modes retain runtime values: 0 automatic, 1 solid,
2 no collision. Empty material slot strings mean retain the mesh default; array
order is material slot order and must not be compacted.

Media records are `{id, mime, width, height, bytes, sha256, alt}`. IDs are opaque
alphanumeric/underscore/hyphen storage references; there are no URLs, executable
markup or filesystem paths. Supported MIME values are PNG, JPEG and WebP. This
contract stores metadata, not image bytes. A future media store must verify the
bytes, dimensions, MIME and hash before associating an object with a revision.

Canonical hashing is SHA-256 of UTF-8 JSON with sorted object keys, compact
separators, unescaped Unicode, finite numbers only, and original array order
(`canonical`). Producers must match these exact number encodings; this is not an
RFC 8785 claim. Portable integrity covers **payload only** and is corruption
detection, not authentication or a signature. The reference registry additionally
hashes the complete envelope and checks it at resolution. Duplicate JSON keys,
NaN/Infinity and unsupported future schemas fail closed. Original newer-version
files should be retained unchanged for a newer reader; do not attempt downgrade.
There is no fabricated legacy portable or Character schema. Future migrations
must explicitly validate the source, transform to a new document and recompute
integrity, leaving published original bytes and codes unchanged.

## Dependencies and compatibility

Pack manifests already have stable `id` and `version`. Schema 1 now optionally adds
an explicit `assets` inventory with `{id, path, kind}` records. Asset IDs use the
same lowercase stable ID syntax as pack IDs and survive renames. Paths belong to
the pack plugin; kind is `mesh` or `material`. IDs and paths are unique within a
pack, and an explicit inventory must include every catalog mesh. This extension
is validated by both CLI and editor authoring models and retained in `Authoring/pack.json`.
Both pack export paths ship an allowlisted `<Plugin>.pack.json` ownership sidecar
beside their containers; existing runtime catalog providers remain compatible.
The editor cook inventory checker verifies declared ownership assets were cooked.
Materials used as overrides must be declared even if no catalog row advertises them.
Examples are in the template and example manifests.

For older manifests, `dependencies` derives mesh ownership from catalog rows and
uses `legacy-` plus SHA-256 of the path as the asset ID. Such derived IDs change
when paths change; migrate to explicit IDs before a rename. Legacy material
ownership is unknown until the creator adds it. Game assets require an explicit
trusted inventory `{id, path, kind}`; `/Game/` alone is not evidence of ownership.
Duplicate installed pack IDs and ambiguous asset ownership are rejected.

Dependency scanning visits only the entry mesh, fingerprint mesh and every
nonempty material slot, **including stored and hidden entries**. It never requires
an unrelated installed pack or every asset in a used pack. Pack dependencies are
`{id, version}`; known assets are `{path, kind, owner, asset_id}`, with owner `game`
or a pack ID. Unowned references are explicit `{path, kind}` entries in
`unknown_assets`. Validation requires dependencies to cover exactly the referenced
assets and no unrelated packs. The caller supplies trusted manifests; creator
claims must not replace independently verified installed-pack metadata.

Preflight is conservative and atomic:

- Game ID/build and Den Designer mod ID/version must match exactly. Mod ID is the
  shipped `community.den-designer`. Versions are opaque exact strings, not guessed
  SemVer ranges. A future policy can introduce reviewed ranges in a new schema.
- Dens also require an exact native compatibility fingerprint. `native_fingerprint`
  hashes a sorted complete inventory of cooked native keys, original mesh paths
  and original positions. The trusted host must capture this inventory before
  applying changes, including hidden/stored scenery; current edited poses are wrong.
  Compositions carry an empty native fingerprint and do not bind scenery identities.
- Every required pack ID must be installed at the recorded version. Every referenced
  asset must also be independently verified loadable as its recorded mesh/material
  kind. A correct pack version alone does not prove its files are present.
- Unknown ownership blocks import, even if an asset happens to load. The author can
  resolve the metadata and create a new revision. Missing assets, wrong kinds,
  changed builds and mismatched fingerprints are reported as distinct issue strings.

The reference `available_assets` map is supplied by the host's load/type checks;
it is not a check of mere mount names or catalog membership. `installed_packs`
is the verified ID-to-version map. Import rejects all issues before returning any
local entries. No partial application, silent dropping of stored props, best-effort
native identity rebinding or execution of payload-provided classes/scripts occurs.
The local runtime's unique mesh/original-position fallback (`runtime_refind.py`,
2 cm per-axis tolerance) remains a local recovery mechanism, not permission to
bypass portable compatibility preflight.

## Listing identity and immutable revisions

A listing has an opaque stable UUID, fixed author ID and content type. Each
publication creates another immutable revision with its own UUID, ordinal,
timestamp, complete envelope, schema version and whole-document hash. Thus titles,
descriptions, display names, compatibility, dependencies and media are revision
snapshots. Code resolution always returns the exact published revision, even when
the listing later has a newer revision. There is no mutable "latest" code.

Codes contain 32 case-sensitive ASCII alphanumeric characters sampled with
`secrets.choice` (approximately 190 bits of cryptographic entropy). They encode
no type, author or sequential identity. A **single UNIQUE database constraint**
on `revisions.share_code`, shared by all content types, enforces uniqueness.
Publication retries code collisions up to eight times, then rolls back. It does
not swallow other constraint failures. `BEGIN IMMEDIATE` serializes revision
allocation across SQLite connections. Database triggers forbid changing or
deleting published revisions and changing listing identity. Resolve accepts only
a code, with no content type parameter. Registry migration 0→1 installs the schema;
reopening version 1 preserves data; newer registry versions are rejected. There
is intentionally no schema for Character Share yet.

## Bounds

| Resource | Limit |
|---|---:|
| Portable JSON (UTF-8, canonical or input bytes) | 4 MiB |
| Full Den entries | 4,096 |
| Composition parts | 1–128 (matches runtime capture) |
| Materials per entry | 64, preserving empty slots |
| Referenced packs | 32 (matches runtime discovery) |
| Pack catalog props / explicit owned assets | 2,048 / 8,192 |
| Asset/native object path | 1,023 characters |
| Title / description | 120 / 4,000 characters |
| Media records | 8 |
| Media object bytes / width / height | 10 MiB / 8,192 / 8,192 |
| Transform components | finite, magnitude ≤ 10,000,000 |
| Scale components | strictly positive, ≤ 10,000,000 |

The Full Den and byte limits are portable transport bounds, not a claim that
placing thousands of props is performant. Transport implementations must bound
request bodies before parsing. Readers must use `loads` for strict duplicate-key,
byte and finite-number checks, then run preflight before importing.
