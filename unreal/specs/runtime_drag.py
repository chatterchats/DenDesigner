"""One native selection drag is one transaction; previews never edit the document.

The renderer/input owner supplies poses. This layer captures exact live state,
validates identity/generation, restores cancellation, and commits one history step.
It never spawns, resolves, loads assets, or writes save data during a preview.
"""
from graph import Graph, variable as v, KML
from runtime import ENTRY, LAYOUT, MUTATION, arr, unpack
from runtime_store import call, branch, combine, STR
from runtime_world import SCENE, SMC, PROP, RECORD, set_value, validity, finish_bool, vector_valid
from runtime_session import prop, method, HISTORY
from runtime_apply import get
from runtime_pick import FACT, PICKER
from runtime_editor_assets import BUS
from runtime_transform import POSE, copy_entry
from runtime_pivot import anchored_position


def not_(g, name, source):return call(g,name,KML+':Not_PreBool',{'A':source})
def equal(g,name,a,b,kind='IntInt'):return call(g,name,KML+':EqualEqual_'+kind,{'A':a,'B':b})


def context_current():
    g=Graph()
    # Native references keep the captured component alive; destruction, replacement,
    # session changes and queued world work still invalidate the transaction.
    checks=[get(g,'DragActive'),validity(g,'component',get(g,'DragComponent')),
            validity(g,'document',get(g,'WorkingDocument')),validity(g,'history',get(g,'History'))]
    branch(g,'references',combine(g,'referencesvalid',checks))
    owner=call(g,'owner','/Script/Engine.ActorComponent:GetOwner',{'self':get(g,'DragComponent')})
    checks=[validity(g,'ownercheck',owner),equal(g,'documentmatch',get(g,'WorkingDocument'),get(g,'DragDocument'),'ObjectObject'),
            equal(g,'generation',get(g,'Generation'),get(g,'DragGeneration')),
            equal(g,'version',prop(g,'versionget',HISTORY,'Version',get(g,'History')),get(g,'DragVersion'))]
    set_value(g,'ok','local:OK',combine(g,'current',checks));finish_bool(g,'Current')
    g.chain('entry','references','ok','result');g.chain('references.else','result')
    return g.function('DragContextCurrent',outputs=[v('Current','bool')],locals=[v('OK','bool','false')])


def can_continue():
    g=Graph();g.call('context','self:DragContextCurrent');g.call('ready','self:CanEdit')
    branch(g,'bus',validity(g,'busvalid',get(g,'InputBus')))
    method(g,'typing',BUS,'IsTyping',get(g,'InputBus'));set_value(g,'typingcopy','local:TextFocused','typing.Typing');g.get('textfocus','local:TextFocused')
    unpack(g,'selected',FACT,get(g,'Selected'));unpack(g,'captured',ENTRY,get(g,'DragEntry'))
    checks=['context.Current','ready.Ready',get(g,'HasSelection'),get(g,'UIOpen'),not_(g,'notlooking',get(g,'Looking')),not_(g,'nohelp',get(g,'HelpOpen')),not_(g,'nottyping','textfocus.TextFocused'),
            equal(g,'component','selected.Component',get(g,'DragComponent'),'ObjectObject'),
            equal(g,'kind','selected.Kind','captured.Kind'),
            call(g,'key',STR+'EqualEqual_StrStr',{'A':'selected.Key','B':'captured.Key'}),
            call(g,'nomodal',KML+':EqualEqual_IntInt',{'A':get(g,'ConfirmMode')},B=0)]
    g.wire((combine(g,'readycheck',checks),'result.Ready'));g.chain('entry','context','ready','bus','typing','typingcopy','result');g.chain('bus.else','result')
    return g.function('CanContinueSelectionDrag',outputs=[v('Ready','bool')],locals=[v('TextFocused','bool','false')])


def begin():
    g=Graph();g.call('ready','self:CanEdit')
    arr(g,'queued','Length',get(g,'EditEvents'))
    checks=['ready.Ready',get(g,'UIOpen'),not_(g,'idle',get(g,'DragActive')),
            call(g,'noqueue',KML+':EqualEqual_IntInt',{'A':'queued.ReturnValue'},B=0),
            call(g,'nomodal',KML+':EqualEqual_IntInt',{'A':get(g,'ConfirmMode')},B=0),
            call(g,'minmode',KML+':GreaterEqual_IntInt',{'A':'entry.Mode'},B=1),
            call(g,'maxmode',KML+':LessEqual_IntInt',{'A':'entry.Mode'},B=3)]
    branch(g,'available',combine(g,'allowed',checks));g.call('read','self:ReadSelectionState');branch(g,'selected','read.Ready')
    unpack(g,'facts',FACT,get(g,'Selected'));steps=[]
    anchor=call(g,'anchorchoice',KML+':SelectString',{'A':get(g,'RotationPivot'),'bPickA':call(g,'rotateanchor',KML+':EqualEqual_IntInt',{'A':'entry.Mode'},B=2)},B='centre')
    g.call('anchor','self:GetComponentEditPivot');g.wire(('facts.Component','anchor.Component'),(anchor,'anchor.Anchor'))
    set_value(g,'captureanchor','DragPivotPoint','anchor.Point');steps.append('captureanchor')
    for name,source in [('DragComponent','facts.Component'),('DragEntry','read.Value'),('DragWasPresent','read.WasPresent'),
                        ('DragDocument',get(g,'WorkingDocument')),('DragGeneration',get(g,'Generation')),
                        ('DragVersion',prop(g,'version',HISTORY,'Version',get(g,'History'))),('DragMode','entry.Mode'),
                        ('DragMobility',prop(g,'mobility',SCENE,'Mobility','facts.Component'))]:
        set_value(g,'capture'+name,name,source);steps.append('capture'+name)
    for name,_,_ in POSE:
        for prefix in ['DragStart','DragFinal']:
            set_value(g,'capture'+prefix+name,prefix+name,'read.'+name);steps.append('capture'+prefix+name)
    branch(g,'picker',validity(g,'pickervalid',get(g,'Picker')));method(g,'cancelquery',PICKER,'CancelQuery',get(g,'Picker'))
    g.set('active','DragActive','true');g.set('yes','local:OK','true');finish_bool(g)
    g.call('snap','self:BeginSnapDrag')
    g.chain('entry','ready','available','read','selected','anchor',*steps,'picker','cancelquery','active','snap','yes','result');g.chain('picker.else','active')
    for pin in ['available.else','selected.else']:g.chain(pin,'result')
    return g.function('BeginSelectionDrag',inputs=[v('Mode','int')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def preview():
    g=Graph();g.call('ready','self:CanContinueSelectionDrag');branch(g,'available','ready.Ready')
    values={};checks=[]
    rotating=call(g,'isrotating',KML+':EqualEqual_IntInt',{'A':get(g,'DragMode')},B=2)
    scaling=call(g,'isscaling',KML+':EqualEqual_IntInt',{'A':get(g,'DragMode')},B=3)
    newrotation=call(g,'pivotrotation',KML+':SelectRotator',{'A':'entry.Rotation','B':get(g,'DragStartRotation'),'bPickA':rotating})
    newscale=call(g,'pivotscale',KML+':SelectVector',{'A':'entry.Scale','B':get(g,'DragStartScale'),'bPickA':scaling})
    anchored=anchored_position(g,'anchor',get(g,'DragStartPosition'),get(g,'DragStartRotation'),get(g,'DragStartScale'),newrotation,newscale,get(g,'DragPivotPoint'))
    for index,(name,kind,_) in enumerate(POSE,1):
        chosen=call(g,'mode'+name,KML+':EqualEqual_IntInt',{'A':get(g,'DragMode')},B=index)
        # A move snaps to neighbouring props (runtime_snap) after any grid snapping by the caller.
        proposed='snap.Snapped' if name=='Position' else 'entry.'+name
        values[name]=call(g,'choose'+name,KML+(':SelectRotator' if kind=='rotator' else ':SelectVector'),{'A':proposed,'B':anchored if name=='Position' else get(g,'DragStart'+name),'bPickA':chosen})
        if kind=='vector':checks.append(vector_valid(g,'valid'+name,values[name],name=='Scale'))
        else:
            call(g,'rotation',KML+':BreakRotator',{'InRot':values[name]})
            for axis in ['Pitch','Yaw','Roll']:
                checks.extend([call(g,axis+'min',KML+':GreaterEqual_DoubleDouble',{'A':'rotation.'+axis},B=-1e7),call(g,axis+'max',KML+':LessEqual_DoubleDouble',{'A':'rotation.'+axis},B=1e7)])
    branch(g,'valid',combine(g,'validpose',checks));steps=[]
    for name,_,_ in POSE:
        set_value(g,'remember'+name,'DragFinal'+name,values[name]);steps.append('remember'+name)
    g.call('write','self:WriteSelectionDragPose')
    g.set('yes','local:OK','true');finish_bool(g)
    g.call('snap','self:SnapDragPosition');g.wire(('entry.Position','snap.Position'))
    g.chain('entry','ready','available','snap','valid',*steps,'write','yes','result')
    for pin in ['available.else','valid.else']:g.chain(pin,'result')
    return g.function('PreviewSelectionDrag',inputs=[v(n,t) for n,t,_ in POSE],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def write_pose():
    g=Graph();branch(g,'valid',validity(g,'componentvalid',get(g,'DragComponent')))
    call(g,'movable',SCENE+':SetMobility',{'self':get(g,'DragComponent')},NewMobility='Movable')
    call(g,'move',SCENE+':K2_SetWorldLocationAndRotation',{'self':get(g,'DragComponent'),'NewLocation':get(g,'DragFinalPosition'),'NewRotation':get(g,'DragFinalRotation')},bSweep='false',bTeleport='true')
    call(g,'scale',SCENE+':SetWorldScale3D',{'self':get(g,'DragComponent'),'NewScale':get(g,'DragFinalScale')})
    g.chain('entry','valid','movable','move','scale')
    return g.function('WriteSelectionDragPose')


def restore():
    g=Graph();g.call('context','self:DragContextCurrent');branch(g,'current','context.Current')
    call(g,'move',SCENE+':K2_SetWorldLocationAndRotation',{'self':get(g,'DragComponent'),'NewLocation':get(g,'DragStartPosition'),'NewRotation':get(g,'DragStartRotation')},bSweep='false',bTeleport='true')
    call(g,'scale',SCENE+':SetWorldScale3D',{'self':get(g,'DragComponent'),'NewScale':get(g,'DragStartScale')})
    call(g,'mobility',SCENE+':SetMobility',{'self':get(g,'DragComponent'),'NewMobility':get(g,'DragMobility')})
    g.chain('entry','context','current','move','scale','mobility')
    return g.function('RestoreSelectionDrag')


def committed_preview():
    # CommitEdit queues work for a later tick. Keep native world bookkeeping in
    # sync immediately, so Clear/teardown before that tick can still restore the
    # baseline. The selected record/prop already exists; no resolution or loads.
    g=Graph();unpack(g,'value',ENTRY,'entry.Value')
    branch(g,'native',call(g,'isnative',KML+':EqualEqual_IntInt',{'A':'value.Kind'},B=2))
    g.call('find','self:FindRecord');g.wire(('value.Key','find.Key'))
    branch(g,'found',call(g,'foundcheck',KML+':GreaterEqual_IntInt',{'A':'find.Index'},B=0))
    arr(g,'record','Get',get(g,'Records'));g.wire(('find.Index','record.Index'))
    branch(g,'valid',validity(g,'recordvalid','record.Item'));method(g,'alive',RECORD,'IsAlive','record.Item');branch(g,'alivecheck','alive.Alive')
    method(g,'nativeapply',RECORD,'ApplyTransform','record.Item',{'Value':'entry.Value'},Present='true')
    owner=call(g,'owner','/Script/Engine.ActorComponent:GetOwner',{'self':get(g,'DragComponent')})
    g.node('prop','cast',**{'class':PROP});g.wire((owner,'prop.Object'))
    method(g,'placedapply',PROP,'PreviewTransform','prop.AsBP Den Placed Prop',{'Value':'entry.Value'})
    g.chain('entry','native','find','found','valid','alive','alivecheck','nativeapply');g.chain('native.else','prop','placedapply')
    return g.function('ApplyCommittedSelectionDrag',inputs=[v('Value','struct:'+ENTRY)])


def release():
    g=Graph();g.call('surface','self:FinishSurfaceDrag');branch(g,'active',get(g,'DragActive'));branch(g,'commit','entry.Commit')
    g.call('ready','self:CanContinueSelectionDrag');branch(g,'available','ready.Ready');unpack(g,'base',ENTRY,get(g,'DragEntry'))
    changed=[];changes={}
    for index,(name,kind,_) in enumerate(POSE,1):
        ismode=call(g,'mode'+name,KML+':EqualEqual_IntInt',{'A':get(g,'DragMode')},B=index)
        if name=='Position':  # turning/scaling about a bounds anchor can also move the authored origin
            ismode=call(g,'positionmode',KML+':GreaterEqual_IntInt',{'A':get(g,'DragMode')},B=1)
        same=call(g,'same'+name,KML+(':EqualEqual_RotatorRotator' if kind=='rotator' else ':EqualEqual_VectorVector'),{'A':get(g,'DragStart'+name),'B':get(g,'DragFinal'+name)},ErrorTolerance=.0001)
        use=combine(g,'changed'+name,[ismode,not_(g,'different'+name,same)]);changed.append(use)
        changes[name]=call(g,'choose'+name,KML+(':SelectRotator' if kind=='rotator' else ':SelectVector'),{'A':get(g,'DragFinal'+name),'B':'base.'+name,'bPickA':use})
        changes['Has'+name]=combine(g,'flag'+name,['base.Has'+name,use],True)
    branch(g,'changed',combine(g,'anychange',changed,True))
    value=copy_entry(g,'edited',get(g,'DragEntry'),changes)
    g.node('mutation','make_struct',struct=MUTATION,defaults={'Present':'true'});g.wire((value,'mutation.Value'))
    g.get('mutations','local:DragMutations');arr(g,'append','Add','mutations.DragMutations');g.wire(('mutation.ST_DenMutation','append.NewItem'))
    rotate=call(g,'rotate',KML+':EqualEqual_IntInt',{'A':get(g,'DragMode')},B=2)
    move=call(g,'move',KML+':EqualEqual_IntInt',{'A':get(g,'DragMode')},B=1)
    label=call(g,'rotateorscale',KML+':SelectString',{'bPickA':rotate},A='Rotate',B='Scale')
    label=call(g,'label',KML+':SelectString',{'B':label,'bPickA':move},A='Move')
    g.call('write','self:CommitEdit');g.wire(('mutations.DragMutations','write.Mutations'),(label,'write.Label'))
    branch(g,'written','write.Accepted');g.set('yes','local:OK','true');g.call('localchange','self:ReuseSelectionIndex')
    # Restore before CommitEdit changes the world generation, so failure cannot
    # strand an uncommitted preview. Accepted edits reapply the preview in this
    # same call; no rendered frame sees the intermediate baseline.
    g.call('beforecommit','self:RestoreSelectionDrag');g.call('committedpose','self:ApplyCommittedSelectionDrag');g.wire((value,'committedpose.Value'))
    g.call('restore','self:RestoreSelectionDrag');g.set('inactive','DragActive','false')
    g.set('componentclear','DragComponent');g.set('docclear','DragDocument');g.set('entryclear','DragEntry');g.call('fields','self:RefreshTransformFields')
    finish_bool(g)
    g.call('snap','self:EndSnapDrag')
    g.chain('entry','surface','snap','active','commit','ready','available','changed','append','beforecommit','write','written','committedpose','yes','localchange','inactive','componentclear','docclear','entryclear','fields','result')
    for pin in ['commit.else','available.else','changed.else','written.else']:g.chain(pin,'restore','inactive')
    g.chain('active.else','result')
    return g.function('EndSelectionDrag',inputs=[v('Commit','bool')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false'),v('DragMutations','struct:'+MUTATION+'[]')])


def poll():
    g=Graph();branch(g,'active',get(g,'DragActive'));g.call('ready','self:CanContinueSelectionDrag');branch(g,'valid','ready.Ready')
    g.call('cancel','self:EndSelectionDrag',Commit='false');g.chain('entry','active','ready','valid');g.chain('valid.else','cancel')
    return g.function('PollSelectionDrag')


def variables():
    return [v('DragActive','bool'),v('DragComponent','object:'+SMC),v('DragDocument','object:'+LAYOUT),v('DragEntry','struct:'+ENTRY),
            v('DragPivotPoint','vector'),v('DragWasPresent','bool'),v('DragGeneration','int'),v('DragVersion','int'),v('DragMode','int'),v('DragMobility','byte'),
            *[v(prefix+n,t) for prefix in ['DragStart','DragFinal'] for n,t,_ in POSE]]


def functions():return [context_current(),can_continue(),begin(),preview(),write_pose(),restore(),committed_preview(),release(),poll()]
