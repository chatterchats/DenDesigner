"""Native gizmo lifecycle, pointer routing and constrained drag previews.

Only the material job performs asset acquisition (asynchronously). Per-frame
hover and transforms use captured native references and Blueprint math.
"""
from graph import Graph, variable as v, KML, GS
from runtime import unpack
from runtime_store import call, branch, combine
from runtime_world import ACTOR, SCENE, MATERIAL, validity, set_value, finish_bool
from runtime_apply import get, clock
from runtime_session import method, prop
from runtime_assets import JOB
from runtime_pick import FACT
from runtime_editor_assets import BUS, RIG
from runtime_editor_host import PC, WIDGET, PANELS, widget, style_toggle
from runtime_gizmo_math import MATH
from runtime_gizmo_visual import VISUAL, OVERLAY


def eq(g,name,a,b):return call(g,name,KML+':EqualEqual_IntInt',{'A':a},B=b)
def neg(g,name,a):return call(g,name,KML+':Not_PreBool',{'A':a})
def op(g,name,fn,a,b=None,**defaults):return call(g,name,KML+':'+fn,{'A':a,**({'B':b} if b else {})},**defaults)
def math(g,name,fn,inputs=None,**defaults):return method(g,name,MATH,fn,get(g,'GizmoMath'),inputs,**defaults)


def spawn(g,name,cls,pin,member):
    xf=call(g,name+'xf',KML+':MakeTransform',Scale='1,1,1')
    pending=call(g,name+'spawn',GS+':BeginDeferredActorSpawnFromClass',{'WorldContextObject':'self.self','Owner':'self.self','SpawnTransform':xf},ActorClass=cls,CollisionHandlingOverride='AlwaysSpawn')
    result=call(g,name+'finish',GS+':FinishSpawningActor',{'Actor':pending,'SpawnTransform':xf})
    g.node(name+'cast','cast',**{'class':cls});g.wire((result,name+'cast.Object'))
    set_value(g,name+'save',member,name+'cast.'+pin)
    g.chain(name+'spawn',name+'finish',name+'cast',name+'save')


def initialize():
    g=Graph();g.node('self','self');g.call('dispose','self:DestroyEditorGizmo')
    obj=call(g,'create',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=MATH)
    g.node('cast','cast',**{'class':MATH});g.wire((obj,'cast.Object'));set_value(g,'math','GizmoMath','cast.AsBP Den Gizmo Math')
    spawn(g,'visual',VISUAL,'AsBP Den Gizmo Visual','GizmoVisual');spawn(g,'job',JOB,'AsBP Den Asset Job','GizmoJob')
    method(g,'request',JOB,'Request',get(g,'GizmoJob'),Path=OVERLAY);set_value(g,'started','GizmoRequestAt',clock(g,'now'))
    g.chain('entry','dispose','create','cast','math','visualspawn');g.chain('visualsave','jobspawn');g.chain('jobsave','request','started')
    return g.function('InitializeEditorGizmo')


def destroy():
    g=Graph();g.call('cancel','self:EndSelectionDrag',Commit='false');previous='cancel'
    for name in ['GizmoJob','GizmoVisual']:
        branch(g,name+'valid',validity(g,name+'check',get(g,name)));call(g,name+'destroy',ACTOR+':K2_DestroyActor',{'self':get(g,name)})
        g.set(name+'clear',name);g.chain(previous,name+'valid',name+'destroy',name+'clear');g.chain(name+'valid.else',name+'clear');previous=name+'clear'
    for name in ['GizmoMath','GizmoHoverKind','GizmoHoverAxis','GizmoDragKind','GizmoDragAxis']:
        g.set(name+'clear',name);g.chain(previous,name+'clear');previous=name+'clear'
    g.chain('entry','cancel')
    return g.function('DestroyEditorGizmo')


def poll_material():
    g=Graph();branch(g,'valid',combine(g,'refs',[validity(g,'jobvalid',get(g,'GizmoJob')),validity(g,'visualvalid',get(g,'GizmoVisual'))]))
    branch(g,'done',prop(g,'doneget',JOB,'Done',get(g,'GizmoJob')))
    result=prop(g,'result',JOB,'Result',get(g,'GizmoJob'));g.node('cast','cast',**{'class':MATERIAL});g.wire((result,'cast.Object'))
    method(g,'build',VISUAL,'BeginBuild',get(g,'GizmoVisual'),{'Material':'cast.AsMaterial Interface'});branch(g,'accepted','build.Accepted')
    elapsed=op(g,'elapsed','Subtract_DoubleDouble',clock(g,'now'),get(g,'GizmoRequestAt'))
    branch(g,'timeout',op(g,'expired','GreaterEqual_DoubleDouble',elapsed,B=30))
    g.set('failed','SelectionMessage','Gizmo material could not load. Numeric transforms remain available.')
    call(g,'release',ACTOR+':K2_DestroyActor',{'self':get(g,'GizmoJob')});g.set('clear','GizmoJob')
    g.chain('entry','valid','done','cast','build','accepted','release','clear');g.chain('done.else','timeout','failed','release')
    g.chain('cast.CastFailed','failed');g.chain('accepted.else','failed')
    return g.function('PollGizmoMaterial')


def blocked():
    g=Graph();checks=[get(g,'Looking'),get(g,'HelpOpen'),op(g,'modal','Greater_IntInt',get(g,'ConfirmMode'),B=0)]
    branch(g,'state',combine(g,'blockedstate',checks,True));g.set('yes','local:OK','true');finish_bool(g,'Blocked')
    branch(g,'bus',validity(g,'busvalid',get(g,'InputBus')));method(g,'typing',BUS,'IsTyping',get(g,'InputBus'));branch(g,'typingcheck','typing.Typing')
    previous='typingcheck.else'
    for i,(var,field) in enumerate([(var,'Panel') for var,_,_ in PANELS]+[('Toolbar','Feedback'),('Toolbar','LibraryTabs')]):
        name='panel'+str(i);branch(g,name+'valid',validity(g,name+'check',get(g,var)))
        panel=widget(g,name+'widget',var,field)
        hovered=call(g,name+'hover',WIDGET+':IsHovered',{'self':panel});visible=call(g,name+'visible',WIDGET+':IsVisible',{'self':get(g,var)})
        branch(g,name+'over',combine(g,name+'both',[hovered,visible]))
        g.node(name+'next','sequence',outputs=1)
        g.chain(previous,name+'valid',name+'over','yes');g.chain(name+'valid.else',name+'next');g.chain(name+'over.else',name+'next');previous=name+'next.then_0'
        if i==0:g.chain('bus.else',name+'valid')
    g.chain('entry','state','yes','result');g.chain('state.else','bus','typing','typingcheck','yes');g.chain(previous,'result')
    return g.function('EditorPointerBlocked',outputs=[v('Blocked','bool')],locals=[v('OK','bool','false')])


def frame():
    g=Graph();unpack(g,'facts',FACT,get(g,'Selected'));g.call('ready','self:CanEdit')
    branch(g,'available',combine(g,'refs',['ready.Ready',get(g,'UIOpen'),get(g,'HasSelection'),validity(g,'component','facts.Component'),validity(g,'rig',get(g,'EditorRig')),validity(g,'math',get(g,'GizmoMath'))]))
    center=call(g,'center',SCENE+':K2_GetComponentLocation',{'self':'facts.Component'});rotation=call(g,'rotation',SCENE+':K2_GetComponentRotation',{'self':'facts.Component'})
    camera=call(g,'camera',ACTOR+':K2_GetActorLocation',{'self':get(g,'EditorRig')})
    distance=op(g,'distance','VSize',op(g,'difference','Subtract_VectorVector',center,camera))
    math(g,'size', 'SizeFor',{'Distance':distance})
    size=call(g,'frozen',KML+':SelectFloat',{'A':get(g,'GizmoDragSize'),'B':'size.Size','bPickA':combine(g,'freezesize',[get(g,'DragActive'),neg(g,'notsurface',get(g,'SurfaceDragging'))])})
    for name,source in [('Center',center),('Rotation',rotation),('Size',size)]:set_value(g,'save'+name,'local:Result'+name,source);g.get('out'+name,'local:Result'+name);g.wire(('out'+name+'.Result'+name,'result.'+name))
    g.set('yes','local:OK','true');finish_bool(g,'Valid')
    g.chain('entry','ready','available','size','saveCenter','saveRotation','saveSize','yes','result');g.chain('available.else','result')
    return g.function('GetGizmoFrame',outputs=[v('Valid','bool'),v('Center','vector'),v('Rotation','rotator'),v('Size','double')],locals=[v('OK','bool','false'),v('ResultCenter','vector'),v('ResultRotation','rotator'),v('ResultSize','double')])


def choose_axis(g,prefix,index):
    yz=call(g,prefix+'yz',KML+':SelectVector',{'A':'axes.Y','B':'axes.Z','bPickA':eq(g,prefix+'isY',index,2)})
    return call(g,prefix+'xyz',KML+':SelectVector',{'A':'axes.X','B':yz,'bPickA':eq(g,prefix+'isX',index,1)})


def begin_drag():
    g=Graph();g.call('frame','self:GetGizmoFrame');branch(g,'valid','frame.Valid')
    math(g,'pick','PickHandle',{'Origin':'entry.Origin','Direction':'entry.Direction','Center':'frame.Center','Size':'frame.Size','Mode':get(g,'GizmoMode'),'Rotation':'frame.Rotation'})
    branch(g,'hit',op(g,'any','Greater_IntInt','pick.Kind',B=0))
    math(g,'axes','FrameAxes',{'Mode':get(g,'GizmoMode'),'Rotation':'frame.Rotation'})
    axis=choose_axis(g,'selected','pick.Axis')
    right=call(g,'right',ACTOR+':GetActorRightVector',{'self':get(g,'EditorRig')});up=call(g,'up',ACTOR+':GetActorUpVector',{'self':get(g,'EditorRig')})
    screenaxis=op(g,'screenaxis','Normal',op(g,'screenplus','Add_VectorVector',right,up),Tolerance=1e-12)
    along=call(g,'dragaxis',KML+':SelectVector',{'A':screenaxis,'B':axis,'bPickA':eq(g,'uniform','pick.Kind',4)})
    sum_=op(g,'sum','Add_VectorVector',op(g,'xy','Add_VectorVector','axes.X','axes.Y'),'axes.Z')
    diagonal=op(g,'diagonal','Normal',op(g,'exclude','Subtract_VectorVector',sum_,axis),Tolerance=1e-12)
    isplane=combine(g,'planeorring',[eq(g,'plane','pick.Kind',2),eq(g,'ring','pick.Kind',3)],True);branch(g,'planar',isplane)
    for name,fn,ax in [('planehit','PlanePoint',axis),('axishit','AxisParam',along)]:
        math(g,name,fn,{'Origin':'entry.Origin','Direction':'entry.Direction','Center':'frame.Center','Axis':ax});branch(g,name+'valid',name+'.Valid')
    g.call('begin','self:BeginSelectionDrag');g.wire((get(g,'GizmoMode'),'begin.Mode'));branch(g,'accepted','begin.Accepted')
    previous='accepted'
    for name,source in [('GizmoDragOrigin','entry.Origin'),('GizmoDragDirection','entry.Direction'),('GizmoDragCenter','frame.Center'),('GizmoDragSize','frame.Size'),('GizmoDragKind','pick.Kind'),('GizmoDragAxis','pick.Axis'),('GizmoDragVector',along),('GizmoDragDiagonal',diagonal)]:
        set_value(g,'save'+name,name,source);g.chain(previous,'save'+name);previous='save'+name
    g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','frame','valid','pick','hit','axes','planar','planehit','planehitvalid','begin','accepted');g.chain('planar.else','axishit','axishitvalid','begin');g.chain(previous,'yes','result')
    for pin in ['valid.else','hit.else','planehitvalid.else','axishitvalid.else','accepted.else']:g.chain(pin,'result')
    return g.function('BeginGizmoDrag',inputs=[v('Origin','vector'),v('Direction','vector')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def drag_delta(g,name,fn,extra=None):
    inputs={'StartOrigin':get(g,'GizmoDragOrigin'),'StartDirection':get(g,'GizmoDragDirection'),'CurrentOrigin':'entry.Origin','CurrentDirection':'entry.Direction','Center':get(g,'GizmoDragCenter'),'Axis':get(g,'GizmoDragVector')}
    math(g,name,fn,{**inputs,**(extra or {})});branch(g,name+'valid',name+'.Valid')


def update_drag():
    g=Graph();g.call('ready','self:CanContinueSelectionDrag');branch(g,'readycheck',combine(g,'refs',['ready.Ready',validity(g,'mathvalid',get(g,'GizmoMath')),validity(g,'rigvalid',get(g,'EditorRig'))]))
    branch(g,'ring',eq(g,'ringkind',get(g,'GizmoDragKind'),3));branch(g,'plane',eq(g,'planekind',get(g,'GizmoDragKind'),2))
    step=call(g,'anglestep',KML+':SelectFloat',{'bPickA':prop(g,'fast',RIG,'bFast',get(g,'EditorRig'))},A=15,B=1)
    drag_delta(g,'ringdelta','RingDelta',{'Step':step});math(g,'rotated','RotateFromDrag',{'Rotation':get(g,'DragStartRotation'),'Axis':get(g,'GizmoDragVector'),'Degrees':'ringdelta.Degrees'})
    g.call('previewring','self:PreviewSelectionDrag');g.wire(('rotated.Rotated','previewring.Rotation'))
    drag_delta(g,'planedelta','PlaneDelta');branch(g,'planemove',eq(g,'movingplane',get(g,'DragMode'),1))
    call(g,'offset',KML+':BreakVector',{'InVec':'planedelta.Offset'});parts={}
    previous='planemove'
    for axis in ['X','Y','Z']:
        math(g,'snap'+axis,'SnapValue',{'Value':'offset.'+axis,'Step':get(g,'GridStep')});g.chain(previous,'snap'+axis);previous='snap'+axis;parts[axis]='snap'+axis+'.Snapped'
    snapped=call(g,'snapped',KML+':MakeVector',parts);position=op(g,'position','Add_VectorVector',get(g,'DragStartPosition'),snapped)
    g.call('previewplane','self:PreviewSelectionDrag');g.wire((position,'previewplane.Position'));g.chain(previous,'previewplane')
    set_value(g,'planealong','local:ResultAlong',op(g,'projection','Dot_VectorVector','planedelta.Offset',get(g,'GizmoDragDiagonal')))
    drag_delta(g,'axisdelta','AxisDelta');branch(g,'axismove',eq(g,'movingaxis',get(g,'DragMode'),1))
    math(g,'snapaxis','SnapValue',{'Value':'axisdelta.Distance','Step':get(g,'GridStep')})
    pos=op(g,'axisposition','Add_VectorVector',get(g,'DragStartPosition'),op(g,'axisoffset','Multiply_VectorFloat',get(g,'GizmoDragVector'),'snapaxis.Snapped'))
    g.call('previewaxis','self:PreviewSelectionDrag');g.wire((pos,'previewaxis.Position'));set_value(g,'axisalong','local:ResultAlong','axisdelta.Distance')
    g.get('along','local:ResultAlong');math(g,'scaled','ScaleFromDrag',{'Scale':get(g,'DragStartScale'),'Kind':get(g,'GizmoDragKind'),'Axis':get(g,'GizmoDragAxis'),'Along':'along.ResultAlong','Size':get(g,'GizmoDragSize')})
    branch(g,'scalevalid','scaled.Valid');g.call('previewscale','self:PreviewSelectionDrag');g.wire(('scaled.Scaled','previewscale.Scale'))
    g.chain('entry','ready','readycheck','ring','ringdelta','ringdeltavalid','rotated','previewring');g.chain('ring.else','plane','planedelta','planedeltavalid','planemove')
    g.chain('planemove.else','planealong','scaled','scalevalid','previewscale');g.chain('plane.else','axisdelta','axisdeltavalid','axismove','snapaxis','previewaxis');g.chain('axismove.else','axisalong','scaled')
    return g.function('UpdateGizmoDrag',inputs=[v('Origin','vector'),v('Direction','vector')],locals=[v('ResultAlong','double')])


def click():
    g=Graph();branch(g,'pressed',op(g,'down','Greater_DoubleDouble','entry.Value',B=.5));branch(g,'active',get(g,'DragActive'))
    branch(g,'pc',validity(g,'pcvalid',get(g,'EditorController')))
    call(g,'releaseRay',PC+':DeprojectMousePositionToWorld',{'self':get(g,'EditorController')});branch(g,'releasevalid','releaseRay.ReturnValue')
    g.call('update','self:UpdateGizmoDrag');g.wire(('releaseRay.WorldLocation','update.Origin'),('releaseRay.WorldDirection','update.Direction'))
    g.call('clearpress','self:ClearSurfacePress');branch(g,'surface',get(g,'SurfaceDragging'))
    g.call('updatesurface','self:UpdateSurfaceDrag');g.wire(('releaseRay.WorldLocation','updatesurface.Origin'),('releaseRay.WorldDirection','updatesurface.Direction'),(prop(g,'shift',RIG,'bFast',get(g,'EditorRig')),'updatesurface.Vertical'))
    g.call('end','self:EndSelectionDrag',Commit='true');g.chain('pressed.else','clearpress','active','pc','releasevalid','surface','updatesurface','end');g.chain('surface.else','update','end');g.chain('releasevalid.else','end');g.chain('pc.else','end')
    g.call('blocked','self:EditorPointerBlocked');branch(g,'blockedcheck',combine(g,'ignore',['blocked.Blocked',get(g,'DragActive')],True))
    branch(g,'visual',validity(g,'visualvalid',get(g,'GizmoVisual')));branch(g,'built',prop(g,'ready',VISUAL,'Ready',get(g,'GizmoVisual')))
    branch(g,'player',validity(g,'playervalid',get(g,'EditorController')))
    call(g,'ray',PC+':DeprojectMousePositionToWorld',{'self':get(g,'EditorController')});branch(g,'rayvalid','ray.ReturnValue')
    g.call('begin','self:BeginGizmoDrag');g.wire(('ray.WorldLocation','begin.Origin'),('ray.WorldDirection','begin.Direction'));branch(g,'began','begin.Accepted')
    g.call('select','self:RequestSurfaceSelection')
    g.chain('entry','pressed','blocked','blockedcheck');g.chain('blockedcheck.else','visual','built','player','rayvalid','begin','began')
    for pin in ['visual.else','built.else','began.else']:g.chain(pin,'select')
    return g.function('GizmoPointerButton',inputs=[v('Value','double')])


def mode():
    g=Graph();valid=combine(g,'range',[op(g,'lo','GreaterEqual_IntInt','entry.Mode',B=0),op(g,'hi','LessEqual_IntInt','entry.Mode',B=3)])
    branch(g,'valid',valid);g.call('cancel','self:EndSelectionDrag',Commit='false');set_value(g,'set','GizmoMode','entry.Mode');g.call('style','self:RefreshGizmoModeUI');g.call('tick','self:PollEditorGizmo')
    g.chain('entry','valid','cancel','set','style','tick')
    return g.function('SetGizmoMode',inputs=[v('Mode','int')])


def cycle():
    g=Graph();next_=op(g,'next','Add_IntInt',get(g,'GizmoMode'),B=1);index=op(g,'modulo','Percent_IntInt',next_,B=4)
    g.call('set','self:SetGizmoMode');g.wire((index,'set.Mode'));g.chain('entry','set')
    return g.function('CycleGizmoMode')


def mode_ui():
    g=Graph();branch(g,'valid',validity(g,'toolbarvalid',get(g,'Toolbar')));previous='valid'
    for i,name in enumerate(['SelectMode','Move','Rotate','ScaleMode']):
        g.chain(previous,style_toggle(g,'style'+name,'Toolbar',name,eq(g,name+'selected',get(g,'GizmoMode'),i)));previous='style'+name
    g.chain('entry','valid')
    return g.function('RefreshGizmoModeUI')


def poll():
    g=Graph();g.call('material','self:PollGizmoMaterial');branch(g,'visual',validity(g,'visualvalid',get(g,'GizmoVisual')))
    g.call('frame','self:GetGizmoFrame');branch(g,'framevalid','frame.Valid');branch(g,'mode',op(g,'enabled','Greater_IntInt',get(g,'GizmoMode'),B=0))
    branch(g,'pc',validity(g,'pcvalid',get(g,'EditorController')));call(g,'ray',PC+':DeprojectMousePositionToWorld',{'self':get(g,'EditorController')});branch(g,'rayvalid','ray.ReturnValue')
    branch(g,'drag',get(g,'DragActive'));g.call('update','self:UpdateGizmoDrag');g.wire(('ray.WorldLocation','update.Origin'),('ray.WorldDirection','update.Direction'))
    set_value(g,'draghover','GizmoHoverKind',get(g,'GizmoDragKind'));set_value(g,'dragaxis','GizmoHoverAxis',get(g,'GizmoDragAxis'))
    g.call('blocked','self:EditorPointerBlocked');branch(g,'block','blocked.Blocked')
    math(g,'pick','PickHandle',{'Origin':'ray.WorldLocation','Direction':'ray.WorldDirection','Center':'frame.Center','Size':'frame.Size','Mode':get(g,'GizmoMode'),'Rotation':'frame.Rotation'})
    set_value(g,'hover','GizmoHoverKind','pick.Kind');set_value(g,'axis','GizmoHoverAxis','pick.Axis')
    g.set('nohover','GizmoHoverKind','0');g.set('noaxis','GizmoHoverAxis','0')
    # Query the pose again after the preview, so the visual tracks this frame.
    g.call('newframe','self:GetGizmoFrame');method(g,'show',VISUAL,'ShowPose',get(g,'GizmoVisual'),{'Center':'newframe.Center','Rotation':'newframe.Rotation','Size':'newframe.Size','Mode':get(g,'GizmoMode'),'HoverKind':get(g,'GizmoHoverKind'),'HoverAxis':get(g,'GizmoHoverAxis')})
    method(g,'hide',VISUAL,'HideVisual',get(g,'GizmoVisual'))
    branch(g,'surface',get(g,'SurfaceDragging'));g.chain('surface','hide')
    g.chain('entry','material','visual','surface');g.chain('surface.else','frame','framevalid','mode','pc','rayvalid','drag','update','draghover','dragaxis','newframe','show')
    g.chain('drag.else','blocked','block','nohover','noaxis','newframe');g.chain('block.else','pick','hover','axis','newframe')
    for pin in ['pc.else','rayvalid.else']:g.chain(pin,'nohover')
    for pin in ['framevalid.else','mode.else']:g.chain(pin,'hide')
    return g.function('PollEditorGizmo')


def variables():
    return [v('GizmoMath','object:'+MATH),v('GizmoVisual','object:'+VISUAL),v('GizmoJob','object:'+JOB),v('GizmoRequestAt','double'),v('GizmoMode','int','1'),
            *[v('Gizmo'+name,'int') for name in ['HoverKind','HoverAxis','DragKind','DragAxis']],v('GizmoDragSize','double'),
            *[v('GizmoDrag'+name,'vector') for name in ['Origin','Direction','Center','Vector','Diagonal']]]


def functions():return [initialize(),destroy(),poll_material(),blocked(),frame(),begin_drag(),update_drag(),click(),mode(),cycle(),mode_ui(),poll()]
