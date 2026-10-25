#!/usr/bin/env python3
"""Pak edition's persistent schema and Blueprint data operations.

Published struct/field identities are UUID5(path[:field]); never rename them to
change presentation. All runtime types use only engine classes and Blueprint VM.
"""
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from graph import Graph, variable as v, KML

ROOT = '/DenDesignerGF/Runtime/'
ENTRY = ROOT + 'ST_DenEntry'
MUTATION = ROOT + 'ST_DenMutation'
CHANGE = ROOT + 'ST_DenChange'
STEP = ROOT + 'ST_DenStep'
LAYOUT = ROOT + 'BP_DenLayoutSave'
ARRAY = '/Script/Engine.KismetArrayLibrary:'
STRING = '/Script/Engine.KismetStringLibrary:'


def struct(path, fields):
    return dict(kind='struct', path=path, guid=str(uuid.uuid5(uuid.NAMESPACE_URL, path)),
                fields=[dict(f, guid=str(uuid.uuid5(uuid.NAMESPACE_URL, path + ':' + f['name']))) for f in fields])


def arr(g, name, fn, target, **defaults):
    g.node(name, 'array_call', function=ARRAY + 'Array_' + fn,
           defaults={k: str(x) for k, x in defaults.items()})
    g.wire((target, name + '.TargetArray'))
    return name


def unpack(g, name, path, source):
    g.node(name, 'break_struct', struct=path)
    g.wire((source, name + '.' + path.rsplit('/', 1)[-1]))


def find_entry():
    g = Graph()
    g.get('entries', 'Entries')
    g.get('i', 'local:Cursor')
    g.get('found', 'local:Found')
    arr(g, 'length', 'Length', 'entries.Entries')
    g.call('within', KML + ':Less_IntInt')
    g.node('loop', 'branch')
    arr(g, 'item', 'Get', 'entries.Entries')
    unpack(g, 'fields', ENTRY, 'item.Item')
    g.call('kind', KML + ':EqualEqual_IntInt')
    g.call('key', STRING + 'EqualEqual_StrStr')
    g.call('both', KML + ':BooleanAND')
    g.node('match', 'branch')
    g.set('remember', 'local:Found')
    g.call('next', KML + ':Add_IntInt', B=1)
    g.set('advance', 'local:Cursor')
    g.wire(('i.Cursor', 'within.A'), ('length.ReturnValue', 'within.B'),
           ('within.ReturnValue', 'loop.Condition'), ('i.Cursor', 'item.Index'),
           ('fields.Kind', 'kind.A'), ('entry.Kind', 'kind.B'),
           ('fields.Key', 'key.A'), ('entry.Key', 'key.B'),
           ('kind.ReturnValue', 'both.A'), ('key.ReturnValue', 'both.B'),
           ('both.ReturnValue', 'match.Condition'), ('i.Cursor', 'remember.Found'),
           ('i.Cursor', 'next.A'), ('next.ReturnValue', 'advance.Cursor'),
           ('found.Found', 'result.Index'))
    g.chain('entry', 'loop', 'match', 'remember', 'result')
    g.chain('loop.else', 'result')
    g.chain('match.else', 'advance', 'loop')
    return g.function('FindEntry', inputs=[v('Kind', 'int'), v('Key', 'string')],
                      outputs=[v('Index', 'int')], locals=[v('Cursor', 'int', '0'), v('Found', 'int', '-1')])


def read_entry():
    g = Graph()
    g.get('entries', 'Entries')
    g.call('find', 'self:FindEntry')
    g.call('valid', KML + ':GreaterEqual_IntInt', B=0)
    g.node('has', 'branch')
    arr(g, 'item', 'Get', 'entries.Entries')
    g.set('value', 'local:ReadValue')
    g.set('exists', 'local:ReadExists', 'true')
    g.get('valueout', 'local:ReadValue')
    g.get('existsout', 'local:ReadExists')
    g.wire(('entry.Kind', 'find.Kind'), ('entry.Key', 'find.Key'),
           ('find.Index', 'valid.A'), ('valid.ReturnValue', 'has.Condition'),
           ('find.Index', 'item.Index'), ('item.Item', 'value.ReadValue'),
           ('valueout.ReadValue', 'result.Value'), ('existsout.ReadExists', 'result.Exists'))
    g.chain('entry', 'find', 'has', 'value', 'exists', 'result')
    g.chain('has.else', 'result')
    return g.function('ReadEntry', inputs=[v('Kind', 'int'), v('Key', 'string')],
                      outputs=[v('Exists', 'bool'), v('Value', 'struct:' + ENTRY)],
                      locals=[v('ReadExists', 'bool', 'false'), v('ReadValue', 'struct:' + ENTRY)])


def write_entry():
    # Value carries identity even when Present=false. Empty/invalid identities are
    # rejected without mutation. Semantic mesh/transform validation is a separate
    # boundary shared by import and editor commands.
    g = Graph()
    g.get('entries', 'Entries')
    unpack(g, 'fields', ENTRY, 'entry.Value')
    g.call('keyok', STRING + 'NotEqual_StriStri', B='')
    g.call('min', KML + ':GreaterEqual_IntInt', B=0)
    g.call('max', KML + ':LessEqual_IntInt', B=2)
    g.call('range', KML + ':BooleanAND')
    g.call('valid', KML + ':BooleanAND')
    g.node('guard', 'branch')
    g.call('find', 'self:FindEntry')
    g.call('exists', KML + ':GreaterEqual_IntInt', B=0)
    g.node('present', 'branch')
    g.node('replace', 'branch')
    g.node('remove', 'branch')
    arr(g, 'set', 'Set', 'entries.Entries', bSizeToFit='false')
    arr(g, 'add', 'Add', 'entries.Entries')
    arr(g, 'delete', 'Remove', 'entries.Entries')
    g.set('ok', 'local:WasAccepted', 'true')
    g.get('okout', 'local:WasAccepted')
    g.wire(('fields.Key', 'keyok.A'), ('fields.Kind', 'min.A'), ('fields.Kind', 'max.A'),
           ('min.ReturnValue', 'range.A'), ('max.ReturnValue', 'range.B'),
           ('range.ReturnValue', 'valid.A'), ('keyok.ReturnValue', 'valid.B'),
           ('valid.ReturnValue', 'guard.Condition'), ('fields.Kind', 'find.Kind'),
           ('fields.Key', 'find.Key'), ('find.Index', 'exists.A'),
           ('entry.Present', 'present.Condition'), ('exists.ReturnValue', 'replace.Condition'),
           ('exists.ReturnValue', 'remove.Condition'), ('find.Index', 'set.Index'),
           ('find.Index', 'delete.IndexToRemove'), ('entry.Value', 'set.Item'),
           ('entry.Value', 'add.NewItem'), ('okout.WasAccepted', 'result.Accepted'))
    g.chain('entry', 'guard', 'find', 'ok', 'present', 'replace', 'set', 'result')
    g.chain('guard.else', 'result')
    g.chain('replace.else', 'add', 'result')
    g.chain('present.else', 'remove', 'delete', 'result')
    g.chain('remove.else', 'result')
    return g.function('WriteEntry', inputs=[v('Value', 'struct:' + ENTRY), v('Present', 'bool')],
                      outputs=[v('Accepted', 'bool')], locals=[v('WasAccepted', 'bool', 'false')])


def apply_batch():
    # Work on a temporary layout. A rejected mutation must not leave half of a
    # store/restore or multi-object command in the live document.
    g = Graph()
    arr(g, 'length', 'Length', 'entry.Mutations')
    g.call('nonempty', KML + ':Greater_IntInt', B=0)
    g.node('start', 'branch')
    g.call('create', '/Script/Engine.GameplayStatics:CreateSaveGameObject', SaveGameClass=LAYOUT)
    g.node('cast', 'cast', **{'class': LAYOUT})
    g.set('scratch', 'local:Scratch')
    g.get('scratchget', 'local:Scratch')
    g.get('originals', 'Entries')
    g.set('copy', LAYOUT + ':Entries')
    g.get('i', 'local:Cursor')
    g.call('within', KML + ':Less_IntInt')
    g.node('loop', 'branch')
    arr(g, 'item', 'Get', 'entry.Mutations')
    unpack(g, 'mutation', MUTATION, 'item.Item')
    unpack(g, 'identity', ENTRY, 'mutation.Value')
    g.call('read', LAYOUT + ':ReadEntry')
    g.set('beforeid', 'local:Original')
    g.node('found', 'branch')
    g.set('beforevalue', 'local:Original')
    g.get('beforeget', 'local:Original')
    g.call('write', LAYOUT + ':WriteEntry')
    g.node('accepted', 'branch')
    g.get('changes', 'local:Captured')
    g.node('change', 'make_struct', struct=CHANGE)
    arr(g, 'append', 'Add', 'changes.Captured')
    g.call('next', KML + ':Add_IntInt', B=1)
    g.set('advance', 'local:Cursor')
    g.get('edited', LAYOUT + ':Entries')
    g.set('commit', 'Entries')
    g.set('ok', 'local:WasAccepted', 'true')
    g.get('okget', 'local:WasAccepted')
    g.wire(('length.ReturnValue', 'nonempty.A'), ('nonempty.ReturnValue', 'start.Condition'),
           ('create.ReturnValue', 'cast.Object'), ('cast.AsBP Den Layout Save', 'scratch.Scratch'),
           ('scratchget.Scratch', 'copy.self'), ('originals.Entries', 'copy.Entries'),
           ('i.Cursor', 'within.A'), ('length.ReturnValue', 'within.B'),
           ('within.ReturnValue', 'loop.Condition'), ('i.Cursor', 'item.Index'),
           ('scratchget.Scratch', 'read.self'), ('identity.Kind', 'read.Kind'), ('identity.Key', 'read.Key'),
           ('mutation.Value', 'beforeid.Original'), ('read.Exists', 'found.Condition'),
           ('read.Value', 'beforevalue.Original'), ('scratchget.Scratch', 'write.self'),
           ('mutation.Value', 'write.Value'), ('mutation.Present', 'write.Present'),
           ('write.Accepted', 'accepted.Condition'), ('read.Exists', 'change.BeforeExists'),
           ('beforeget.Original', 'change.Before'), ('mutation.Present', 'change.AfterExists'),
           ('mutation.Value', 'change.After'), ('change.ST_DenChange', 'append.NewItem'),
           ('i.Cursor', 'next.A'), ('next.ReturnValue', 'advance.Cursor'),
           ('scratchget.Scratch', 'edited.self'), ('edited.Entries', 'commit.Entries'),
           ('okget.WasAccepted', 'result.Accepted'), ('changes.Captured', 'result.Changes'))
    g.chain('entry', 'start', 'create', 'cast', 'scratch', 'copy', 'loop', 'read', 'beforeid', 'found', 'beforevalue', 'write', 'accepted', 'append', 'advance', 'loop')
    g.chain('found.else', 'write')
    g.chain('loop.else', 'commit', 'ok', 'result')
    g.chain('accepted.else', 'result')
    g.chain('start.else', 'result')
    g.chain('cast.CastFailed', 'result')
    return g.function('ApplyBatch', inputs=[v('Mutations', 'struct:' + MUTATION + '[]')],
                      outputs=[v('Accepted', 'bool'), v('Changes', 'struct:' + CHANGE + '[]')],
                      locals=[v('Scratch', 'object:' + LAYOUT), v('Cursor', 'int', '0'),
                              v('Original', 'struct:' + ENTRY), v('Captured', 'struct:' + CHANGE + '[]'),
                              v('WasAccepted', 'bool', 'false')])


def save_variables(entries_type, scope):
    return [v('SchemaVersion', 'int', '1'), v('StorageKey', 'string'), v('Scope', 'string', scope),
                   v('CampaignID', 'string'), v('Enabled', 'bool', 'true'), v('DisplayName', 'string'), v('GameVersion', 'string'),
                   v('Revision', 'int64', '0'), v('ContentID', 'string'),
                   v('DraftBaseRevision', 'int64', '0'), v('DraftBaseID', 'string'), v('WrittenAt', 'string'), v('IsDraft', 'bool', 'false'),
                   v('EntryCount', 'int', '0'), v('Entries', 'struct:' + entries_type + '[]'), v('WriteCompleteID', 'string')]


def specs():
    yield '01_ST_DenEntry', struct(ENTRY, [
        v('Kind', 'int'), v('Key', 'string'), v('Mesh', 'string'),
        v('Position', 'vector'), v('Rotation', 'rotator'), v('Scale', 'vector', '1,1,1'),
        v('HasPosition', 'bool'), v('HasRotation', 'bool'), v('HasScale', 'bool'),
        v('Hidden', 'bool'), v('CollisionMode', 'int'), v('Materials', 'string[]'),
        v('Source', 'string'), v('HasFingerprint', 'bool'), v('FingerprintMesh', 'string'),
        v('FingerprintPosition', 'vector')])
    yield '01b_ST_DenMutation', struct(MUTATION, [v('Value', 'struct:' + ENTRY), v('Present', 'bool')])
    yield '02_ST_DenChange', struct(CHANGE, [
        v('BeforeExists', 'bool'), v('Before', 'struct:' + ENTRY),
        v('AfterExists', 'bool'), v('After', 'struct:' + ENTRY)])
    yield '03_ST_DenStep', struct(STEP, [
        v('Label', 'string'), v('MergeKey', 'string'), v('Time', 'double'),
        v('BeforeVersion', 'int'), v('AfterVersion', 'int'), v('Changes', 'struct:' + CHANGE + '[]')])
    yield '04_BP_DenLayoutSave', dict(kind='blueprint', path=LAYOUT, parent='/Script/Engine.SaveGame',
        variables=save_variables(ENTRY, 'home'),
        functions=[find_entry(), read_entry(), write_entry(), apply_batch()])

    from runtime_history import spec as history_spec
    yield '05_BP_DenHistory', history_spec(ROOT, LAYOUT, ENTRY, MUTATION, CHANGE, STEP, arr, unpack)

    from runtime_store import spec as store_spec
    yield '06_BP_DenStore', store_spec(ROOT, LAYOUT)

    from runtime_layouts import spec as layouts_spec
    yield '07_BP_DenLayouts', layouts_spec(ROOT, LAYOUT)

    from runtime_presets import library_specs
    yield from library_specs(ROOT, LAYOUT, ENTRY, struct, save_variables, store_spec, arr, unpack)

    from runtime_preferences import specs as preferences_specs
    yield from preferences_specs()

    from runtime_world import specs as world_specs
    yield from world_specs()

    from runtime_assets import spec as asset_job_spec
    yield '15_BP_DenAssetJob',asset_job_spec()

    from runtime_apply import specs as apply_specs
    yield from apply_specs()

    from runtime_session import spec as session_spec
    yield '18_BP_DenSession',session_spec()

    from runtime_pick import specs as pick_specs
    yield from pick_specs()

    from runtime_compositions import types as composition_types
    yield from composition_types()

    from runtime_gizmo_math import spec as gizmo_math_spec
    yield '18c_BP_DenGizmoMath',gizmo_math_spec()

    from runtime_gizmo_visual import spec as gizmo_visual_spec
    yield '18d_BP_DenGizmoVisual',gizmo_visual_spec()

    from runtime_prop_packs import types as prop_pack_types
    yield from prop_pack_types()

    from runtime_catalog import specs as catalog_specs
    yield from catalog_specs()

    from runtime_thumbnails import studio_spec
    yield '18g_BP_DenThumbnailStudio',studio_spec()
    from runtime_thumbnail_queue import spec as thumbnail_queue_spec
    yield '18h_BP_DenThumbnails',thumbnail_queue_spec()

    from runtime_editor_assets import specs as editor_specs
    yield from editor_specs()

    from runtime_input_mappings import spec as input_mappings_spec
    yield '21z_BP_DenInputMappings',input_mappings_spec()

    from runtime_editor_host import spec as editor_host_spec
    yield '22_BP_DenEditorHost',editor_host_spec()

    from runtime_shortcut import spec as shortcut_spec
    yield '23_BP_DenShortcut',shortcut_spec()
    from runtime_coordinator import spec as coordinator_spec, notice_spec
    yield '24_WBP_DenStartupNotice',notice_spec()
    yield '25_BP_DenRuntimeCoordinator',coordinator_spec()


if __name__ == '__main__':
    target = Path(__file__).resolve().parents[1] / 'generated/runtime'
    target.mkdir(parents=True, exist_ok=True)
    written = set()
    for name, spec in specs():
        (target / (name + '.json')).write_text(json.dumps(spec, indent=2) + '\n')
        written.add(name + '.json')
    # A renumbered or removed spec must not be built from its old file.
    for stale in target.glob('*.json'):
        if stale.name not in written:
            stale.unlink()
    print(f'Generated native runtime specs in {target}')
