"""Catalog placement owns a cancellable load job and a transient collisionless prop.

Neither the preview nor an asset request enters the layout/history. Only an
accepted click creates a fresh placed entry through the normal transaction path.
"""
from graph import Graph, variable as v, KML, KSL, GS
from runtime import ENTRY, MUTATION, arr, unpack
from runtime_store import call, branch, combine, STR
from runtime_world import ACTOR, PROP, MESH, PRIMITIVE, set_value, validity, finish_bool
from runtime_assets import JOB
from runtime_apply import get, clock
from runtime_session import prop, method
from runtime_transform import copy_entry
from runtime_catalog import CATALOG
from runtime_editor_assets import RIG
from runtime_editor_host import PC
from runtime_gizmo_controller import op, neg, math


def spawn(g,name,cls,field):
    xf=call(g,name+'transform',KML+':MakeTransform',Scale='1,1,1')
    actor=call(g,name+'spawn',GS+':BeginDeferredActorSpawnFromClass',{'WorldContextObject':'self.self','Owner':'self.self','SpawnTransform':xf},ActorClass=cls,CollisionHandlingOverride='AlwaysSpawn')
    done=call(g,name+'finish',GS+':FinishSpawningActor',{'Actor':actor,'SpawnTransform':xf})
    g.node(name+'cast','cast',**{'class':cls});g.wire((done,name+'cast.Object'))
    pin='AsBP Den Asset Job' if cls==JOB else 'AsBP Den Placed Prop'
    set_value(g,name+'save',field,name+'cast.'+pin)
    g.chain(name+'spawn',name+'finish',name+'cast',name+'save')


def cancel():
    g=Graph();g.set('stop','PlacementActive','false');g.set('pose','PlacementPoseValid','false');previous='pose'
    for field in ['PlacementJob','PlacementGhost']:
        branch(g,field+'valid',validity(g,field+'check',get(g,field)));call(g,field+'destroy',ACTOR+':K2_DestroyActor',{'self':get(g,field)})
        g.set(field+'clear',field);g.chain(previous,field+'valid',field+'destroy',field+'clear');g.chain(field+'valid.else',field+'clear');previous=field+'clear'
    for field in ['PlacementMesh','PlacementPath','PlacementEntry','PlacementIndex','SelectionMessage']:
        g.set(field+'clear',field);g.chain(previous,field+'clear');previous=field+'clear'
    # A drop, Esc or failure gives the rail back its pin.
    branch(g,'folded',get(g,'RailAutoFold'));g.set('unfold','RailAutoFold','false');g.call('rail','self:RefreshEditorRail');g.chain(previous,'folded','unfold','rail')
    g.chain('entry','stop','pose');return g.function('CancelPlacement')


def choose():
    g=Graph();g.node('self','self');g.call('ready','self:CanEdit')
    branch(g,'available',combine(g,'allowed',['ready.Ready',get(g,'UIOpen'),neg(g,'idle',get(g,'DragActive')),validity(g,'provider',get(g,'CatalogProvider')),call(g,'panel',STR+'EqualEqual_StrStr',{'A':get(g,'ActivePanel')},B='catalog')]))
    # A card is valid only for this exact completed query and a displayed result.
    call(g,'split',STR+'Split',{'SourceString':'entry.Key'},InStr=':',SearchCase='CaseSensitive',SearchDir='FromStart');branch(g,'splitok','split.ReturnValue')
    revision=call(g,'revision',STR+'Conv_StringToInt',{'InString':'split.LeftS'});index=call(g,'index',STR+'Conv_StringToInt',{'InString':'split.RightS'})
    checks=[]
    for name,value,source in [('rev',revision,'split.LeftS'),('idx',index,'split.RightS')]:
        text=call(g,name+'text',STR+'Conv_IntToString',{'InInt':value});checks.append(call(g,name+'exact',STR+'EqualEqual_StrStr',{'A':text,'B':source}))
    checks += [op(g,'same','EqualEqual_IntInt',revision,prop(g,'current',CATALOG,'Revision',get(g,'CatalogProvider'))),prop(g,'readyquery',CATALOG,'Ready',get(g,'CatalogProvider'))]
    arr(g,'contains','Contains',prop(g,'results',CATALOG,'Results',get(g,'CatalogProvider')));g.wire((index,'contains.ItemToFind'));checks.append('contains.ReturnValue')
    branch(g,'valid',combine(g,'validkey',checks));method(g,'read',CATALOG,'ReadItem',get(g,'CatalogProvider'),{'Index':index});branch(g,'found','read.Found')
    # Capture before closing the panel cancels its query.
    set_value(g,'capturepath','local:ChosenPath','read.Path');set_value(g,'captureindex','local:ChosenIndex',index)
    g.call('cancel','self:CancelPlacement');g.call('clear','self:ClearSelection');g.call('press','self:ClearSurfacePress')
    g.get('path','local:ChosenPath');g.get('chosen','local:ChosenIndex');set_value(g,'pathsave','PlacementPath','path.ChosenPath');set_value(g,'indexsave','PlacementIndex','chosen.ChosenIndex')
    g.set('active','PlacementActive','true');set_value(g,'time','PlacementStartedAt',clock(g,'now'));spawn(g,'job',JOB,'PlacementJob')
    method(g,'request',JOB,'Request',get(g,'PlacementJob'),{'Path':get(g,'PlacementPath')});branch(g,'accepted','request.Accepted')
    g.call('close','self:SetEditorPanel',Name='');g.call('focus','self:FocusEditorViewport');g.set('message','SelectionMessage','Loading prop…');g.call('failed','self:CancelPlacement')
    g.set('fold','RailAutoFold','true');g.call('rail','self:RefreshEditorRail')
    g.chain('entry','ready','available','splitok','valid','read','found','capturepath','captureindex','cancel','clear','press','pathsave','indexsave','active','time','jobspawn');g.chain('jobsave','request','accepted','close','focus','message','fold','rail');g.chain('accepted.else','failed');g.chain('jobcast.CastFailed','failed')
    return g.function('ChooseCatalogItem',inputs=[v('Key','string')],locals=[v('ChosenPath','string'),v('ChosenIndex','int')])


def create_preview():
    g=Graph();g.node('self','self');branch(g,'active',combine(g,'allowed',[get(g,'PlacementActive'),validity(g,'loaded','entry.Mesh'),neg(g,'noghost',validity(g,'ghost',get(g,'PlacementGhost')))]))
    path=call(g,'path',KSL+':GetPathName',{'Object':'entry.Mesh'});branch(g,'same',call(g,'samepath',STR+'EqualEqual_StrStr',{'A':path,'B':get(g,'PlacementPath')}))
    set_value(g,'mesh','PlacementMesh','entry.Mesh')
    yaw=call(g,'rotation',ACTOR+':K2_GetActorRotation',{'self':get(g,'EditorRig')});call(g,'parts',KML+':BreakRotator',{'InRot':yaw});math(g,'snap','SnapValue',{'Value':'parts.Yaw'},Step=90)
    rot=call(g,'facing',KML+':MakeRotator',{'Yaw':op(g,'opposite','Add_DoubleDouble','snap.Snapped',B=180)})
    g.node('value','make_struct',struct=ENTRY,defaults={'Kind':'0','Key':'preview','Scale':'1,1,1','HasPosition':'true','HasRotation':'true','HasScale':'true'});g.wire((get(g,'PlacementPath'),'value.Mesh'),(rot,'value.Rotation'))
    set_value(g,'entrysave','PlacementEntry','value.ST_DenEntry');spawn(g,'ghost',PROP,'PlacementGhost')
    call(g,'hide',ACTOR+':SetActorHiddenInGame',{'self':get(g,'PlacementGhost')},bNewHidden='true')
    method(g,'configure',PROP,'Configure',get(g,'PlacementGhost'),{'Value':get(g,'PlacementEntry'),'LoadedMesh':'entry.Mesh'},Ghost='true');branch(g,'configured','configure.Accepted')
    component=prop(g,'component',PROP,'Mesh',get(g,'PlacementGhost'));call(g,'outline',PRIMITIVE+':SetCustomDepthStencilValue',{'self':component},Value=15);call(g,'depth',PRIMITIVE+':SetRenderCustomDepth',{'self':component},bValue='true')
    g.set('message','SelectionMessage','Click to place · Shift-click places more · Wheel turns · Esc cancels');g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','active','same','mesh','snap','entrysave','ghostspawn');g.chain('ghostsave','hide','configure','configured','outline','depth','message','yes','result')
    for pin in ['active.else','same.else','ghostcast.CastFailed','configured.else']:g.chain(pin,'result')
    return g.function('CreatePlacementPreview',inputs=[v('Mesh','object:'+MESH)],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def update():
    g=Graph();g.node('self','self');branch(g,'active',combine(g,'allowed',[get(g,'UIOpen'),get(g,'PlacementActive'),validity(g,'ghost',get(g,'PlacementGhost'))]))
    direction=op(g,'unit','Normal','entry.Direction',Tolerance=1e-12);branch(g,'direction',op(g,'nonzero','Greater_DoubleDouble',op(g,'length','VSize',direction),B=.5))
    end=op(g,'end','Add_VectorVector','entry.Origin',op(g,'reach','Multiply_VectorFloat',direction,get(g,'ReachCm')))
    call(g,'trace',KSL+':LineTraceSingle',{'WorldContextObject':'self.self','Start':'entry.Origin','End':end},TraceChannel='TraceTypeQuery1',bTraceComplex='true',DrawDebugType='None',bIgnoreSelf='true')
    call(g,'hit',GS+':BreakHitResult',{'Hit':'trace.OutHit'})
    fallback=op(g,'fallback','Add_VectorVector','entry.Origin',op(g,'distance','Multiply_VectorFloat',direction,op(g,'distanceclamp','FMin',get(g,'ReachCm'),B=300)))
    point=call(g,'point',KML+':SelectVector',{'A':'hit.ImpactPoint','B':fallback,'bPickA':'trace.ReturnValue'});call(g,'parts',KML+':BreakVector',{'InVec':point})
    for axis in ['X','Y']:math(g,'snap'+axis,'SnapValue',{'Value':'parts.'+axis,'Step':get(g,'GridStep')})
    # Placement rotates around yaw; use the scaled asset bottom, independent of world position.
    bounds=call(g,'bounds',MESH+':GetBounds',{'self':get(g,'PlacementMesh')});call(g,'box',KML+':BreakBoxSphereBounds',{'InBoxSphereBounds':bounds});call(g,'origin',KML+':BreakVector',{'InVec':'box.Origin'});call(g,'extent',KML+':BreakVector',{'InVec':'box.BoxExtent'})
    unpack(g,'value',ENTRY,get(g,'PlacementEntry'));call(g,'scale',KML+':BreakVector',{'InVec':'value.Scale'})
    bottom=op(g,'bottom','Multiply_DoubleDouble',op(g,'low','Subtract_DoubleDouble','origin.Z','extent.Z'),'scale.Z')
    position=call(g,'position',KML+':MakeVector',{'X':'snapX.Snapped','Y':'snapY.Snapped','Z':op(g,'z','Subtract_DoubleDouble','parts.Z',bottom)})
    value=copy_entry(g,'updated',get(g,'PlacementEntry'),{'Position':position});set_value(g,'save','PlacementEntry',value)
    method(g,'preview',PROP,'PreviewTransform',get(g,'PlacementGhost'),{'Value':get(g,'PlacementEntry')});set_value(g,'valid','PlacementPoseValid','preview.Accepted');call(g,'show',ACTOR+':SetActorHiddenInGame',{'self':get(g,'PlacementGhost')},bNewHidden='false')
    g.chain('entry','active','direction','trace','snapX','snapY','save','preview','valid','show')
    return g.function('UpdatePlacementRay',inputs=[v('Origin','vector'),v('Direction','vector')])


def poll():
    g=Graph();branch(g,'active',get(g,'PlacementActive'));branch(g,'open',get(g,'UIOpen'));branch(g,'job',validity(g,'jobvalid',get(g,'PlacementJob')))
    branch(g,'done',prop(g,'donevalue',JOB,'Done',get(g,'PlacementJob')));g.node('mesh','cast',**{'class':MESH});g.wire((prop(g,'loaded',JOB,'Result',get(g,'PlacementJob')),'mesh.Object'))
    g.call('create','self:CreatePlacementPreview');g.wire(('mesh.AsStatic Mesh','create.Mesh'));branch(g,'created','create.Accepted')
    call(g,'destroy',ACTOR+':K2_DestroyActor',{'self':get(g,'PlacementJob')});g.set('release','PlacementJob')
    branch(g,'timeout',op(g,'timelimit','Greater_DoubleDouble',op(g,'elapsed','Subtract_DoubleDouble',clock(g,'now'),get(g,'PlacementStartedAt')),B=30))
    g.call('cancel','self:CancelPlacement');g.set('error','SelectionMessage','This prop could not be loaded. Choose another prop or try again.')
    branch(g,'pc',validity(g,'pcvalid',get(g,'EditorController')));g.call('blocked','self:EditorPointerBlocked');branch(g,'unblocked',neg(g,'clear','blocked.Blocked'))
    call(g,'ray',PC+':DeprojectMousePositionToWorld',{'self':get(g,'EditorController')});branch(g,'valid','ray.ReturnValue');g.call('update','self:UpdatePlacementRay');g.wire(('ray.WorldLocation','update.Origin'),('ray.WorldDirection','update.Direction'))
    g.chain('entry','active','open','job','done','mesh','create','created','destroy','release','pc','blocked','unblocked','valid','update');g.chain('job.else','pc');g.chain('done.else','timeout','cancel','error');g.chain('open.else','cancel')
    for pin in ['mesh.CastFailed','created.else']:g.chain(pin,'cancel')
    return g.function('PollPlacement')


def commit():
    g=Graph();g.call('ready','self:CanEdit');branch(g,'allowed',combine(g,'allowedcheck',['ready.Ready',get(g,'UIOpen'),get(g,'PlacementActive'),get(g,'PlacementPoseValid'),validity(g,'ghost',get(g,'PlacementGhost'))]))
    g.call('key','self:NewPlacedKey');branch(g,'keyvalid',call(g,'nonempty',STR+'NotEqual_StrStr',{'A':'key.Key'},B=''))
    value=copy_entry(g,'placed',get(g,'PlacementEntry'),{'Key':'key.Key'})
    g.node('mutation','make_struct',struct=MUTATION,defaults={'Present':'true'});g.wire((value,'mutation.Value'));g.get('mutations','local:PlacementMutations');arr(g,'add','Add','mutations.PlacementMutations');g.wire(('mutation.ST_DenMutation','add.NewItem'))
    g.call('commit','self:CommitEdit',Label='Place');g.wire(('mutations.PlacementMutations','commit.Mutations'));branch(g,'accepted','commit.Accepted')
    method(g,'recent',CATALOG,'Remember',get(g,'CatalogProvider'),{'Index':get(g,'PlacementIndex')});g.call('persistrecent','self:SavePlacementRecent');branch(g,'repeat','entry.Repeat');g.call('cancel','self:CancelPlacement');g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','ready','allowed','key','keyvalid','add','commit','accepted','recent','persistrecent','repeat','yes','result');set_value(g,'pending','PendingCopyKey','key.Key');g.set('sourcekind','CopySourceKind','-1');g.set('sourcekey','CopySourceKey','');g.chain('repeat.else','cancel','pending','sourcekind','sourcekey','yes')
    for pin in ['allowed.else','keyvalid.else','accepted.else']:g.chain(pin,'result')
    return g.function('CommitPlacement',inputs=[v('Repeat','bool')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false'),v('PlacementMutations','struct:'+MUTATION+'[]')])


def click():
    g=Graph();branch(g,'pressed',op(g,'down','Greater_DoubleDouble','entry.Value',B=.5));g.call('blocked','self:EditorPointerBlocked');branch(g,'allowed',neg(g,'unblocked','blocked.Blocked'))
    g.call('poll','self:PollPlacement');g.call('commit','self:CommitPlacement');g.wire((prop(g,'shift',RIG,'bFast',get(g,'EditorRig')),'commit.Repeat'));g.chain('entry','pressed','blocked','allowed','poll','commit')
    return g.function('PlacementPointerButton',inputs=[v('Value','double')])


def adjust():
    g=Graph();branch(g,'active',combine(g,'allowed',[get(g,'PlacementActive'),validity(g,'ghost',get(g,'PlacementGhost'))]));unpack(g,'value',ENTRY,get(g,'PlacementEntry'))
    branch(g,'scale',call(g,'scalename',STR+'EqualEqual_StrStr',{'A':'entry.Name'},B='scale'))
    call(g,'parts',KML+':BreakVector',{'InVec':'value.Scale'});factor=call(g,'factor',KML+':MultiplyMultiply_FloatFloat',{'Exp':'entry.Steps'},Base=1.05)
    size=call(g,'clamp',KML+':FClamp',{'Value':op(g,'size','Multiply_DoubleDouble','parts.X',factor)},Min=.05,Max=20)
    vector=call(g,'uniform',KML+':MakeVector',{'X':size,'Y':size,'Z':size});scaled=copy_entry(g,'scaled',get(g,'PlacementEntry'),{'Scale':vector});set_value(g,'sizesave','PlacementEntry',scaled)
    fine=call(g,'fine',STR+'EqualEqual_StrStr',{'A':'entry.Name'},B='rotate_fine');degrees=call(g,'degrees',KML+':SelectFloat',{'bPickA':fine},A=1,B=15)
    call(g,'rotparts',KML+':BreakRotator',{'InRot':'value.Rotation'});yaw=op(g,'yaw','Add_DoubleDouble','rotparts.Yaw',op(g,'delta','Multiply_DoubleDouble',degrees,'entry.Steps'));rotation=call(g,'rotation',KML+':MakeRotator',{'Yaw':yaw})
    rotated=copy_entry(g,'rotated',get(g,'PlacementEntry'),{'Rotation':rotation});set_value(g,'rotsave','PlacementEntry',rotated)
    g.chain('entry','active','scale','sizesave');g.chain('scale.else','rotsave');return g.function('AdjustPlacement',inputs=[v('Name','string'),v('Steps','double')])


def variables():return [v('PlacementActive','bool'),v('PlacementPoseValid','bool'),v('PlacementJob','object:'+JOB),v('PlacementGhost','object:'+PROP),v('PlacementMesh','object:'+MESH),v('PlacementPath','string'),v('PlacementIndex','int'),v('PlacementStartedAt','double'),v('PlacementEntry','struct:'+ENTRY)]
def functions():return [cancel(),choose(),create_preview(),update(),poll(),commit(),click(),adjust()]
