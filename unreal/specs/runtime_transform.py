"""Native selection poses and validated transform commands.

Only changed groups gain override flags. All unrelated persisted entry fields are
copied, including material overrides, collision mode and recovered fingerprints.
"""
from graph import Graph, variable as v, KML
from runtime import ENTRY, MUTATION, LAYOUT, arr, unpack
from runtime_store import call, branch, combine, STR
from runtime_world import SCENE, RECORD, set_value, validity, finish_bool, vector_valid
from runtime_session import prop, method
from runtime_apply import get
from runtime_pick import FACT, PICKER
from runtime_editor_assets import RIG
from runtime_editor_host import widget, text
from runtime_pivot import PIVOTS, anchored_position

ENTRY_FIELDS=['Kind','Key','Mesh','Position','Rotation','Scale','HasPosition','HasRotation','HasScale','Hidden','CollisionMode','Materials','Source','HasFingerprint','FingerprintMesh','FingerprintPosition']
POSE=[('Position','vector','K2_GetComponentLocation'),('Rotation','rotator','K2_GetComponentRotation'),('Scale','vector','K2_GetComponentScale')]


def format_number(g,name,source):
    return call(g,name,'/Script/Engine.KismetTextLibrary:Conv_DoubleToText',{'Value':source},bUseGrouping='false',MaximumFractionalDigits=2)


def copy_entry(g,name,source,changes=None,defaults=None):
    unpack(g,name+'base',ENTRY,source);g.node(name,'make_struct',struct=ENTRY,defaults=defaults or {})
    changes=changes or {};defaults=defaults or {}
    for field in ENTRY_FIELDS:
        if field not in defaults:g.wire((changes.get(field,name+'base.'+field),name+'.'+field))
    return name+'.ST_DenEntry'


def read_selection():
    g=Graph();unpack(g,'facts',FACT,get(g,'Selected'))
    branch(g,'valid',combine(g,'validcheck',[get(g,'HasSelection'),validity(g,'component','facts.Component'),validity(g,'doc',get(g,'WorkingDocument'))]))
    method(g,'read',LAYOUT,'ReadEntry',get(g,'WorkingDocument'),{'Kind':'facts.Kind','Key':'facts.Key'})
    branch(g,'exists','read.Exists');set_value(g,'existing','local:SelectionEntryCopy','read.Value')
    branch(g,'vanilla',call(g,'native',KML+':EqualEqual_IntInt',{'A':'facts.Kind'},B=2))
    g.call('find','self:FindRecord');g.wire(('facts.Key','find.Key'));branch(g,'recordfound',call(g,'found',KML+':GreaterEqual_IntInt',{'A':'find.Index'},B=0))
    arr(g,'record','Get',get(g,'Records'));g.wire(('find.Index','record.Index'))
    branch(g,'recordvalid',validity(g,'recordcheck','record.Item'))
    method(g,'alive',RECORD,'IsAlive','record.Item');branch(g,'alivecheck','alive.Alive')
    g.node('new','make_struct',struct=ENTRY,defaults={'Kind':'2','HasFingerprint':'true','Scale':'1,1,1'})
    g.wire(('facts.Key','new.Key'),('facts.Mesh','new.Mesh'),('facts.Mesh','new.FingerprintMesh'),(prop(g,'original',RECORD,'OriginalPosition','record.Item'),'new.FingerprintPosition'))
    set_value(g,'created','local:SelectionEntryCopy','new.ST_DenEntry')
    g.node('pose','sequence',outputs=1);previous='pose.then_0'
    for name,kind,fn in POSE:
        set_value(g,'copy'+name,'local:Pose'+name,call(g,'get'+name,SCENE+':'+fn,{'self':'facts.Component'}));g.chain(previous,'copy'+name);previous='copy'+name
        g.get('out'+name,'local:Pose'+name);g.wire(('out'+name+'.Pose'+name,'result.'+name))
    g.set('yes','local:OK','true');finish_bool(g,'Ready');g.get('outentry','local:SelectionEntryCopy');g.wire(('outentry.SelectionEntryCopy','result.Value'),('read.Exists','result.WasPresent'))
    g.chain('entry','valid','read','exists','existing','pose');g.chain('exists.else','vanilla','find','recordfound','recordvalid','alive','alivecheck','created','pose');g.chain(previous,'yes','result')
    for pin in ['valid.else','vanilla.else','recordfound.else','recordvalid.else','alivecheck.else']:g.chain(pin,'result')
    return g.function('ReadSelectionState',outputs=[v('Ready','bool'),v('Value','struct:'+ENTRY),v('WasPresent','bool'),*[v(n,t) for n,t,_ in POSE]],locals=[v('OK','bool','false'),v('SelectionEntryCopy','struct:'+ENTRY),*[v('Pose'+n,t) for n,t,_ in POSE]])


def commit_pose():
    g=Graph();g.call('ready','self:CanEdit');branch(g,'available',combine(g,'availablecheck',['ready.Ready',call(g,'notdragging',KML+':Not_PreBool',{'A':get(g,'DragActive')})]));g.call('read','self:ReadSelectionState');branch(g,'selected','read.Ready')
    unpack(g,'base',ENTRY,'read.Value');changes={};changed=[];checks=[]
    unpack(g,'facts',FACT,get(g,'Selected'))
    g.call('anchor','self:GetComponentEditPivot');g.wire(('facts.Component','anchor.Component'),(get(g,'RotationPivot'),'anchor.Anchor'))
    anchored=anchored_position(g,'pivot','read.Position','read.Rotation','read.Scale','entry.Rotation','read.Scale','anchor.Point')
    compensate=combine(g,'compensate',['entry.ChangeRotation',call(g,'noposition',KML+':Not_PreBool',{'A':'entry.ChangePosition'})])
    position=call(g,'requestedposition',KML+':SelectVector',{'A':anchored,'B':'entry.Position','bPickA':compensate})
    shifts=call(g,'shifted',KML+':NotEqual_VectorVector',{'A':anchored,'B':'read.Position'},ErrorTolerance=.0001)
    useposition=combine(g,'useposition',['entry.ChangePosition',combine(g,'pivotmoved',[compensate,shifts])],True)
    for name,kind,_ in POSE:
        use=useposition if name=='Position' else 'entry.Change'+name
        proposed=position if name=='Position' else 'entry.'+name
        same=call(g,'same'+name,KML+(':EqualEqual_RotatorRotator' if kind=='rotator' else ':EqualEqual_VectorVector'),{'A':proposed,'B':'read.'+name},ErrorTolerance=.0001)
        different=call(g,'diff'+name,KML+':Not_PreBool',{'A':same});changed.append(combine(g,'changed'+name,[use,different]))
        changes[name]=call(g,'select'+name,KML+(':SelectRotator' if kind=='rotator' else ':SelectVector'),{'A':proposed,'B':'base.'+name,'bPickA':use})
        changes['Has'+name]=combine(g,'flag'+name,['base.Has'+name,use],True)
        if kind=='vector':valid=vector_valid(g,'valid'+name,proposed,name=='Scale')
        else:
            call(g,'rotation',KML+':BreakRotator',{'InRot':'entry.Rotation'});parts=[]
            for axis in ['Pitch','Yaw','Roll']:
                parts += [call(g,axis+'low',KML+':GreaterEqual_DoubleDouble',{'A':'rotation.'+axis},B=-1e7),call(g,axis+'high',KML+':LessEqual_DoubleDouble',{'A':'rotation.'+axis},B=1e7)]
            valid=combine(g,'rotationvalid',parts)
        unused=call(g,'unused'+name,KML+':Not_PreBool',{'A':use});checks.append(combine(g,'check'+name,[unused,valid],True))
    branch(g,'valid',combine(g,'validall',checks));branch(g,'changed',combine(g,'changedany',changed,True))
    value=copy_entry(g,'edited','read.Value',changes)
    g.node('mutation','make_struct',struct=MUTATION,defaults={'Present':'true'});g.wire((value,'mutation.Value'))
    g.get('mutations','local:Mutations');arr(g,'append','Add','mutations.Mutations');g.wire(('mutation.ST_DenMutation','append.NewItem'))
    # Include the selection identity in the merge key so repeated adjustments to
    # different objects can never collapse into one history entry.
    key=call(g,'key',STR+'Concat_StrStr',{'A':'base.Key','B':'entry.MergeKey'})
    nonempty=call(g,'merge',STR+'NotEqual_StrStr',{'A':'entry.MergeKey'},B='')
    mergekey=call(g,'choosekey',KML+':SelectString',{'A':key,'bPickA':nonempty},B='')
    g.call('commit','self:CommitEdit');g.wire(('mutations.Mutations','commit.Mutations'),('entry.Label','commit.Label'),(mergekey,'commit.MergeKey'))
    set_value(g,'ok','local:OK','commit.Accepted');branch(g,'committed','commit.Accepted');g.call('localchange','self:ReuseSelectionIndex');g.set('clear','SelectionMessage','');g.set('invalid','SelectionMessage','Enter a finite transform within the supported range.')
    finish_bool(g);g.chain('entry','ready','available','read','selected','anchor','valid','changed','append','commit','ok','committed','localchange','clear','result');g.chain('valid.else','invalid','result')
    for pin in ['available.else','selected.else','changed.else','committed.else']:g.chain(pin,'result')
    return g.function('CommitSelectionPose',inputs=[*[v(n,t) for n,t,_ in POSE],*[v('Change'+n,'bool') for n,_,_ in POSE],v('Label','string'),v('MergeKey','string')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false'),v('Mutations','struct:'+MUTATION+'[]')])


def decimal():
    g=Graph();numeric=call(g,'numeric',STR+'IsNumeric',{'SourceString':'entry.Text'})
    # FString::IsNumeric accepts bare signs and dots. Require a digit too.
    digits=[call(g,'digit'+d,STR+'Contains',{'SearchIn':'entry.Text'},Substring=d,bUseCase='true') for d in '0123456789']
    valid=combine(g,'valid',[numeric,combine(g,'digits',digits,True)])
    g.wire((valid,'result.Valid'));g.chain('entry','result')
    return g.function('IsTransformDecimal',inputs=[v('Text','string')],outputs=[v('Valid','bool')])


def number():
    g=Graph();comma=call(g,'comma',STR+'Replace',{'SourceString':'entry.Text'},From=',',To='.',SearchCase='CaseSensitive')
    stripped=call(g,'trim',STR+'Trim',{'SourceString':comma});clean=call(g,'trailing',STR+'TrimTrailing',{'SourceString':stripped})
    lower=call(g,'lower',STR+'ToLower',{'SourceString':clean})
    call(g,'split',STR+'Split',{'SourceString':lower},InStr='e',SearchCase='CaseSensitive',SearchDir='FromStart');branch(g,'exponent','split.ReturnValue')
    g.call('mantissa','self:IsTransformDecimal');g.wire(('split.LeftS','mantissa.Text'));branch(g,'mantissaok','mantissa.Valid')
    g.call('exp','self:IsTransformDecimal');g.wire(('split.RightS','exp.Text'))
    dot=call(g,'dot',STR+'Contains',{'SearchIn':'split.RightS'},Substring='.',bUseCase='true');nodot=call(g,'nodot',KML+':Not_PreBool',{'A':dot})
    branch(g,'expok',combine(g,'integerexp',['exp.Valid',nodot]))
    g.call('decimal','self:IsTransformDecimal');g.wire((clean,'decimal.Text'));branch(g,'decimalok','decimal.Valid')
    value=call(g,'parse',STR+'Conv_StringToDouble',{'InString':clean});set_value(g,'parsed','local:ParsedValue',value)
    lo=call(g,'min',KML+':GreaterEqual_DoubleDouble',{'A':value},B=-1e7);hi=call(g,'max',KML+':LessEqual_DoubleDouble',{'A':value},B=1e7)
    set_value(g,'valid','local:OK',combine(g,'finitebounded',[lo,hi]));finish_bool(g,'Valid');g.get('outvalue','local:ParsedValue');g.wire(('outvalue.ParsedValue','result.Value'))
    g.chain('entry','exponent','mantissa','mantissaok','exp','expok','parsed','valid','result');g.chain('exponent.else','decimal','decimalok','parsed')
    for pin in ['mantissaok.else','expok.else','decimalok.else']:g.chain(pin,'result')
    return g.function('ParseTransformNumber',inputs=[v('Text','string')],outputs=[v('Valid','bool'),v('Value','double')],locals=[v('OK','bool','false'),v('ParsedValue','double')])


def numeric(axis):
    g=Graph();g.call('parse','self:ParseTransformNumber');g.wire(('entry.Text','parse.Text'));branch(g,'parsed','parse.Valid')
    g.call('read','self:ReadSelectionState');branch(g,'selected','read.Ready')
    call(g,'position',KML+':BreakVector',{'InVec':'read.Position'});call(g,'rotation',KML+':BreakRotator',{'InRot':'read.Rotation'});call(g,'scale',KML+':BreakVector',{'InVec':'read.Scale'})
    g.set('clearvalidation','SelectionMessage','')
    g.chain('selected','clearvalidation')
    previous='clearvalidation'
    for field in [axis]:
        branch(g,'field'+field,call(g,'name'+field,STR+'EqualEqual_StrStr',{'A':'entry.Field'},B=field))
        group='Position' if field in ['X','Y','Z'] else 'Scale' if field=='Scale' else 'Rotation'
        if group=='Position':value=call(g,'value'+field,KML+':MakeVector',{axis:'parse.Value' if axis==field else 'position.'+axis for axis in ['X','Y','Z']})
        elif group=='Rotation':
            normalized=call(g,'wrap'+field,KML+':NormalizeAxis',{'Angle':'parse.Value'})
            value=call(g,'value'+field,KML+':MakeRotator',{axis:normalized if axis==field else 'rotation.'+axis for axis in ['Pitch','Yaw','Roll']})
        else:
            clamped=call(g,'clamp',KML+':FClamp',{'Value':'parse.Value'},Min=.05,Max=20)
            value=call(g,'valueScale',KML+':MakeVector',{axis:clamped for axis in ['X','Y','Z']})
        g.call('commit'+field,'self:CommitSelectionPose',**{'Change'+group:'true','Label':'Edit '+field})
        # Submitting the rounded display must not quantize the actual pose.
        # Compare with exactly the same formatter, rather than relaxing pose
        # tolerance (which would swallow deliberate high-precision edits).
        source='position.'+field if group=='Position' else 'scale.X' if group=='Scale' else 'rotation.'+field
        shown=format_number(g,'shown'+field,source)
        showntext=call(g,'showntext'+field,'/Script/Engine.KismetTextLibrary:Conv_TextToString',{'InText':shown})
        g.call('display'+field,'self:ParseTransformNumber');g.wire((showntext,'display'+field+'.Text'))
        same=call(g,'equaldisplay'+field,KML+':EqualEqual_DoubleDouble',{'A':'parse.Value','B':'display'+field+'.Value'})
        branch(g,'unchanged'+field,combine(g,'samedisplay'+field,['display'+field+'.Valid',same]))
        g.wire((value,'commit'+field+'.'+group));g.chain(previous,'field'+field,'display'+field,'unchanged'+field)
        g.chain('unchanged'+field+'.else','commit'+field);previous='field'+field+'.else'
    g.set('invalid','SelectionMessage','Enter a number between -10000000 and 10000000.');g.call('refresh','self:RefreshTransformFields');g.call('feedback','self:RefreshEditorUI')
    g.chain('entry','parse','parsed','read','selected');g.chain('parsed.else','invalid','refresh','feedback')
    return g.function('SetSelectionField'+axis,inputs=[v('Field','string'),v('Text','string')])


def numeric_dispatch():
    g=Graph();previous='entry'
    for axis in ['X','Y','Z','Pitch','Yaw','Roll','Scale']:
        branch(g,axis,call(g,axis+'name',STR+'EqualEqual_StrStr',{'A':'entry.Field'},B=axis))
        g.call(axis+'apply','self:SetSelectionField'+axis,Field=axis);g.wire(('entry.Text',axis+'apply.Text'));g.chain(previous,axis,axis+'apply');previous=axis+'.else'
    return g.function('SetSelectionField',inputs=[v('Field','string'),v('Text','string')])


def adjust(mode):
    g=Graph();g.call('read','self:ReadSelectionState');branch(g,'selected','read.Ready')
    if mode=='Rotate':
        call(g,'rotation',KML+':BreakRotator',{'InRot':'read.Rotation'})
        delta=call(g,'delta',KML+':Multiply_DoubleDouble',{'A':'entry.Steps','B':'entry.Degrees'})
        yaw=call(g,'sum',KML+':Add_DoubleDouble',{'A':'rotation.Yaw','B':delta});yaw=call(g,'wrap',KML+':NormalizeAxis',{'Angle':yaw})
        value=call(g,'new',KML+':MakeRotator',{'Pitch':'rotation.Pitch','Roll':'rotation.Roll','Yaw':yaw});group='Rotation';params=[v('Steps','double'),v('Degrees','double')]
    elif mode=='Scale':
        factor=call(g,'factor',KML+':MultiplyMultiply_FloatFloat',{'Exp':'entry.Steps'},Base=1.05)
        call(g,'scale',KML+':BreakVector',{'InVec':'read.Scale'});parts={}
        for axis in ['X','Y','Z']:
            product=call(g,'product'+axis,KML+':Multiply_DoubleDouble',{'A':'scale.'+axis,'B':factor});parts[axis]=call(g,'clamp'+axis,KML+':FClamp',{'Value':product},Min=.05,Max=20)
        value=call(g,'new',KML+':MakeVector',parts);group='Scale';params=[v('Steps','double')]
    else:
        branch(g,'rig',validity(g,'rigvalid',get(g,'EditorRig')))
        rot=call(g,'camera', '/Script/Engine.Actor:K2_GetActorRotation',{'self':get(g,'EditorRig')});call(g,'rotation',KML+':BreakRotator',{'InRot':rot})
        yaw=call(g,'snapyaw',KML+':GridSnap_Float',{'Location':'rotation.Yaw'},GridSize=90)
        direction=call(g,'direction',KML+':RotateAngleAxis',{'InVect':'entry.Direction','AngleDeg':yaw},Axis='0,0,1')
        grid=call(g,'grid',KML+':Greater_DoubleDouble',{'A':get(g,'GridStep')},B=0)
        step=call(g,'step',KML+':SelectFloat',{'A':get(g,'GridStep'),'bPickA':grid},B=5)
        delta=call(g,'delta',KML+':Multiply_VectorFloat',{'A':direction,'B':step});value=call(g,'new',KML+':Add_VectorVector',{'A':'read.Position','B':delta});group='Position';params=[v('Direction','vector')]
    g.call('commit','self:CommitSelectionPose',**{'Change'+group:'true','Label':mode,'MergeKey':':'+mode.lower()});g.wire((value,'commit.'+group))
    g.chain('entry','read','selected',*(['rig'] if mode=='Nudge' else []),'commit')
    return g.function(mode+'Selection',inputs=params)


def store_selection():
    g=Graph();g.call('ready','self:CanEdit');branch(g,'available',combine(g,'availablecheck',['ready.Ready',call(g,'notdragging',KML+':Not_PreBool',{'A':get(g,'DragActive')})]));g.call('read','self:ReadSelectionState');branch(g,'selected','read.Ready')
    unpack(g,'base',ENTRY,'read.Value');branch(g,'placed',call(g,'isplaced',KML+':EqualEqual_IntInt',{'A':'base.Kind'},B=0))
    g.get('mutations','local:SelectionMutations')
    g.node('remove','make_struct',struct=MUTATION,defaults={'Present':'false'});g.wire(('read.Value','remove.Value'))
    arr(g,'removeadd','Add','mutations.SelectionMutations');g.wire(('remove.ST_DenMutation','removeadd.NewItem'))
    stored=copy_entry(g,'stored','read.Value',defaults={'Kind':'1'})
    hidden=copy_entry(g,'hidden','read.Value',defaults={'Hidden':'true'})
    for name,value in [('stored',stored),('hidden',hidden)]:
        g.node(name+'mutation','make_struct',struct=MUTATION,defaults={'Present':'true'});g.wire((value,name+'mutation.Value'))
        arr(g,name+'add','Add','mutations.SelectionMutations');g.wire((name+'mutation.ST_DenMutation',name+'add.NewItem'))
    unpack(g,'picked',FACT,get(g,'Selected'))
    g.call('commit','self:CommitEdit',Label='Store');g.wire(('mutations.SelectionMutations','commit.Mutations'));branch(g,'accepted','commit.Accepted');g.call('clear','self:ClearSelection')
    branch(g,'picker',validity(g,'pickervalid',get(g,'Picker')))
    method(g,'prune',PICKER,'RemoveIndexedComponent',get(g,'Picker'),{'Component':'picked.Component'});g.call('reuse','self:ReuseSelectionIndex')
    g.chain('entry','ready','available','read','selected','placed','removeadd','storedadd','commit','accepted','picker','prune','reuse','clear');g.chain('picker.else','clear');g.chain('placed.else','hiddenadd','commit')
    return g.function('StoreSelection',locals=[v('SelectionMutations','struct:'+MUTATION+'[]')])


def reset_selection():
    g=Graph();g.call('ready','self:CanEdit');branch(g,'available',combine(g,'availablecheck',['ready.Ready',call(g,'notdragging',KML+':Not_PreBool',{'A':get(g,'DragActive')})]));g.call('read','self:ReadSelectionState');branch(g,'selected','read.Ready')
    unpack(g,'base',ENTRY,'read.Value');branch(g,'placed',call(g,'isplaced',KML+':EqualEqual_IntInt',{'A':'base.Kind'},B=0))
    call(g,'rot',KML+':BreakRotator',{'InRot':'read.Rotation'});rotation=call(g,'upright',KML+':MakeRotator',{'Yaw':'rot.Yaw'},Pitch=0,Roll=0)
    g.call('straighten','self:CommitSelectionPose',ChangeRotation='true',ChangeScale='true',Scale='1,1,1',Label='Reset');g.wire((rotation,'straighten.Rotation'))
    g.get('mutations','local:SelectionMutations');g.node('mutation','make_struct',struct=MUTATION,defaults={'Present':'false'});g.wire(('read.Value','mutation.Value'))
    arr(g,'append','Add','mutations.SelectionMutations');g.wire(('mutation.ST_DenMutation','append.NewItem'))
    branch(g,'present','read.WasPresent');g.call('commit','self:CommitEdit',Label='Reset');g.wire(('mutations.SelectionMutations','commit.Mutations'))
    g.chain('entry','ready','available','read','selected','placed','straighten');g.chain('placed.else','present','append','commit')
    return g.function('ResetSelection',locals=[v('SelectionMutations','struct:'+MUTATION+'[]')])


def refresh_fields():
    g=Graph();branch(g,'inspector',validity(g,'valid',get(g,'Inspector')));g.call('read','self:ReadSelectionState');branch(g,'selected','read.Ready')
    for name,fn,pin in [('pos','BreakVector','Position'),('rot','BreakRotator','Rotation'),('scale','BreakVector','Scale')]:call(g,name,KML+':'+fn,{'InRot' if name=='rot' else 'InVec':'read.'+pin})
    previous='selected'
    for field in ['X','Y','Z','Pitch','Yaw','Roll','Scale']:
        source=('pos.'+field if field in ['X','Y','Z'] else 'scale.X' if field=='Scale' else 'rot.'+field)
        label=format_number(g,'format'+field,source)
        box=widget(g,'box'+field,'Inspector','Field'+field);call(g,'write'+field,'/Script/UMG.EditableTextBox:SetText',{'self':box,'InText':label})
        g.chain(previous,'write'+field);previous='write'+field
    # The inspector's button cycles the same persisted setting as Settings.
    caption=get(g,'RotationPivot')
    for anchor,label in PIVOTS:
        match=call(g,'pivotis'+anchor,STR+'EqualEqual_StrStr',{'A':get(g,'RotationPivot')},B=anchor)
        caption=call(g,'pivotlabel'+anchor,KML+':SelectString',{'B':caption,'bPickA':match},A='Pivot: '+label)
    text(g,'pivotcaption','Inspector','RotationPivotLabel',value=caption);g.chain(previous,'pivotcaption')
    g.chain('entry','inspector','read','selected')
    return g.function('RefreshTransformFields')


def functions():return [read_selection(),commit_pose(),decimal(),number(),numeric_dispatch(),*[numeric(axis) for axis in ['X','Y','Z','Pitch','Yaw','Roll','Scale']],adjust('Rotate'),adjust('Scale'),adjust('Nudge'),store_selection(),reset_selection(),refresh_fields()]
