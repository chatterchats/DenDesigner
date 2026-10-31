"""Asynchronous all-parts preview; one history transaction per placed composition."""
from graph import Graph,variable as v,KML,KSL,GS
from runtime import ENTRY,LAYOUT,MUTATION,arr,unpack
from runtime_store import call,branch,combine,STR
from runtime_world import ACTOR,WORLD,PROP,PRIMITIVE,set_value,validity,finish_bool
from runtime_apply import APPLY,get
from runtime_session import prop,method
from runtime_transform import copy_entry
from runtime_gizmo_controller import op,neg,math
from runtime_editor_host import PC
from runtime_editor_assets import RIG
from runtime_layout_ui import PRESETS
from runtime_compositions import LIMIT


def transform():
    g=Graph();unpack(g,'part',ENTRY,'entry.Value')
    offset=call(g,'offset',KML+':RotateAngleAxis',{'InVect':op(g,'scaledposition','Multiply_VectorFloat','part.Position','entry.Scale'),'AngleDeg':'entry.Yaw'},Axis='0,0,1')
    position=op(g,'position','Add_VectorVector','entry.Origin',offset)
    yaw=call(g,'yaw',KML+':MakeRotator',{'Yaw':'entry.Yaw'})
    rotation=call(g,'rotation',KML+':ComposeRotators',{'A':'part.Rotation','B':yaw})
    value=copy_entry(g,'value','entry.Value',{'Position':position,'Rotation':rotation,'Scale':op(g,'scale','Multiply_VectorFloat','part.Scale','entry.Scale')},defaults={'Hidden':'false'})
    g.call('validate','self:ValidCompositionTransform');g.wire((value,'validate.Value'),(value,'result.Transformed'),('validate.Valid','result.Valid'));g.chain('entry','validate','result')
    return g.function('TransformCompositionPart',inputs=[v('Value','struct:'+ENTRY),v('Origin','vector'),v('Yaw','double'),v('Scale','double')],outputs=[v('Transformed','struct:'+ENTRY),v('Valid','bool')])


def validate():
    g=Graph();branch(g,'document',validity(g,'alive','entry.Document'))
    branch(g,'schema',op(g,'supported','EqualEqual_IntInt',prop(g,'version',LAYOUT,'SchemaVersion','entry.Document'),B=1))
    rows=prop(g,'rows',LAYOUT,'Entries','entry.Document');arr(g,'count','Length',rows);branch(g,'bounded',combine(g,'size',[op(g,'min','Greater_IntInt','count.ReturnValue',B=0),op(g,'max','LessEqual_IntInt','count.ReturnValue',B=LIMIT)]))
    g.get('i','local:Cursor');g.get('keys','local:Keys');branch(g,'more',op(g,'within','Less_IntInt','i.Cursor','count.ReturnValue'));arr(g,'part','Get',rows);g.wire(('i.Cursor','part.Index'));unpack(g,'partdata',ENTRY,'part.Item')
    g.call('xf','self:ValidCompositionTransform');g.wire(('part.Item','xf.Value'));g.call('mesh','self:ValidAssetPath');g.wire(('partdata.Mesh','mesh.Path'));arr(g,'exists','Contains','keys.Keys');g.wire(('partdata.Key','exists.ItemToFind'));arr(g,'materials','Length','partdata.Materials')
    branch(g,'valid',combine(g,'partvalid',['xf.Valid','mesh.Valid','partdata.HasPosition','partdata.HasRotation','partdata.HasScale',neg(g,'visible','partdata.Hidden'),neg(g,'unique','exists.ReturnValue'),op(g,'kind','EqualEqual_IntInt','partdata.Kind',B=0),op(g,'matlimit','LessEqual_IntInt','materials.ReturnValue',B=256),call(g,'key',STR+'NotEqual_StrStr',{'A':'partdata.Key'},B='')]))
    arr(g,'remember','Add','keys.Keys');g.wire(('partdata.Key','remember.NewItem'));set_value(g,'next','local:Cursor',op(g,'advance','Add_IntInt','i.Cursor',B=1));g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','document','schema','bounded','more','xf','mesh','valid','remember','next','more');g.chain('more.else','yes','result')
    for pin in ['document.else','schema.else','bounded.else','valid.else']:g.chain(pin,'result')
    return g.function('ValidateComposition',inputs=[v('Document','object:'+LAYOUT)],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false'),v('Cursor','int','0'),v('Keys','string[]')])


def cancel():
    g=Graph();set_value(g,'wasactive','local:WasActive',get(g,'CompositionPlacing'));g.set('stop','CompositionPlacing','false');g.set('ready','CompositionPreviewReady','false');g.set('pose','CompositionPoseValid','false')
    branch(g,'valid',validity(g,'alive',get(g,'CompositionPreview')))
    method(g,'cancel',APPLY,'CancelWork',get(g,'CompositionPreview'));method(g,'clear',WORLD,'Clear',get(g,'CompositionPreview'));call(g,'destroy',ACTOR+':K2_DestroyActor',{'self':get(g,'CompositionPreview')})
    g.set('release','CompositionPreview');g.set('document','CompositionDocument');g.chain('entry','wasactive','stop','ready','pose','valid','cancel','clear','destroy','release','document');g.chain('valid.else','release')
    g.get('was','local:WasActive');branch(g,'clearfeedback','was.WasActive');g.set('message','SelectionMessage','');g.set('unfold','RailAutoFold','false');g.call('refresh','self:RefreshEditorUI');g.chain('document','clearfeedback','message','unfold','refresh')
    return g.function('CancelCompositionPreview',locals=[v('WasActive','bool','false')])


def start():
    g=Graph();g.node('self','self');g.call('ready','self:CanEdit');g.call('validate','self:ValidateComposition');g.wire(('entry.Document','validate.Document'))
    branch(g,'allowed',combine(g,'available',[get(g,'UIOpen'),'ready.Ready','validate.Accepted']))
    g.call('cancel','self:CancelCompositionPreview');g.call('single','self:CancelPlacement');g.call('parts','self:ClearCompositionSelection');g.call('selection','self:ClearSelection');set_value(g,'document','CompositionDocument','entry.Document')
    identity=call(g,'identity',KML+':MakeTransform',Scale='1,1,1');actor=call(g,'spawn',GS+':BeginDeferredActorSpawnFromClass',{'WorldContextObject':'self.self','Owner':'self.self','SpawnTransform':identity},ActorClass=APPLY,CollisionHandlingOverride='AlwaysSpawn')
    actor=call(g,'finish',GS+':FinishSpawningActor',{'Actor':actor,'SpawnTransform':identity});g.node('cast','cast',**{'class':APPLY});g.wire((actor,'cast.Object'));set_value(g,'remember','CompositionPreview','cast.AsBP Den Apply')
    g.set('ghost',APPLY+':PreviewOnly','true');g.wire((get(g,'CompositionPreview'),'ghost.self'));method(g,'begin',APPLY,'BeginLayout',get(g,'CompositionPreview'),{'Document':get(g,'CompositionDocument')});branch(g,'began','begin.Accepted')
    g.set('yaw','CompositionYaw','0');g.set('scale','CompositionScale','1');g.set('active','CompositionPlacing','true');g.set('message','SelectionMessage','Loading all composition parts…');g.call('close','self:SetEditorPanel',Name='');g.call('focus','self:FocusEditorViewport');g.set('yes','local:OK','true');finish_bool(g)
    g.set('fold','RailAutoFold','true');g.call('rail','self:RefreshEditorRail')
    g.call('failed','self:CancelCompositionPreview');g.set('error','CompositionMessage','This composition could not be loaded. No props were added.');g.call('labels','self:RefreshCompositionFeedback')
    g.chain('entry','ready','validate','allowed','cancel','single','parts','selection','document','spawn','finish','cast','remember','ghost','begin','began','yaw','scale','active','message','close','focus','fold','rail','yes','result')
    g.chain('allowed.else','error','labels','result');g.chain('cast.CastFailed','failed','error');g.chain('began.else','failed')
    return g.function('StartCompositionPreview',inputs=[v('Document','object:'+LAYOUT)],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def choose():
    g=Graph();g.call('current','self:CompositionLibraryCurrent');branch(g,'fresh','current.Accepted');method(g,'load',PRESETS,'LoadPreset',get(g,'CompositionService'),{'Name':'entry.Name'});branch(g,'loaded',combine(g,'healthy',[validity(g,'doc','load.Document'),op(g,'status','LessEqual_IntInt','load.Status',B=2)]))
    g.call('start','self:StartCompositionPreview');g.wire(('load.Document','start.Document'));g.chain('entry','current','fresh','load','loaded','start');return g.function('LoadEditorComposition',inputs=[v('Name','string')])


def pose():
    g=Graph();g.set('invalid','CompositionPoseValid','false');branch(g,'ready',combine(g,'available',[get(g,'CompositionPlacing'),get(g,'CompositionPreviewReady'),validity(g,'manager',get(g,'CompositionPreview'))]))
    set_value(g,'origin','CompositionOrigin','entry.Origin')
    rows=prop(g,'rows',LAYOUT,'Entries',get(g,'CompositionDocument'));arr(g,'count','Length',rows);g.get('i','local:Cursor');branch(g,'more',op(g,'within','Less_IntInt','i.Cursor','count.ReturnValue'));arr(g,'row','Get',rows);g.wire(('i.Cursor','row.Index'));unpack(g,'rowdata',ENTRY,'row.Item')
    arr(g,'actor','Get',prop(g,'actors',WORLD,'Placed',get(g,'CompositionPreview')));g.wire(('i.Cursor','actor.Index'));branch(g,'alive',validity(g,'actorvalid','actor.Item'))
    unpack(g,'current',ENTRY,prop(g,'currentvalue',PROP,'Current','actor.Item'));branch(g,'found',call(g,'samekey',STR+'EqualEqual_StrStr',{'A':'rowdata.Key','B':'current.Key'}))
    g.call('transform','self:TransformCompositionPart');g.wire(('row.Item','transform.Value'),('entry.Origin','transform.Origin'),(get(g,'CompositionYaw'),'transform.Yaw'),(get(g,'CompositionScale'),'transform.Scale'));branch(g,'valid','transform.Valid')
    method(g,'preview',PROP,'PreviewTransform','actor.Item',{'Value':'transform.Transformed'});branch(g,'moved','preview.Accepted')
    call(g,'show',ACTOR+':SetActorHiddenInGame',{'self':'actor.Item'},bNewHidden='false');component=prop(g,'component',PROP,'Mesh','actor.Item');call(g,'stencil',PRIMITIVE+':SetCustomDepthStencilValue',{'self':component},Value=15);call(g,'depth',PRIMITIVE+':SetRenderCustomDepth',{'self':component},bValue='true')
    set_value(g,'next','local:Cursor',op(g,'advance','Add_IntInt','i.Cursor',B=1));g.set('yes','CompositionPoseValid','true')
    g.call('cancel','self:CancelCompositionPreview');g.set('error','SelectionMessage','The composition preview became unavailable. No props were added.')
    g.chain('entry','invalid','ready','origin','more','alive','found','transform','valid','preview','moved','show','stencil','depth','next','more');g.chain('more.else','yes')
    for pin in ['found.else','alive.else','valid.else','moved.else']:g.chain(pin,'cancel','error')
    return g.function('SetCompositionPreviewOrigin',inputs=[v('Origin','vector')],locals=[v('Cursor','int','0')])


def poll():
    g=Graph();branch(g,'active',get(g,'CompositionPlacing'));branch(g,'valid',combine(g,'available',[get(g,'UIOpen'),validity(g,'preview',get(g,'CompositionPreview'))]))
    branch(g,'busy',prop(g,'busyvalue',APPLY,'Busy',get(g,'CompositionPreview')));branch(g,'ready',get(g,'CompositionPreviewReady'))
    arr(g,'count','Length',prop(g,'rows',LAYOUT,'Entries',get(g,'CompositionDocument')))
    branch(g,'success',combine(g,'complete',[op(g,'noerrors','EqualEqual_IntInt',prop(g,'errors',APPLY,'ErrorCount',get(g,'CompositionPreview')),B=0),op(g,'allparts','EqualEqual_IntInt',prop(g,'placed',APPLY,'PlacedCount',get(g,'CompositionPreview')),'count.ReturnValue')]))
    g.set('complete','CompositionPreviewReady','true');g.set('message','SelectionMessage','Click to place composition · Shift-click places more · Wheel turns · +/− scales · Esc cancels')
    branch(g,'pc',validity(g,'pcvalid',get(g,'EditorController')));g.call('blocked','self:EditorPointerBlocked');branch(g,'unblocked',neg(g,'clear','blocked.Blocked'));call(g,'ray',PC+':DeprojectMousePositionToWorld',{'self':get(g,'EditorController')});branch(g,'rayok','ray.ReturnValue')
    g.node('self','self');end=op(g,'end','Add_VectorVector','ray.WorldLocation',op(g,'reach','Multiply_VectorFloat','ray.WorldDirection',get(g,'ReachCm')))
    call(g,'trace',KSL+':LineTraceSingle',{'WorldContextObject':'self.self','Start':'ray.WorldLocation','End':end},TraceChannel='TraceTypeQuery1',bTraceComplex='true',DrawDebugType='None',bIgnoreSelf='true');call(g,'hit',GS+':BreakHitResult',{'Hit':'trace.OutHit'})
    fallback=op(g,'fallback','Add_VectorVector','ray.WorldLocation',op(g,'offset','Multiply_VectorFloat','ray.WorldDirection',op(g,'distance','FMin',get(g,'ReachCm'),B=300)))
    point=call(g,'point',KML+':SelectVector',{'A':'hit.ImpactPoint','B':fallback,'bPickA':'trace.ReturnValue'});call(g,'xyz',KML+':BreakVector',{'InVec':point})
    for axis in ['X','Y']:math(g,'snap'+axis,'SnapValue',{'Value':'xyz.'+axis,'Step':get(g,'GridStep')})
    at=call(g,'at',KML+':MakeVector',{'X':'snapX.Snapped','Y':'snapY.Snapped','Z':'xyz.Z'});g.call('pose','self:SetCompositionPreviewOrigin');g.wire((at,'pose.Origin'))
    g.call('cancel','self:CancelCompositionPreview');g.set('error','SelectionMessage','A composition part or material could not be loaded. No props were added.')
    g.chain('entry','active','valid','busy');g.chain('busy.else','ready','pc','blocked','unblocked','rayok','trace','snapX','snapY','pose');g.call('refresh','self:RefreshEditorUI');g.call('refresherror','self:RefreshEditorUI');g.chain('ready.else','success','complete','message','refresh','pc');g.chain('success.else','cancel','error','refresherror');g.chain('valid.else','cancel')
    return g.function('PollCompositionPreview')


def commit():
    g=Graph();g.call('ready','self:CanEdit');branch(g,'allowed',combine(g,'available',['ready.Ready',get(g,'UIOpen'),get(g,'CompositionPlacing'),get(g,'CompositionPreviewReady'),get(g,'CompositionPoseValid')]))
    g.call('validate','self:ValidateComposition');g.wire((get(g,'CompositionDocument'),'validate.Document'));branch(g,'valid','validate.Accepted')
    rows=prop(g,'rows',LAYOUT,'Entries',get(g,'CompositionDocument'));arr(g,'count','Length',rows);g.get('i','local:Cursor');g.get('batch','local:Mutations');g.get('keys','local:Keys');branch(g,'more',op(g,'within','Less_IntInt','i.Cursor','count.ReturnValue'))
    arr(g,'row','Get',rows);g.wire(('i.Cursor','row.Index'));g.call('key','self:NewPlacedKey');arr(g,'exists','Contains','keys.Keys');g.wire(('key.Key','exists.ItemToFind'))
    branch(g,'free',combine(g,'keycheck',[call(g,'nonempty',STR+'NotEqual_StrStr',{'A':'key.Key'},B=''),neg(g,'unique','exists.ReturnValue')]))
    g.call('transform','self:TransformCompositionPart');g.wire(('row.Item','transform.Value'),(get(g,'CompositionOrigin'),'transform.Origin'),(get(g,'CompositionYaw'),'transform.Yaw'),(get(g,'CompositionScale'),'transform.Scale'));branch(g,'posevalid','transform.Valid')
    placed=copy_entry(g,'placed','transform.Transformed',{'Key':'key.Key'},defaults={'Source':'','HasFingerprint':'false','FingerprintMesh':'','FingerprintPosition':'0,0,0'})
    g.node('mutation','make_struct',struct=MUTATION,defaults={'Present':'true'});g.wire((placed,'mutation.Value'));arr(g,'add','Add','batch.Mutations');g.wire(('mutation.ST_DenMutation','add.NewItem'));arr(g,'remember','Add','keys.Keys');g.wire(('key.Key','remember.NewItem'));set_value(g,'next','local:Cursor',op(g,'advance','Add_IntInt','i.Cursor',B=1))
    g.call('commit','self:CommitEdit',Label='Place composition');g.wire(('batch.Mutations','commit.Mutations'));branch(g,'accepted','commit.Accepted');branch(g,'repeat','entry.Repeat');g.call('cancel','self:CancelCompositionPreview');g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','ready','allowed','validate','valid','more','key','free','transform','posevalid','add','remember','next','more');g.chain('more.else','commit','accepted','repeat','yes','result');g.chain('repeat.else','cancel','yes')
    for pin in ['allowed.else','valid.else','free.else','posevalid.else','accepted.else']:g.chain(pin,'result')
    return g.function('CommitComposition',inputs=[v('Repeat','bool')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false'),v('Cursor','int','0'),v('Mutations','struct:'+MUTATION+'[]'),v('Keys','string[]')])


def click():
    g=Graph();branch(g,'pressed',op(g,'down','Greater_DoubleDouble','entry.Value',B=.5));g.call('blocked','self:EditorPointerBlocked');branch(g,'allowed',neg(g,'clear','blocked.Blocked'));g.call('poll','self:PollCompositionPreview');g.call('commit','self:CommitComposition');g.wire((prop(g,'shift',RIG,'bFast',get(g,'EditorRig')),'commit.Repeat'));g.chain('entry','pressed','blocked','allowed','poll','commit');return g.function('CompositionPointerButton',inputs=[v('Value','double')])


def adjust():
    g=Graph();branch(g,'active',get(g,'CompositionPlacing'));branch(g,'scaling',call(g,'scaleaction',STR+'EqualEqual_StrStr',{'A':'entry.Name'},B='scale'))
    factor=call(g,'factor',KML+':MultiplyMultiply_FloatFloat',{'Exp':'entry.Steps'},Base=1.05);scale=call(g,'clamp',KML+':FClamp',{'Value':op(g,'scaled','Multiply_DoubleDouble',get(g,'CompositionScale'),factor)},Min=.05,Max=20);set_value(g,'scale','CompositionScale',scale)
    fine=call(g,'fine',STR+'EqualEqual_StrStr',{'A':'entry.Name'},B='rotate_fine');degrees=call(g,'degrees',KML+':SelectFloat',{'bPickA':fine},A=1,B=15)
    set_value(g,'yaw','CompositionYaw',op(g,'turn','Add_DoubleDouble',get(g,'CompositionYaw'),op(g,'delta','Multiply_DoubleDouble',degrees,'entry.Steps')))
    g.call('pose','self:SetCompositionPreviewOrigin');g.wire((get(g,'CompositionOrigin'),'pose.Origin'));g.chain('entry','active','scaling','scale','pose');g.chain('scaling.else','yaw','pose');return g.function('AdjustComposition',inputs=[v('Name','string'),v('Steps','double')])


def variables():return [v('CompositionDocument','object:'+LAYOUT),v('CompositionPreview','object:'+APPLY),v('CompositionPlacing','bool'),v('CompositionPreviewReady','bool'),v('CompositionPoseValid','bool'),v('CompositionOrigin','vector'),v('CompositionYaw','double'),v('CompositionScale','double','1')]
def functions():return [transform(),validate(),cancel(),start(),choose(),pose(),poll(),commit(),click(),adjust()]
