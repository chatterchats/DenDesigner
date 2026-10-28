"""Standalone preferences schema, validation and bounded recent-asset history.

String keys/values are intentionally independent of widget labels and localized
key display names. The ordinary rotating store provides the persistence envelope.
Preferences use native mod SaveGame slots.
"""
from graph import Graph, variable as v, KML
from runtime import ROOT, arr, unpack, struct, save_variables
from runtime_store import call, branch, combine, STR, spec as store_spec

ROW = ROOT + 'ST_DenPreference'
DOCUMENT = ROOT + 'BP_DenPreferencesSave'
STORE = ROOT + 'BP_DenPreferencesStore'
BINDINGS = [
    ('key_forward', 'IA_Den_Move', 'W', 'Fly forward'),
    ('key_back', 'IA_Den_Move', 'S', 'Fly back'),
    ('key_left', 'IA_Den_Move', 'A', 'Fly left'),
    ('key_right', 'IA_Den_Move', 'D', 'Fly right'),
    ('key_up', 'IA_Den_Move', 'SpaceBar', 'Fly up'),
    ('key_down', 'IA_Den_Move', 'LeftControl', 'Fly down'),
    ('key_fast', 'IA_Den_Fast', 'LeftShift', 'Fly fast / fine turns / lift while dragging'),
    ('key_turn_left', 'IA_Den_Rotate', 'Q', 'Turn left'),
    ('key_turn_right', 'IA_Den_Rotate', 'E', 'Turn right'),
    ('key_store', 'IA_Den_Store', 'X', 'Store'),
    ('key_copy', 'IA_Den_Duplicate', 'C', 'Copy'),
    ('key_undo', 'IA_Den_Undo', 'Z', 'Undo'),
    ('key_redo', 'IA_Den_Redo', 'Y', 'Redo'),
    ('key_focus', 'IA_Den_Focus', 'F', 'Focus selection'),
    ('key_reset', 'IA_Den_Reset', 'R', 'Reset'),
    ('key_snap', 'IA_Den_Snap', 'G', 'Grid snap'),
    ('key_catalog', 'IA_Den_Catalog', 'Tab', 'Catalog'),
    ('key_storeroom', 'IA_Den_Storeroom', 'H', 'Storeroom'),
    ('key_layouts', 'IA_Den_Layouts', 'L', 'Layouts'),
    ('key_gimbal', 'IA_Den_Gimbal', 'T', 'Gizmo mode'),
]
DIGITS = ['Zero', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine']
MODIFIERS = ['LeftShift', 'RightShift', 'LeftControl', 'RightControl', 'LeftAlt', 'RightAlt']
KEY_NAMES = [*'ABCDEFGHIJKLMNOPQRSTUVWXYZ', *DIGITS, *['NumPad'+x for x in DIGITS],
             *['F'+str(i) for i in range(1,13)], 'BackSpace', 'Tab', 'Enter', 'Pause', 'CapsLock',
             'SpaceBar', 'End', 'Home', 'Insert', 'Multiply', 'Decimal', 'Divide', 'Semicolon',
             'Comma', 'Period', 'Slash', 'Tilde', 'LeftBracket', 'Backslash', 'RightBracket',
             'Apostrophe', *MODIFIERS]
# Alt is the fixed neighbour-snap bypass. Other fixed editing keys are absent from KEY_NAMES.
# F9 collided with an existing load/mod action during the OS-input regression.
# Keep it decodable for old preferences, but reject it as a new assignment.
RESERVED_KEYS = {'F9'}
EDITOR_KEYS = [key for key in KEY_NAMES if key not in ('LeftAlt', 'RightAlt') and key not in RESERVED_KEYS]
TOGGLE_KEYS = [key for key in KEY_NAMES if key not in MODIFIERS and key not in RESERVED_KEYS]
NUMBERS = {'fly_speed': ('900', 200, 3000), 'fast_multiplier': ('3', 1, 8), 'look_speed': ('2.5', .5, 10), 'snap_distance': ('8', 2, 30)}
CHOICES = {
    'toggle_key': ('Home', TOGGLE_KEYS),
    'toggle_modifier': ('ctrl', ['ctrl', 'shift', 'alt', 'none']),
    'snap': ('0', ['0', '5', '10', '25', '50']),
    'reach': ('2000', ['1000', '2000', '4000', '10000']),
    'gimbal': ('move', ['move', 'rotate', 'scale', 'off']),
    'rotation_pivot': ('centre', ['centre', 'bottom', 'top', 'origin']),
    'unlock_structure': ('false', ['false', 'true']),
    'select_floors': ('true', ['false', 'true']),
    'select_walls': ('false', ['false', 'true']),
    'autosave': ('true', ['false', 'true']),
    'thumbnails': ('true', ['false', 'true']),
    'neighbour_snap': ('true', ['false', 'true']),
    'snap_guides': ('true', ['false', 'true']),
    **{key: (default, EDITOR_KEYS) for key, _, default, _ in BINDINGS},
}
DEFAULTS = {**{key: row[0] for key, row in NUMBERS.items()}, **{key: row[0] for key, row in CHOICES.items()}}
RECENT_LIMIT = 40
RECENT_KEYS = ['recent_'+str(i).zfill(2) for i in range(RECENT_LIMIT)]


def output(g, name, kind, default=None):
    g.get('out'+name, 'local:Result'+name)
    g.wire(('out'+name+'.Result'+name, 'result.'+name))
    return v('Result'+name, kind, default)


def enum(g, name, source, values):
    return combine(g, name+'any', [call(g, name+str(i), STR+'EqualEqual_StrStr', {'A':source}, B=value)
                                 for i,value in enumerate(values)], True)


def defaults():
    g=Graph();previous='entry'
    for i,(key,value) in enumerate({**DEFAULTS, **{k:'' for k in RECENT_KEYS}}.items()):
        ident='key'+str(i)
        branch(g,ident,call(g,ident+'eq',STR+'EqualEqual_StrStr',{'A':'entry.Key'},B=key))
        g.set(ident+'value','local:ResultValue',value)
        g.chain(previous,ident,ident+'value','known');previous=ident+'.else'
    g.set('known','local:ResultKnown','true');g.chain('known','result');g.chain(previous,'result')
    return g.function('PreferenceDefault',inputs=[v('Key','string')],outputs=[v('Value','string'),v('Known','bool')],
                      locals=[output(g,'Value','string'),output(g,'Known','bool','false')])


def valid_mesh():
    g=Graph();length=call(g,'length',STR+'Len',{'S':'entry.Path'})
    checks=[call(g,'min',KML+':Greater_IntInt',{'A':length},B=3),call(g,'max',KML+':LessEqual_IntInt',{'A':length},B=1024),
            call(g,'root',STR+'StartsWith',{'SourceString':'entry.Path'},InPrefix='/'),
            call(g,'dot',STR+'Contains',{'SearchIn':'entry.Path'},Substring='.',bUseCase='true')]
    for i,bad in enumerate([' ', '\t', '\r', '\n', ':', '..', "'", '"', '\\']):
        present=call(g,'bad'+str(i),STR+'Contains',{'SearchIn':'entry.Path'},Substring=bad,bUseCase='true')
        checks.append(call(g,'clean'+str(i),KML+':Not_PreBool',{'A':present}))
    g.wire((combine(g,'valid',checks),'result.Valid'));g.chain('entry','result')
    return g.function('ValidRecentMesh',inputs=[v('Path','string')],outputs=[v('Valid','bool')])


def validate():
    from runtime_transform import decimal, number
    g=Graph();previous='entry'
    # Shared choice validation avoids reproducing the entire keyboard whitelist
    # for every action in the generated Blueprint.
    branch(g,'binding',enum(g,'bindingkey','entry.Key',[x[0] for x in BINDINGS]))
    valid=enum(g,'keyboard','entry.Value',EDITOR_KEYS)
    g.set('bindingvalid','local:ResultValid');g.wire((valid,'bindingvalid.ResultValid'))
    g.chain(previous,'binding','bindingvalid','result');previous='binding.else'
    for i,(key,(_,values)) in enumerate(CHOICES.items()):
        if key.startswith('key_'):continue
        ident='choice'+str(i)
        branch(g,ident,call(g,ident+'key',STR+'EqualEqual_StrStr',{'A':'entry.Key'},B=key))
        g.set(ident+'valid','local:ResultValid');g.wire((enum(g,ident+'values','entry.Value',values),ident+'valid.ResultValid'))
        g.chain(previous,ident,ident+'valid','result');previous=ident+'.else'
    for i,(key,(_,lo,hi)) in enumerate(NUMBERS.items()):
        ident='number'+str(i)
        branch(g,ident,call(g,ident+'key',STR+'EqualEqual_StrStr',{'A':'entry.Key'},B=key))
        g.call(ident+'parse','self:ParseTransformNumber');g.wire(('entry.Value',ident+'parse.Text'))
        low=call(g,ident+'low',KML+':GreaterEqual_DoubleDouble',{'A':ident+'parse.Value'},B=lo)
        high=call(g,ident+'high',KML+':LessEqual_DoubleDouble',{'A':ident+'parse.Value'},B=hi)
        g.set(ident+'valid','local:ResultValid');g.wire((combine(g,ident+'ok',[ident+'parse.Valid',low,high]),ident+'valid.ResultValid'))
        g.chain(previous,ident,ident+'parse',ident+'valid','result');previous=ident+'.else'
    branch(g,'recent',enum(g,'recentkey','entry.Key',RECENT_KEYS))
    g.call('mesh','self:ValidRecentMesh');g.wire(('entry.Value','mesh.Path'))
    empty=call(g,'empty',STR+'EqualEqual_StrStr',{'A':'entry.Value'},B='')
    g.set('recentvalid','local:ResultValid');g.wire((combine(g,'recentok',[empty,'mesh.Valid'],True),'recentvalid.ResultValid'))
    g.chain(previous,'recent','mesh','recentvalid','result');g.chain('recent.else','result')
    return [decimal(),number(),valid_mesh(),g.function('ValidatePreference',inputs=[v('Key','string'),v('Value','string')],
            outputs=[v('Valid','bool')],locals=[output(g,'Valid','bool','false')])]


def find():
    g=Graph();g.get('rows','Entries');g.get('i','local:Cursor');arr(g,'length','Length','rows.Entries')
    branch(g,'loop',call(g,'within',KML+':Less_IntInt',{'A':'i.Cursor','B':'length.ReturnValue'}))
    arr(g,'row','Get','rows.Entries');g.wire(('i.Cursor','row.Index'));unpack(g,'fields',ROW,'row.Item')
    branch(g,'same',call(g,'equal',STR+'EqualEqual_StrStr',{'A':'entry.Key','B':'fields.Key'}))
    g.set('found','local:ResultIndex');g.wire(('i.Cursor','found.ResultIndex'))
    g.set('next','local:Cursor');g.wire((call(g,'add',KML+':Add_IntInt',{'A':'i.Cursor'},B=1),'next.Cursor'))
    g.chain('entry','loop','same','found','result');g.chain('loop.else','result');g.chain('same.else','next','loop')
    return g.function('FindPreference',inputs=[v('Key','string')],outputs=[v('Index','int')],locals=[v('Cursor','int','0'),output(g,'Index','int','-1')])


def read():
    g=Graph();g.call('default','self:PreferenceDefault');g.wire(('entry.Key','default.Key'))
    g.set('fallback','local:ResultValue');g.wire(('default.Value','fallback.ResultValue'),('default.Known','result.Known'));branch(g,'known','default.Known')
    g.call('find','self:FindPreference');g.wire(('entry.Key','find.Key'))
    branch(g,'exists',call(g,'found',KML+':GreaterEqual_IntInt',{'A':'find.Index'},B=0))
    g.get('rows','Entries');arr(g,'row','Get','rows.Entries');g.wire(('find.Index','row.Index'));unpack(g,'fields',ROW,'row.Item')
    g.call('validate','self:ValidatePreference');g.wire(('entry.Key','validate.Key'),('fields.Value','validate.Value'));branch(g,'valid','validate.Valid')
    g.set('value','local:ResultValue');g.wire(('fields.Value','value.ResultValue'));g.set('override','local:ResultOverride','true')
    g.chain('entry','default','fallback','known','find','exists','validate','valid','value','override','result')
    for pin in ['known.else','exists.else','valid.else']:g.chain(pin,'result')
    return g.function('ReadPreference',inputs=[v('Key','string')],outputs=[v('Value','string'),v('Known','bool'),v('Override','bool')],
                      locals=[output(g,'Value','string'),output(g,'Override','bool','false')])


def binding_available():
    g=Graph();branch(g,'binding',enum(g,'bindingkey','entry.Key',[x[0] for x in BINDINGS]))
    branch(g,'toggle',call(g,'togglekey',STR+'EqualEqual_StrStr',{'A':'entry.Key'},B='toggle_key'))
    g.call('togglevalue','self:ReadPreference',Key='toggle_key')
    branch(g,'toggleclash',call(g,'togglesame',STR+'EqualEqual_StrStr',{'A':'entry.Value','B':'togglevalue.Value'}))
    g.node('compare','sequence',outputs=1)
    g.chain('entry','binding','togglevalue','toggleclash','result');g.chain('toggleclash.else','compare')
    g.chain('binding.else','toggle','compare');g.chain('toggle.else','yes')
    previous='compare.then_0'
    for i,(key,_,_,_) in enumerate(BINDINGS):
        ident='other'+str(i);g.call(ident,'self:ReadPreference',Key=key)
        notself=call(g,ident+'notself',STR+'NotEqual_StrStr',{'A':'entry.Key'},B=key)
        same=call(g,ident+'same',STR+'EqualEqual_StrStr',{'A':'entry.Value','B':ident+'.Value'})
        branch(g,ident+'clash',combine(g,ident+'clashes',[notself,same]));g.chain(previous,ident,ident+'clash','result');previous=ident+'clash.else'
    g.set('yes','local:ResultAvailable','true');g.chain(previous,'yes','result')
    return g.function('BindingAvailable',inputs=[v('Key','string'),v('Value','string')],outputs=[v('Available','bool')],locals=[output(g,'Available','bool','false')])


def write():
    g=Graph();g.call('validate','self:ValidatePreference');g.wire(('entry.Key','validate.Key'),('entry.Value','validate.Value'));branch(g,'valid','validate.Valid')
    g.call('available','self:BindingAvailable');g.wire(('entry.Key','available.Key'),('entry.Value','available.Value'));branch(g,'free','available.Available')
    g.call('find','self:FindPreference');g.wire(('entry.Key','find.Key'));g.set('yes','local:ResultAccepted','true')
    branch(g,'exists',call(g,'found',KML+':GreaterEqual_IntInt',{'A':'find.Index'},B=0))
    g.get('rows','Entries');arr(g,'row','Get','rows.Entries');g.wire(('find.Index','row.Index'));unpack(g,'fields',ROW,'row.Item')
    branch(g,'same',call(g,'equal',STR+'EqualEqual_StrStr',{'A':'fields.Value','B':'entry.Value'}))
    g.node('value','make_struct',struct=ROW);g.wire(('entry.Key','value.Key'),('entry.Value','value.Value'))
    arr(g,'replace','Set','rows.Entries',bSizeToFit='false');g.wire(('find.Index','replace.Index'),('value.ST_DenPreference','replace.Item'))
    arr(g,'append','Add','rows.Entries');g.wire(('value.ST_DenPreference','append.NewItem'))
    g.call('default','self:PreferenceDefault');g.wire(('entry.Key','default.Key'))
    branch(g,'isdefault',call(g,'defaultsame',STR+'EqualEqual_StrStr',{'A':'entry.Value','B':'default.Value'}))
    g.set('changed','local:ResultChanged','true')
    g.chain('entry','validate','valid','available','free','find','yes','exists','same','result')
    g.chain('same.else','replace','changed','result');g.chain('exists.else','default','isdefault','result');g.chain('isdefault.else','append','changed')
    for pin in ['valid.else','free.else']:g.chain(pin,'result')
    return g.function('WritePreference',inputs=[v('Key','string'),v('Value','string')],outputs=[v('Accepted','bool'),v('Changed','bool')],
                      locals=[output(g,'Accepted','bool','false'),output(g,'Changed','bool','false')])


def recents():
    g=Graph();g.get('paths','local:ResultPaths');previous='entry'
    for i,key in enumerate(RECENT_KEYS):
        ident='r'+str(i);g.call(ident,'self:ReadPreference',Key=key)
        branch(g,ident+'has',call(g,ident+'nonempty',STR+'NotEqual_StrStr',{'A':ident+'.Value'},B=''))
        arr(g,ident+'add','AddUnique','paths.ResultPaths');g.wire((ident+'.Value',ident+'add.NewItem'))
        g.node(ident+'done','sequence',outputs=1);g.chain(previous,ident,ident+'has',ident+'add',ident+'done');g.chain(ident+'has.else',ident+'done');previous=ident+'done.then_0'
    g.chain(previous,'result');g.wire(('paths.ResultPaths','result.Paths'))
    read=g.function('RecentMeshes',outputs=[v('Paths','string[]')],locals=[v('ResultPaths','string[]')])
    g=Graph();g.call('valid','self:ValidRecentMesh');g.wire(('entry.Path','valid.Path'));branch(g,'allowed','valid.Valid')
    g.call('read','self:RecentMeshes');g.get('paths','local:NewPaths');arr(g,'first','Add','paths.NewPaths');g.wire(('entry.Path','first.NewItem'))
    g.get('i','local:Cursor');arr(g,'length','Length','read.Paths');branch(g,'loop',call(g,'within',KML+':Less_IntInt',{'A':'i.Cursor','B':'length.ReturnValue'}))
    arr(g,'row','Get','read.Paths');g.wire(('i.Cursor','row.Index'));arr(g,'append','AddUnique','paths.NewPaths');g.wire(('row.Item','append.NewItem'))
    g.set('next','local:Cursor');g.wire((call(g,'add',KML+':Add_IntInt',{'A':'i.Cursor'},B=1),'next.Cursor'))
    g.chain('entry','valid','allowed','read','first','loop','append','next','loop');g.chain('allowed.else','result')
    arr(g,'count','Length','paths.NewPaths');previous='loop.else'
    for i,key in enumerate(RECENT_KEYS):
        ident='r'+str(i);branch(g,ident+'exists',call(g,ident+'within',KML+':Greater_IntInt',{'A':'count.ReturnValue'},B=i))
        arr(g,ident+'value','Get','paths.NewPaths',Index=i);g.call(ident+'write','self:WritePreference',Key=key);g.wire((ident+'value.Item',ident+'write.Value'))
        g.call(ident+'clear','self:WritePreference',Key=key,Value='');g.node(ident+'done','sequence',outputs=1)
        g.chain(previous,ident+'exists',ident+'write',ident+'done');g.chain(ident+'exists.else',ident+'clear',ident+'done');previous=ident+'done.then_0'
    g.set('yes','local:ResultAccepted','true');g.chain(previous,'yes','result')
    remember=g.function('RememberMesh',inputs=[v('Path','string')],outputs=[v('Accepted','bool')],
                        locals=[v('Cursor','int','0'),v('NewPaths','string[]'),output(g,'Accepted','bool','false')])
    return [read,remember]


def specs():
    yield '11a_ST_DenPreference',struct(ROW,[v('Key','string'),v('Value','string')])
    yield '11b_BP_DenPreferencesSave',dict(kind='blueprint',path=DOCUMENT,parent='/Script/Engine.SaveGame',
        variables=save_variables(ROW,'preferences'),
        functions=[defaults(),*validate(),find(),read(),binding_available(),write(),*recents()])
    yield '11c_BP_DenPreferencesStore',store_spec(ROOT,DOCUMENT,'BP_DenPreferencesStore','AsBP Den Preferences Save','Preferences')
    from runtime_preference_service import spec as service_spec
    yield '11d_BP_DenPreferences',service_spec()
    from runtime_key_names import spec as keys_spec
    yield '11e_BP_DenKeyNames',keys_spec()

