"""Blueprint gizmo geometry and drag math; no loads, world mutation or Lua.

Modes: 0 off, 1 move, 2 rotate, 3 scale.
Handles: 0 none, 1 axis, 2 plane, 3 ring, 4 uniform. Axis: 1 X, 2 Y,
3 Z (a plane's excluded/normal axis); uniform uses axis 0.
Invalid intersections return Valid=false rather than infinity/NaN.
"""
from graph import Graph, variable as v, KML
from runtime import ROOT
from runtime_store import call, branch, combine
from runtime_world import set_value, finish_bool, vector_valid

MATH=ROOT+'BP_DenGizmoMath'
AXES=['X','Y','Z']
UNIT=['1,0,0','0,1,0','0,0,1']
RAY=[v('Origin','vector'),v('Direction','vector'),v('Center','vector'),v('Axis','vector')]


def op(g,name,fn,a=None,b=None,**defaults):
    return call(g,name,KML+':'+fn,{**({'A':a} if a else {}),**({'B':b} if b else {})},**defaults)


def output(g,field,source):
    g.wire((source,'result.'+field))


def local_out(g,name,kind):
    g.get('out'+name,'local:Result'+name);output(g,name,'out'+name+'.Result'+name)
    return v('Result'+name,kind)


def axis_param():
    g=Graph()
    d=op(g,'d','Normal','entry.Direction',Tolerance=1e-12);a=op(g,'a','Normal','entry.Axis',Tolerance=1e-12)
    b=op(g,'dot','Dot_VectorVector',a,d)
    den=op(g,'den','Subtract_DoubleDouble',b=op(g,'square','Multiply_DoubleDouble',b,b),A=1)
    checks=[op(g,'nonparallel','GreaterEqual_DoubleDouble',den,B=1e-6)]
    for name,source in [('ray',d),('axis',a)]:
        checks.append(op(g,name+'length','Greater_DoubleDouble',op(g,name+'size','VSize',source),B=.5))
    branch(g,'valid',combine(g,'usable',checks))
    w=op(g,'w','Subtract_VectorVector','entry.Center','entry.Origin')
    dw=op(g,'dw','Dot_VectorVector',d,w);aw=op(g,'aw','Dot_VectorVector',a,w)
    numerator=op(g,'num','Subtract_DoubleDouble',op(g,'bdw','Multiply_DoubleDouble',b,dw),aw)
    set_value(g,'value','local:ResultDistance',op(g,'divide','Divide_DoubleDouble',numerator,den))
    g.set('yes','local:OK','true');finish_bool(g,'Valid')
    loc=local_out(g,'Distance','double')
    g.chain('entry','valid','value','yes','result');g.chain('valid.else','result')
    return g.function('AxisParam',inputs=RAY,outputs=[v('Valid','bool'),v('Distance','double')],locals=[v('OK','bool','false'),loc])


def plane_point():
    g=Graph();d=op(g,'d','Normal','entry.Direction',Tolerance=1e-12)
    a=op(g,'a','Normal','entry.Axis',Tolerance=1e-12)
    den=op(g,'den','Dot_VectorVector',d,a)
    branch(g,'valid',op(g,'nonparallel','GreaterEqual_DoubleDouble',op(g,'abs','Abs',den),B=1e-6))
    w=op(g,'w','Subtract_VectorVector','entry.Center','entry.Origin')
    t=op(g,'t','Divide_DoubleDouble',op(g,'dot','Dot_VectorVector',w,a),den)
    branch(g,'forward',op(g,'positive','GreaterEqual_DoubleDouble',t,B=0))
    point=op(g,'point','Add_VectorVector','entry.Origin',op(g,'along','Multiply_VectorFloat',d,t))
    set_value(g,'value','local:ResultPoint',point);g.set('yes','local:OK','true');finish_bool(g,'Valid')
    loc=local_out(g,'Point','vector')
    g.chain('entry','valid','forward','value','yes','result')
    for pin in ['valid.else','forward.else']:g.chain(pin,'result')
    return g.function('PlanePoint',inputs=RAY,outputs=[v('Valid','bool'),v('Point','vector')],locals=[v('OK','bool','false'),loc])


def angle():
    g=Graph();n=op(g,'normal','Normal','entry.Axis',Tolerance=1e-12)
    call(g,'parts',KML+':BreakVector',{'InVec':n})
    vertical=op(g,'vertical','Less_DoubleDouble',op(g,'abs','Abs','parts.Z'),B=.9)
    helper=call(g,'helper',KML+':SelectVector',{'bPickA':vertical},A='0,0,1',B='1,0,0')
    u=op(g,'u','Normal',op(g,'cross','Cross_VectorVector',helper,n),Tolerance=1e-12)
    w=op(g,'w','Cross_VectorVector',n,u);r=op(g,'r','Subtract_VectorVector','entry.Point','entry.Center')
    result=call(g,'angle',KML+':DegAtan2',{'Y':op(g,'y','Dot_VectorVector',r,w),'X':op(g,'x','Dot_VectorVector',r,u)})
    output(g,'Degrees',result);g.chain('entry','result')
    return g.function('Angle',inputs=[v('Point','vector'),v('Center','vector'),v('Axis','vector')],outputs=[v('Degrees','double')])


def ray_call(g,name,fn):
    g.call(name,'self:'+fn)
    for field in ['Origin','Direction','Center','Axis']:g.wire(('entry.'+field,name+'.'+field))


def segment_distance():
    g=Graph();branch(g,'length',op(g,'positive','Greater_DoubleDouble','entry.Length',B=0))
    ray_call(g,'axis','AxisParam');branch(g,'valid','axis.Valid')
    clamped=call(g,'clamp',KML+':FClamp',{'Value':'axis.Distance','Max':'entry.Length'},Min=0)
    a=op(g,'a','Normal','entry.Axis',Tolerance=1e-12);d=op(g,'d','Normal','entry.Direction',Tolerance=1e-12)
    q=op(g,'q','Add_VectorVector','entry.Center',op(g,'qa','Multiply_VectorFloat',a,clamped))
    t=op(g,'t','FMax',op(g,'dot','Dot_VectorVector',op(g,'w','Subtract_VectorVector',q,'entry.Origin'),d),B=0)
    nearest=op(g,'nearest','Add_VectorVector','entry.Origin',op(g,'td','Multiply_VectorFloat',d,t))
    distance=op(g,'dist','VSize',op(g,'offset','Subtract_VectorVector',q,nearest))
    set_value(g,'distance','local:ResultDistance',distance);set_value(g,'along','local:ResultAlong',clamped)
    g.set('yes','local:OK','true');finish_bool(g,'Valid')
    locs=[local_out(g,'Distance','double'),local_out(g,'Along','double')]
    g.chain('entry','length','axis','valid','distance','along','yes','result')
    for pin in ['length.else','valid.else']:g.chain(pin,'result')
    return g.function('SegmentDistance',inputs=RAY+[v('Length','double')],outputs=[v('Valid','bool'),v('Distance','double'),v('Along','double')],locals=[v('OK','bool','false'),*locs])


def ring_distance():
    g=Graph();branch(g,'radius',op(g,'positive','Greater_DoubleDouble','entry.Radius',B=0))
    ray_call(g,'plane','PlanePoint');branch(g,'valid','plane.Valid')
    radial=op(g,'radial','VSize',op(g,'offset','Subtract_VectorVector','plane.Point','entry.Center'))
    distance=op(g,'dist','Abs',op(g,'diff','Subtract_DoubleDouble',radial,'entry.Radius'))
    set_value(g,'distance','local:ResultDistance',distance)
    g.call('angle','self:Angle');g.wire(('plane.Point','angle.Point'),('entry.Center','angle.Center'),('entry.Axis','angle.Axis'))
    set_value(g,'degrees','local:ResultDegrees','angle.Degrees');g.set('yes','local:OK','true');finish_bool(g,'Valid')
    locs=[local_out(g,'Distance','double'),local_out(g,'Degrees','double')]
    g.chain('entry','radius','plane','valid','distance','angle','degrees','yes','result')
    for pin in ['radius.else','valid.else']:g.chain(pin,'result')
    return g.function('RingDistance',inputs=RAY+[v('Radius','double')],outputs=[v('Valid','bool'),v('Distance','double'),v('Degrees','double')],locals=[v('OK','bool','false'),*locs])


def frame_axes():
    g=Graph();scale=op(g,'scale','EqualEqual_IntInt','entry.Mode',B=3)
    for axis,unit,fn in zip(AXES,UNIT,['GetForwardVector','GetRightVector','GetUpVector']):
        local=call(g,'local'+axis,KML+':'+fn,{'InRot':'entry.Rotation'})
        world=call(g,'axis'+axis,KML+':SelectVector',{'A':local,'bPickA':scale},B=unit)
        output(g,axis,world)
    g.chain('entry','result')
    return g.function('FrameAxes',inputs=[v('Mode','int'),v('Rotation','rotator')],outputs=[v(a,'vector') for a in AXES])


def pick_handle():
    g=Graph();g.get('best','local:BestDistance')
    d=op(g,'ray','Normal','entry.Direction',Tolerance=1e-12)
    checks=[op(g,'positive','Greater_DoubleDouble','entry.Size',B=0),
            op(g,'bounded','LessEqual_DoubleDouble','entry.Size',B=1e7),
            op(g,'nonzero','Greater_DoubleDouble',op(g,'raylen','VSize',d),B=.5),
            op(g,'modeMin','GreaterEqual_IntInt','entry.Mode',B=1),op(g,'modeMax','LessEqual_IntInt','entry.Mode',B=3),
            vector_valid(g,'origin','entry.Origin'),vector_valid(g,'center','entry.Center')]
    branch(g,'valid',combine(g,'checks',checks))
    g.call('axes','self:FrameAxes');g.wire(('entry.Mode','axes.Mode'),('entry.Rotation','axes.Rotation'))
    branch(g,'rotate',op(g,'isrotate','EqualEqual_IntInt','entry.Mode',B=2))
    grab=op(g,'grab','Multiply_DoubleDouble','entry.Size',B=.09)
    radius=op(g,'radius','Multiply_DoubleDouble','entry.Size',B=.8)
    def remember(name,kind,axis,distance=None):
        g.set(name+'kind','local:ResultKind',str(kind));g.set(name+'axis','local:ResultAxis',str(axis))
        if distance:set_value(g,name+'distance','local:BestDistance',distance)
        else:g.set(name+'distance','local:BestDistance','0')
        g.chain(name+'kind',name+'axis',name+'distance')
        return name+'kind',name+'distance'
    def consider(previous,name,index,ring):
        fn='RingDistance' if ring else 'SegmentDistance';g.call(name,'self:'+fn)
        for field,source in [('Origin','entry.Origin'),('Direction',d),('Center','entry.Center'),('Axis','axes.'+AXES[index]),('Radius' if ring else 'Length',radius if ring else 'entry.Size')]:
            g.wire((source,name+'.'+field))
        branch(g,name+'valid',name+'.Valid')
        reach=op(g,name+'reach','LessEqual_DoubleDouble',name+'.Distance',grab)
        closer=op(g,name+'closer','Less_DoubleDouble',name+'.Distance','best.BestDistance')
        branch(g,name+'choose',combine(g,name+'both',[reach,closer]))
        first,last=remember(name,3 if ring else 1,index+1,name+'.Distance')
        g.node(name+'next','sequence',outputs=1)
        g.chain(previous,name,name+'valid',name+'choose',first);g.chain(last,name+'next')
        for pin in [name+'valid.else',name+'choose.else']:g.chain(pin,name+'next')
        return name+'next.then_0'
    previous='rotate'
    for i in range(3):previous=consider(previous,'ring'+str(i),i,True)
    g.chain(previous,'result')
    previous='rotate.else'
    for i in range(3):previous=consider(previous,'shaft'+str(i),i,False)
    for i in range(3):
        name='plane'+str(i);g.call(name,'self:PlanePoint')
        for field,source in [('Origin','entry.Origin'),('Direction',d),('Center','entry.Center'),('Axis','axes.'+AXES[i])]:g.wire((source,name+'.'+field))
        branch(g,name+'valid',name+'.Valid');offset=op(g,name+'offset','Subtract_VectorVector',name+'.Point','entry.Center')
        checks=[]
        for j in [(i+1)%3,(i+2)%3]:
            n=name+AXES[j];along=op(g,n+'unit','Divide_DoubleDouble',op(g,n+'dot','Dot_VectorVector',offset,'axes.'+AXES[j]),'entry.Size')
            checks += [op(g,n+'min','GreaterEqual_DoubleDouble',along,B=.25),op(g,n+'max','LessEqual_DoubleDouble',along,B=.45)]
        branch(g,name+'inside',combine(g,name+'square',checks))
        first,last=remember(name,2,i+1);g.node(name+'next','sequence',outputs=1)
        g.chain(previous,name,name+'valid',name+'inside',first);g.chain(last,name+'next')
        for pin in [name+'valid.else',name+'inside.else']:g.chain(pin,name+'next')
        previous=name+'next.then_0'
    branch(g,'scale',op(g,'isscale','EqualEqual_IntInt','entry.Mode',B=3))
    diag=op(g,'diagonal','Normal',op(g,'sum3','Add_VectorVector',op(g,'sum2','Add_VectorVector','axes.X','axes.Y'),'axes.Z'),Tolerance=1e-12)
    point=op(g,'uniformpoint','Add_VectorVector','entry.Center',op(g,'diagpoint','Multiply_VectorFloat',diag,'entry.Size'))
    t=op(g,'uniformt','FMax',op(g,'uniformdot','Dot_VectorVector',op(g,'uniformoffset','Subtract_VectorVector',point,'entry.Origin'),d),B=0)
    nearest=op(g,'uniformnearest','Add_VectorVector','entry.Origin',op(g,'uniformalong','Multiply_VectorFloat',d,t))
    distance=op(g,'uniformdist','VSize',op(g,'uniformdiff','Subtract_VectorVector',point,nearest))
    branch(g,'uniformhit',op(g,'uniformreach','LessEqual_DoubleDouble',distance,op(g,'cubegrab','Multiply_DoubleDouble','entry.Size',B=.12)))
    first,last=remember('uniform',4,0)
    g.chain(previous,'scale','uniformhit',first);g.chain(last,'result')
    for pin in ['valid.else','scale.else','uniformhit.else']:g.chain(pin,'result')
    locs=[local_out(g,'Kind','int'),local_out(g,'Axis','int')]
    g.chain('entry','valid','axes','rotate')
    return g.function('PickHandle',inputs=[v('Origin','vector'),v('Direction','vector'),v('Center','vector'),v('Size','double'),v('Mode','int'),v('Rotation','rotator')],
                      outputs=[v('Kind','int'),v('Axis','int')],locals=[*locs,v('BestDistance','double','1e30')])


def size_for():
    g=Graph();size=op(g,'size','FMax',op(g,'distance','Multiply_DoubleDouble','entry.Distance',B=.16),B=1)
    output(g,'Size',size);g.chain('entry','result')
    return g.function('SizeFor',inputs=[v('Distance','double')],outputs=[v('Size','double')])


def snap():
    g=Graph();set_value(g,'original','local:ResultSnapped','entry.Value')
    branch(g,'enabled',op(g,'positive','Greater_DoubleDouble','entry.Step',B=0))
    divided=op(g,'div','Divide_DoubleDouble','entry.Value','entry.Step')
    rounded=op(g,'floor','FFloor',op(g,'half','Add_DoubleDouble',divided,B=.5))
    set_value(g,'rounded','local:ResultSnapped',op(g,'snap','Multiply_DoubleDouble',rounded,'entry.Step'))
    loc=local_out(g,'Snapped','double')
    g.chain('entry','original','enabled','rounded','result');g.chain('enabled.else','result')
    return g.function('SnapValue',inputs=[v('Value','double'),v('Step','double')],outputs=[v('Snapped','double')],locals=[loc])


def wrap():
    g=Graph();turns=op(g,'floor','FFloor',op(g,'div','Divide_DoubleDouble',op(g,'plus','Add_DoubleDouble','entry.Degrees',B=180),B=360))
    result=op(g,'wrap','Subtract_DoubleDouble','entry.Degrees',op(g,'turns','Multiply_DoubleDouble',turns,B=360))
    output(g,'Wrapped',result);g.chain('entry','result')
    return g.function('WrapAngle',inputs=[v('Degrees','double')],outputs=[v('Wrapped','double')])


def delta(kind):
    g=Graph();fn='AxisParam' if kind=='Axis' else 'PlanePoint'
    for name,prefix in [('start','Start'),('current','Current')]:
        g.call(name,'self:'+fn)
        for field,source in [('Origin','entry.'+prefix+'Origin'),('Direction','entry.'+prefix+'Direction'),('Center','entry.Center'),('Axis','entry.Axis')]:g.wire((source,name+'.'+field))
        branch(g,name+'valid',name+'.Valid')
    if kind=='Axis':value=op(g,'difference','Subtract_DoubleDouble','current.Distance','start.Distance');out='Distance';typ='double';previous='currentvalid'
    elif kind=='Plane':value=op(g,'difference','Subtract_VectorVector','current.Point','start.Point');out='Offset';typ='vector';previous='currentvalid'
    else:
        for name in ['start','current']:
            g.call(name+'angle','self:Angle');g.wire((name+'.Point',name+'angle.Point'),('entry.Center',name+'angle.Center'),('entry.Axis',name+'angle.Axis'))
        diff=op(g,'difference','Subtract_DoubleDouble','currentangle.Degrees','startangle.Degrees')
        g.call('wrap','self:WrapAngle');g.wire((diff,'wrap.Degrees'))
        g.call('snap','self:SnapValue');g.wire(('wrap.Wrapped','snap.Value'),('entry.Step','snap.Step'))
        g.chain('currentvalid','startangle','currentangle','wrap','snap')
        previous='snap';value='snap.Snapped';out='Degrees';typ='double'
    set_value(g,'value','local:Result'+out,value);g.set('yes','local:OK','true');finish_bool(g,'Valid');loc=local_out(g,out,typ)
    g.chain('entry','start','startvalid','current','currentvalid');g.chain(previous,'value','yes','result')
    for pin in ['startvalid.else','currentvalid.else']:g.chain(pin,'result')
    params=[v('StartOrigin','vector'),v('StartDirection','vector'),v('CurrentOrigin','vector'),v('CurrentDirection','vector'),v('Center','vector'),v('Axis','vector')]
    return g.function(kind+'Delta',inputs=params+([v('Step','double')] if kind=='Ring' else []),outputs=[v('Valid','bool'),v(out,typ)],locals=[v('OK','bool','false'),loc])


def scaled():
    g=Graph();checks=[op(g,'size','Greater_DoubleDouble','entry.Size',B=0),vector_valid(g,'scale','entry.Scale',True)]
    uniform=op(g,'uniform','EqualEqual_IntInt','entry.Kind',B=4)
    axis=op(g,'axis','EqualEqual_IntInt','entry.Kind',B=1);plane=op(g,'plane','EqualEqual_IntInt','entry.Kind',B=2)
    axisrange=combine(g,'axisrange',[op(g,'lo','GreaterEqual_IntInt','entry.Axis',B=1),op(g,'hi','LessEqual_IntInt','entry.Axis',B=3)])
    checks.append(combine(g,'handle',[uniform,combine(g,'directional',[axisrange,combine(g,'axisorplane',[axis,plane],True)])],True))
    branch(g,'valid',combine(g,'checks',checks))
    factor=op(g,'factor','FMax',op(g,'ratio','Add_DoubleDouble',op(g,'divide','Divide_DoubleDouble','entry.Along','entry.Size'),B=1),B=.05)
    call(g,'parts',KML+':BreakVector',{'InVec':'entry.Scale'});parts={}
    for i,name in enumerate(AXES,1):
        same=op(g,'same'+name,'EqualEqual_IntInt','entry.Axis',B=i);different=op(g,'different'+name,'NotEqual_IntInt','entry.Axis',B=i)
        changed=combine(g,'change'+name,[uniform,combine(g,'axis'+name,[axis,same]),combine(g,'plane'+name,[plane,different])],True)
        product=op(g,'product'+name,'Multiply_DoubleDouble','parts.'+name,factor)
        clamped=call(g,'clamp'+name,KML+':FClamp',{'Value':product},Min=.05,Max=20)
        parts[name]=call(g,'choose'+name,KML+':SelectFloat',{'A':clamped,'B':'parts.'+name,'bPickA':changed})
    set_value(g,'value','local:ResultScaled',call(g,'make',KML+':MakeVector',parts))
    g.set('yes','local:OK','true');finish_bool(g,'Valid');loc=local_out(g,'Scaled','vector')
    g.chain('entry','valid','value','yes','result');g.chain('valid.else','result')
    return g.function('ScaleFromDrag',inputs=[v('Scale','vector'),v('Kind','int'),v('Axis','int'),v('Along','double'),v('Size','double')],outputs=[v('Valid','bool'),v('Scaled','vector')],locals=[v('OK','bool','false'),loc])


def rotated():
    g=Graph();turn=call(g,'turn',KML+':RotatorFromAxisAndAngle',{'Axis':'entry.Axis','Angle':'entry.Degrees'})
    rotation=call(g,'compose',KML+':ComposeRotators',{'A':'entry.Rotation','B':turn})
    output(g,'Rotated',rotation);g.chain('entry','result')
    return g.function('RotateFromDrag',inputs=[v('Rotation','rotator'),v('Axis','vector'),v('Degrees','double')],outputs=[v('Rotated','rotator')])


def spec():
    return dict(kind='blueprint',path=MATH,parent='/Script/CoreUObject.Object',
                functions=[axis_param(),plane_point(),angle(),segment_distance(),ring_distance(),frame_axes(),pick_handle(),
                           size_for(),snap(),wrap(),delta('Axis'),delta('Plane'),delta('Ring'),scaled(),rotated()])
