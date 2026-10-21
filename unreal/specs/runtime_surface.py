"""Native surface/height dragging and asynchronous click-to-drag arming."""
from graph import Graph, variable as v, KML, KSL, GS
from runtime import unpack
from runtime_store import call, branch, combine
from runtime_world import PRIMITIVE, SMC, validity, set_value, finish_bool
from runtime_apply import get
from runtime_session import prop
from runtime_pick import FACT
from runtime_editor_assets import RIG
from runtime_editor_host import PC
from runtime_gizmo_controller import op, eq, neg, math

RAY=[v('Origin','vector'),v('Direction','vector')]
DRAY=RAY+[v('Vertical','bool')]


def clear_press():
    g=Graph();previous='entry'
    for field in ['SurfaceButtonDown','SurfacePressPending','SurfaceArmed','SurfaceArmedComponent']:
        g.set('clear'+field,field);g.chain(previous,'clear'+field);previous='clear'+field
    return g.function('ClearSurfacePress')


def prepare_press():
    g=Graph();g.call('clear','self:ClearSurfacePress')
    direction=op(g,'normal','Normal','entry.Direction',Tolerance=1e-12)
    branch(g,'valid',op(g,'nonzero','Greater_DoubleDouble',op(g,'size','VSize',direction),B=.5))
    set_value(g,'ray','SurfacePressDirection',direction);g.set('down','SurfaceButtonDown','true');g.set('pending','SurfacePressPending','true')
    g.chain('entry','clear','valid','ray','down','pending')
    return g.function('PrepareSurfacePress',inputs=RAY)


def request():
    g=Graph();branch(g,'pc',validity(g,'pcvalid',get(g,'EditorController')))
    call(g,'ray',PC+':DeprojectMousePositionToWorld',{'self':get(g,'EditorController')});branch(g,'valid','ray.ReturnValue')
    g.call('press','self:PrepareSurfacePress');g.wire(('ray.WorldLocation','press.Origin'),('ray.WorldDirection','press.Direction'))
    g.call('pick','self:RequestSelection',Value=1);g.chain('entry','pc','valid','press','pick')
    return g.function('RequestSurfaceSelection')


def consume():
    g=Graph();set_value(g,'pending','local:HeldPress',combine(g,'held',[get(g,'SurfacePressPending'),get(g,'SurfaceButtonDown')]))
    set_value(g,'direction','local:PressRay',get(g,'SurfacePressDirection'))
    g.call('accept','self:AcceptSelection');g.wire(('entry.Facts','accept.Facts'))
    g.get('heldlocal','local:HeldPress');branch(g,'arm',combine(g,'armcheck',['heldlocal.HeldPress',get(g,'HasSelection')]))
    unpack(g,'facts',FACT,get(g,'Selected'));g.get('ray','local:PressRay')
    set_value(g,'rayrestore','SurfacePressDirection','ray.PressRay');set_value(g,'component','SurfaceArmedComponent','facts.Component');set_value(g,'generation','SurfaceArmedGeneration',get(g,'Generation'))
    g.set('down','SurfaceButtonDown','true');g.set('armed','SurfaceArmed','true')
    branch(g,'collect',get(g,'CompositionSelecting'));g.call('collectpart','self:ToggleCompositionPart');g.wire(('entry.Facts','collectpart.Facts'));g.call('clearpress','self:ClearSurfacePress');g.chain('entry','collect','collectpart','clearpress');g.chain('collect.else','pending','direction','accept','arm','rayrestore','component','generation','down','armed')
    return g.function('ConsumePointerSelection',inputs=[v('Facts','struct:'+FACT)],locals=[v('HeldPress','bool','false'),v('PressRay','vector')])


def trace():
    g=Graph();g.node('self','self');direction=op(g,'normal','Normal','entry.Direction',Tolerance=1e-12)
    end=op(g,'end','Add_VectorVector','entry.Origin',op(g,'reach','Multiply_VectorFloat',direction,get(g,'ReachCm')))
    call(g,'trace',KSL+':LineTraceSingle',{'WorldContextObject':'self.self','Start':'entry.Origin','End':end},TraceChannel='TraceTypeQuery1',bTraceComplex='true',DrawDebugType='None',bIgnoreSelf='true')
    call(g,'hit',GS+':BreakHitResult',{'Hit':'trace.OutHit'});call(g,'normalparts',KML+':BreakVector',{'InVec':'hit.ImpactNormal'})
    usable=combine(g,'surface',['trace.ReturnValue',op(g,'upright','GreaterEqual_DoubleDouble','normalparts.Z',B=.7)])
    g.wire((usable,'result.Valid'),('hit.ImpactPoint','result.Point'));g.chain('entry','trace','result')
    return g.function('TraceDragSurface',inputs=RAY,outputs=[v('Valid','bool'),v('Point','vector')])


def plane(g,name,center,axis=None):
    math(g,name,'PlanePoint',{'Origin':'entry.Origin','Direction':'entry.Direction','Center':center,**({'Axis':axis} if axis else {})},**({} if axis else {'Axis':'0,0,1'}))
    branch(g,name+'valid',name+'.Valid')


def rebase():
    g=Graph();g.set('invalid','SurfaceGrabValid','false');set_value(g,'base','SurfaceBase',get(g,'DragFinalPosition'));set_value(g,'vertical','SurfaceVertical','entry.Vertical')
    branch(g,'lift','entry.Vertical')
    call(g,'direction',KML+':BreakVector',{'InVec':'entry.Direction'})
    normal=call(g,'horizontal',KML+':MakeVector',{'X':op(g,'negativeX','Multiply_DoubleDouble','direction.X',B=-1),'Y':op(g,'negativeY','Multiply_DoubleDouble','direction.Y',B=-1)},Z=0)
    length=op(g,'length','VSize',normal);use=op(g,'longenough','GreaterEqual_DoubleDouble',length,B=.001)
    normal=call(g,'choose',KML+':SelectVector',{'A':op(g,'unit','Normal',normal,Tolerance=1e-12),'bPickA':use},B='1,0,0')
    set_value(g,'savenormal','SurfaceNormal',normal);plane(g,'verticalhit',get(g,'SurfaceBase'),get(g,'SurfaceNormal'))
    g.call('trace','self:TraceDragSurface');g.wire(('entry.Origin','trace.Origin'),('entry.Direction','trace.Direction'));branch(g,'ground','trace.Valid')
    plane(g,'fallback',get(g,'SurfaceBase'))
    previous=[]
    for name,point in [('lift','verticalhit.Point'),('ground','trace.Point'),('fallback','fallback.Point')]:
        set_value(g,name+'grab','SurfaceGrab',point);previous.append(name+'grab')
    call(g,'grabparts',KML+':BreakVector',{'InVec':get(g,'SurfaceGrab')});set_value(g,'height','SurfacePlaneZ','grabparts.Z')
    offset=op(g,'offset','Subtract_VectorVector',get(g,'SurfaceBase'),get(g,'SurfaceGrab'));set_value(g,'saveoffset','SurfaceOffset',offset);g.set('valid','SurfaceGrabValid','true')
    g.chain('entry','invalid','base','vertical','lift','savenormal','verticalhit','verticalhitvalid','liftgrab','height','saveoffset','valid')
    g.chain('lift.else','trace','ground','groundgrab','height');g.chain('ground.else','fallback','fallbackvalid','fallbackgrab','height')
    return g.function('RebaseSurfaceDrag',inputs=DRAY)


def begin():
    g=Graph();branch(g,'math',validity(g,'mathvalid',get(g,'GizmoMath')));g.call('begin','self:BeginSelectionDrag',Mode=1);branch(g,'accepted','begin.Accepted')
    set_value(g,'component','SurfaceComponent',get(g,'DragComponent'))
    response=call(g,'response',PRIMITIVE+':GetCollisionResponseToChannel',{'self':get(g,'SurfaceComponent')},Channel='ECC_Visibility')
    set_value(g,'capture','SurfaceResponse',response);g.set('flag','SurfaceDragging','true')
    call(g,'ignore',PRIMITIVE+':SetCollisionResponseToChannel',{'self':get(g,'SurfaceComponent')},Channel='ECC_Visibility',NewResponse='ECR_Ignore')
    g.call('rebase','self:RebaseSurfaceDrag')
    for p in ['Origin','Direction','Vertical']:g.wire(('entry.'+p,'rebase.'+p))
    g.set('armed','SurfaceArmed','false');g.set('pending','SurfacePressPending','false');g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','math','begin','accepted','component','capture','flag','ignore','rebase','armed','pending','yes','result')
    g.chain('math.else','result');g.chain('accepted.else','result')
    return g.function('BeginSurfaceDrag',inputs=DRAY,outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def finish():
    g=Graph();g.call('press','self:ClearSurfacePress');branch(g,'changed',get(g,'SurfaceDragging'))
    branch(g,'valid',validity(g,'componentvalid',get(g,'SurfaceComponent')))
    call(g,'restore',PRIMITIVE+':SetCollisionResponseToChannel',{'self':get(g,'SurfaceComponent'),'NewResponse':get(g,'SurfaceResponse')},Channel='ECC_Visibility')
    g.set('clear','SurfaceComponent');g.set('stop','SurfaceDragging','false');g.set('grab','SurfaceGrabValid','false')
    g.chain('entry','press','changed','valid','restore','clear','stop','grab');g.chain('valid.else','clear');g.chain('changed.else','clear')
    return g.function('FinishSurfaceDrag')


def update():
    g=Graph();g.call('ready','self:CanContinueSelectionDrag');branch(g,'allowed',combine(g,'allowedcheck',['ready.Ready',get(g,'SurfaceDragging'),validity(g,'mathvalid',get(g,'GizmoMath'))]))
    different=call(g,'different',KML+':NotEqual_BoolBool',{'A':'entry.Vertical','B':get(g,'SurfaceVertical')})
    branch(g,'rebase',combine(g,'needsrebase',[different,neg(g,'nograb',get(g,'SurfaceGrabValid'))],True));g.call('refresh','self:RebaseSurfaceDrag')
    for p in ['Origin','Direction','Vertical']:g.wire(('entry.'+p,'refresh.'+p))
    branch(g,'grab',get(g,'SurfaceGrabValid'));branch(g,'vertical',get(g,'SurfaceVertical'))
    plane(g,'height',get(g,'SurfaceGrab'),get(g,'SurfaceNormal'))
    for name,source in [('base',get(g,'SurfaceBase')),('grabpoint',get(g,'SurfaceGrab')),('heightpoint','height.Point')]:call(g,name,KML+':BreakVector',{'InVec':source})
    z=op(g,'newz','Add_DoubleDouble','base.Z',op(g,'dz','Subtract_DoubleDouble','heightpoint.Z','grabpoint.Z'))
    position=call(g,'lifted',KML+':MakeVector',{'X':'base.X','Y':'base.Y','Z':z})
    g.call('previewheight','self:PreviewSelectionDrag');g.wire((position,'previewheight.Position'))
    g.call('trace','self:TraceDragSurface');g.wire(('entry.Origin','trace.Origin'),('entry.Direction','trace.Direction'));branch(g,'ground','trace.Valid')
    call(g,'groundpoint',KML+':BreakVector',{'InVec':'trace.Point'});set_value(g,'planeheight','SurfacePlaneZ','groundpoint.Z');set_value(g,'anchorhit','local:Anchor','trace.Point')
    planez=call(g,'planez',KML+':MakeVector',{'Z':get(g,'SurfacePlaneZ')},X=0,Y=0);plane(g,'fallback',planez);set_value(g,'anchorplane','local:Anchor','fallback.Point')
    g.get('anchor','local:Anchor');target=op(g,'target','Add_VectorVector','anchor.Anchor',get(g,'SurfaceOffset'));call(g,'parts',KML+':BreakVector',{'InVec':target})
    for axis in ['X','Y']:math(g,'snap'+axis,'SnapValue',{'Value':'parts.'+axis,'Step':get(g,'GridStep')})
    snapped=call(g,'snapped',KML+':MakeVector',{'X':'snapX.Snapped','Y':'snapY.Snapped','Z':'parts.Z'})
    g.call('previewground','self:PreviewSelectionDrag');g.wire((snapped,'previewground.Position'))
    g.chain('entry','ready','allowed','rebase','refresh','grab','vertical','height','heightvalid','previewheight');g.chain('rebase.else','grab')
    g.chain('vertical.else','trace','ground','planeheight','anchorhit','snapX','snapY','previewground');g.chain('ground.else','fallback','fallbackvalid','anchorplane','snapX')
    return g.function('UpdateSurfaceDrag',inputs=DRAY,locals=[v('Anchor','vector')])


def consider():
    g=Graph();branch(g,'armed',get(g,'SurfaceArmed'));g.call('ready','self:CanEdit');g.call('blocked','self:EditorPointerBlocked')
    unpack(g,'facts',FACT,get(g,'Selected'))
    same=call(g,'same',KML+':EqualEqual_ObjectObject',{'A':'facts.Component','B':get(g,'SurfaceArmedComponent')})
    generation=call(g,'generation',KML+':EqualEqual_IntInt',{'A':get(g,'Generation'),'B':get(g,'SurfaceArmedGeneration')})
    branch(g,'allowed',combine(g,'available',['ready.Ready',get(g,'UIOpen'),get(g,'HasSelection'),get(g,'SurfaceButtonDown'),same,generation,neg(g,'idle',get(g,'DragActive')),neg(g,'unblocked','blocked.Blocked')]))
    direction=op(g,'unit','Normal','entry.Direction',Tolerance=1e-12)
    angle=op(g,'dot','Dot_VectorVector',direction,get(g,'SurfacePressDirection'))
    branch(g,'moved',combine(g,'changed',[op(g,'size','Greater_DoubleDouble',op(g,'length','VSize',direction),B=.5),op(g,'threshold','Less_DoubleDouble',angle,B=.9999875000260416)]))
    g.call('begin','self:BeginSurfaceDrag')
    for p in ['Origin','Direction','Vertical']:g.wire(('entry.'+p,'begin.'+p))
    g.call('clear','self:ClearSurfacePress');g.chain('entry','armed','ready','blocked','allowed','moved','begin');g.chain('allowed.else','clear')
    return g.function('ConsiderSurfaceDrag',inputs=DRAY)


def poll():
    g=Graph();branch(g,'pc',combine(g,'references',[get(g,'UIOpen'),validity(g,'pcvalid',get(g,'EditorController')),validity(g,'rigvalid',get(g,'EditorRig'))]))
    needed=combine(g,'needsupdate',[get(g,'SurfaceDragging'),get(g,'SurfaceArmed')],True);branch(g,'needed',needed)
    call(g,'ray',PC+':DeprojectMousePositionToWorld',{'self':get(g,'EditorController')});branch(g,'valid','ray.ReturnValue')
    branch(g,'drag',get(g,'SurfaceDragging'))
    for name,fn in [('update','UpdateSurfaceDrag'),('consider','ConsiderSurfaceDrag')]:
        g.call(name,'self:'+fn);g.wire(('ray.WorldLocation',name+'.Origin'),('ray.WorldDirection',name+'.Direction'),(prop(g,name+'shift',RIG,'bFast',get(g,'EditorRig')),name+'.Vertical'))
    g.chain('entry','pc','needed','valid','drag','update');g.chain('drag.else','consider')
    return g.function('PollSurfaceDrag')


def variables():
    return [v(n,'bool') for n in ['SurfaceButtonDown','SurfacePressPending','SurfaceArmed','SurfaceDragging','SurfaceVertical','SurfaceGrabValid']]+[
        v('SurfaceArmedComponent','object:'+SMC),v('SurfaceArmedGeneration','int'),v('SurfaceComponent','object:'+SMC),v('SurfaceResponse','byte'),v('SurfacePlaneZ','double'),
        *[v('Surface'+n,'vector') for n in ['PressDirection','Base','Grab','Normal','Offset']]]


def functions():return [clear_press(),prepare_press(),request(),consume(),trace(),rebase(),begin(),finish(),update(),consider(),poll()]
