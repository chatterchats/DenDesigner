"""Ordered editor mutations while native world application is asynchronous.

Selection identity is copied when input arrives. Delayed commands cannot edit a
subsequently selected object. Save/undo/redo retain their order with input edits.
"""
from graph import Graph, variable as v, KML
from runtime import arr, unpack
from runtime_store import call, branch, combine, STR
from runtime_world import set_value, finish_bool
from runtime_apply import get, clear
from runtime_pick import FACT
from runtime_editor_assets import EVENT

FIELDS={'set_x':'X','set_y':'Y','set_z':'Z','set_pitch':'Pitch','set_yaw':'Yaw','set_roll':'Roll','set_scale':'Scale'}
TRANSFORMS=[*FIELDS,'rotate','rotate_fine','scale','nudge','store','reset','duplicate','focus']
GLOBAL=['save','undo','redo','exit']
STOREROOM=['restore','restore_all','forget']
COMPOSITIONS=['save_composition','load_composition','delete_composition']
PRESETS=['save_preset','load_preset','delete_preset','scope']


def clear_queue():
    g=Graph();previous='entry'
    for name in ['EditEvents','EditKeys','EditKinds']:
        clear(g,name,name);g.chain(previous,name);previous=name
    g.set('copyclear','PendingCopyKey','');g.set('identityclear','CopySourceKey','');g.chain(previous,'copyclear','identityclear')
    return g.function('ClearEditorMutations')


def enqueue():
    g=Graph();branch(g,'selection','entry.RequireSelection');branch(g,'selected',get(g,'HasSelection'))
    unpack(g,'facts',FACT,get(g,'Selected'));set_value(g,'key','local:IdentityKey','facts.Key');set_value(g,'kind','local:IdentityKind','facts.Kind')
    arr(g,'count','Length',get(g,'EditEvents'));branch(g,'room',call(g,'bounded',KML+':Less_IntInt',{'A':'count.ReturnValue'},B=256))
    g.get('keyget','local:IdentityKey');g.get('kindget','local:IdentityKind')
    for node,var,value in [('event','EditEvents','entry.Event'),('keys','EditKeys','keyget.IdentityKey'),('kinds','EditKinds','kindget.IdentityKind')]:
        arr(g,node,'Add',get(g,var));g.wire((value,node+'.NewItem'))
    g.set('full','SelectionMessage','Too many pending edits. Release the key and let them finish.');g.set('noselection','SelectionMessage','Select a prop first.')
    g.chain('entry','selection','selected','key','kind','room','event','keys','kinds');g.chain('selection.else','room');g.chain('selected.else','noselection');g.chain('room.else','full')
    return g.function('QueueEditorMutation',inputs=[v('Event','struct:'+EVENT),v('RequireSelection','bool')],locals=[v('IdentityKey','string'),v('IdentityKind','int','-1')])


def execute():
    g=Graph();unpack(g,'event',EVENT,'entry.Event');previous='entry'
    for i,name in enumerate(GLOBAL+STOREROOM+PRESETS+COMPOSITIONS+TRANSFORMS):
        branch(g,'name'+str(i),call(g,'match'+str(i),STR+'EqualEqual_StrStr',{'A':'event.EventName'},B=name))
        node='run'+str(i)
        if name in GLOBAL:
            g.call(node+'cancel','self:CancelPlacement');g.call(node,'self:'+dict(save='SaveCurrent',undo='UndoEdit',redo='RedoEdit',exit='RequestEditorExit')[name]);g.call(node+'composition','self:CancelCompositionPreview');g.call(node+'parts','self:ClearCompositionSelection');g.chain(node+'cancel',node+'composition',node+'parts',node)
        elif name in STOREROOM:
            g.call(node,'self:RunStoreroomAction',Forget='true' if name=='forget' else 'false',All='true' if name=='restore_all' else 'false');g.wire(('event.Argument',node+'.Key'))
        elif name=='scope':
            g.call(node,'self:RequestEditorScopeChange')
        elif name in COMPOSITIONS:
            g.call(node,'self:RunCompositionAction',Name=name);g.wire(('event.Argument',node+'.Argument'))
        elif name in PRESETS:
            g.call(node,'self:RunPresetAction',Name=name);g.wire(('event.Argument',node+'.Argument'))
        elif name in FIELDS:
            g.call(node,'self:SetSelectionField',Field=FIELDS[name]);g.wire(('event.Argument',node+'.Text'))
        elif name in ['store','reset','duplicate','focus']:g.call(node,'self:'+dict(store='StoreSelection',reset='ResetSelection',duplicate='DuplicateSelection',focus='FocusSelection')[name])
        elif name.startswith('rotate'):
            g.call(node,'self:RotateSelection',Degrees=1 if name=='rotate_fine' else 15);g.wire(('event.Scalar',node+'.Steps'))
        elif name=='scale':g.call(node,'self:ScaleSelection');g.wire(('event.Scalar',node+'.Steps'))
        else:g.call(node,'self:NudgeSelection');g.wire(('event.Direction',node+'.Direction'))
        g.chain(previous,'name'+str(i),node+'cancel' if name in GLOBAL else node);g.chain(node,'refresh');previous='name'+str(i)+'.else'
    g.call('refresh','self:RefreshEditorUI')
    return g.function('RunEditorMutation',inputs=[v('Event','struct:'+EVENT)])


def pump():
    g=Graph();branch(g,'open',get(g,'UIOpen'));branch(g,'modal',call(g,'ismodal',KML+':Greater_IntInt',{'A':get(g,'ConfirmMode')},B=0))
    g.call('clear','self:ClearEditorMutations');g.call('ready','self:CanEdit');branch(g,'available',combine(g,'readycheck',['ready.Ready',call(g,'notdragging',KML+':Not_PreBool',{'A':get(g,'DragActive')})]))
    arr(g,'len','Length',get(g,'EditEvents'));branch(g,'any',call(g,'pending',KML+':Greater_IntInt',{'A':'len.ReturnValue'},B=0))
    previous='any'
    for node,var,local,kind in [('event','EditEvents','EventCopy','struct:'+EVENT),('key','EditKeys','KeyCopy','string'),('kind','EditKinds','KindCopy','int')]:
        arr(g,node,'Get',get(g,var),Index=0);set_value(g,'copy'+node,'local:'+local,node+'.Item');g.chain(previous,'copy'+node);previous='copy'+node
        g.get(node+'out','local:'+local)
    for node,var in [('events','EditEvents'),('keys','EditKeys'),('kinds','EditKinds')]:
        arr(g,'remove'+node,'Remove',get(g,var),IndexToRemove=0);g.chain(previous,'remove'+node);previous='remove'+node
    branch(g,'global',call(g,'globalcheck',KML+':Less_IntInt',{'A':'kindout.KindCopy'},B=0));unpack(g,'selected',FACT,get(g,'Selected'))
    samekind=call(g,'samekind',KML+':EqualEqual_IntInt',{'A':'kindout.KindCopy','B':'selected.Kind'});samekey=call(g,'samekey',STR+'EqualEqual_StrStr',{'A':'keyout.KeyCopy','B':'selected.Key'})
    branch(g,'same',combine(g,'identity',[get(g,'HasSelection'),samekind,samekey]));g.call('run','self:RunEditorMutation');g.wire(('eventout.EventCopy','run.Event'))
    g.chain('entry','open','modal','clear');g.chain('open.else','clear');g.chain('modal.else','ready','available','any');g.chain(previous,'global','run');g.chain('global.else','same','run')
    return g.function('PumpEditorMutations',locals=[v('EventCopy','struct:'+EVENT),v('KeyCopy','string'),v('KindCopy','int')])


def variables():return [v('EditEvents','struct:'+EVENT+'[]'),v('EditKeys','string[]'),v('EditKinds','int[]')]
def functions():return [clear_queue(),enqueue(),execute(),pump()]
