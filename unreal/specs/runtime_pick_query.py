"""Budgeted native candidate discovery and ray queries for BP_DenPicker."""
from graph import Graph, variable as v, KML, KSL, GS
from runtime import arr, unpack
from runtime_store import call, branch, combine
from runtime_world import ACTOR, SCENE, SMC, PRIMITIVE, WORLD, set_value, validity
from runtime_session import prop
from runtime_apply import get, clock, bump, clear
from runtime_pick import FACT, COMP


def begin_index():
    g=Graph();g.call('cancel','self:CancelQuery');set_value(g,'manager','Manager','entry.WorldManager')
    branch(g,'valid',validity(g,'check','entry.WorldManager'))
    call(g,'refresh',WORLD+':RefreshActors',{'self':'entry.WorldManager'})
    actors=prop(g,'actors',WORLD,'WorldActors','entry.WorldManager');set_value(g,'copy','IndexActors',actors)
    clear(g,'surface','SurfaceCandidates');clear(g,'bounds','BoundsCandidates');clear(g,'components','IndexComponents')
    g.set('actor','IndexActor','0');g.set('component','IndexComponent','-1');g.set('start','Indexing','true')
    g.set('stop','Indexing','false');clear(g,'oldactors','IndexActors')
    g.chain('entry','cancel','stop','oldactors','surface','bounds','components','manager','valid','refresh','copy','actor','component','start')
    return g.function('BeginIndex',inputs=[v('WorldManager','object:'+WORLD)])


def remove_indexed_component():
    # Store only removes eligibility: keep every other indexed candidate. The
    # normal candidate validity/visibility checks still protect in-flight picks.
    g=Graph();g.node('cast','cast',**{'class':SMC});g.wire(('entry.Component','cast.Object'))
    for name,var in [('surface','SurfaceCandidates'),('bounds','BoundsCandidates')]:
        arr(g,name,'RemoveItem',get(g,var));g.wire(('cast.AsStatic Mesh Component',name+'.Item'))
    g.chain('entry','cast','surface','bounds')
    return g.function('RemoveIndexedComponent',inputs=[v('Component','object:'+PRIMITIVE)])


def index_candidate():
    g=Graph();g.call('classify','self:Classify',EditStructure='true',SelectFloors='true',SelectWalls='true');g.wire((get(g,'Manager'),'classify.Manager'),('entry.Component','classify.Component'))
    unpack(g,'facts',FACT,'classify.Facts');branch(g,'allowed','facts.Allowed')
    call(g,'bounds',KSL+':GetComponentBounds',{'Component':'entry.Component'})
    size=call(g,'size',KML+':Vector_GetAbsMax',{'A':'bounds.BoxExtent'});branch(g,'sizeok',call(g,'within',KML+':LessEqual_DoubleDouble',{'A':size},B=1000))
    g.call('needed','self:NeedsBounds');g.wire(('entry.Component','needed.Component'))
    collision=call(g,'collision',PRIMITIVE+':GetCollisionEnabled',{'self':'entry.Component'})
    branch(g,'surface',call(g,'nocollision',KML+':EqualEqual_ByteByte',{'A':collision},B=0))
    own=call(g,'own',KML+':EqualEqual_IntInt',{'A':'facts.Kind'},B=0);branch(g,'owned',combine(g,'ownedbounds',[own,'needed.Needed']))
    arr(g,'addsurface','AddUnique',get(g,'SurfaceCandidates'));g.wire(('entry.Component','addsurface.NewItem'))
    branch(g,'missing','needed.Needed');arr(g,'addbounds','AddUnique',get(g,'BoundsCandidates'));g.wire(('entry.Component','addbounds.NewItem'))
    g.chain('entry','classify','allowed','sizeok','needed','surface','owned','addbounds');g.chain('owned.else','addsurface');g.chain('surface.else','missing','addbounds')
    return g.function('IndexCandidate',inputs=[v('Component','object:'+SMC)])


def index_step():
    g=Graph();arr(g,'len','Length',get(g,'IndexActors'))
    branch(g,'within',call(g,'actorwithin',KML+':Less_IntInt',{'A':get(g,'IndexActor'),'B':'len.ReturnValue'}))
    arr(g,'actor','Get',get(g,'IndexActors'));g.wire((get(g,'IndexActor'),'actor.Index'));branch(g,'valid',validity(g,'actorvalid','actor.Item'))
    branch(g,'cached',call(g,'cachedcheck',KML+':GreaterEqual_IntInt',{'A':get(g,'IndexComponent')},B=0))
    components=call(g,'components',ACTOR+':K2_GetComponentsByClass',{'self':'actor.Item'},ComponentClass=SMC)
    set_value(g,'cache','IndexComponents',components);g.set('start','IndexComponent','0')
    arr(g,'clen','Length',get(g,'IndexComponents'));branch(g,'component',call(g,'componentwithin',KML+':Less_IntInt',{'A':get(g,'IndexComponent'),'B':'clen.ReturnValue'}))
    arr(g,'item','Get',get(g,'IndexComponents'));g.wire((get(g,'IndexComponent'),'item.Index'))
    branch(g,'componentvalid',validity(g,'cvalid','item.Item'))
    g.node('cast','cast',**{'class':SMC});g.wire(('item.Item','cast.Object'))
    g.call('consider','self:IndexCandidate');g.wire(('cast.AsStatic Mesh Component','consider.Component'))
    bump(g,'nextcomponent','IndexComponent');bump(g,'nextactor','IndexActor');g.set('uncache','IndexComponent','-1');clear(g,'releasecomponents','IndexComponents')
    g.set('done','Indexing','false');clear(g,'releaseactors','IndexActors')
    g.chain('entry','within','valid','cached','component','componentvalid','cast','consider','nextcomponent')
    g.chain('cached.else','cache','start');g.chain('valid.else','nextactor','uncache','releasecomponents');g.chain('component.else','nextactor');g.chain('componentvalid.else','nextcomponent');g.chain('cast.CastFailed','nextcomponent');g.chain('within.else','done','releaseactors','releasecomponents')
    return g.function('IndexStep')


def pump(index):
    g=Graph();set_value(g,'started','local:StartedAt',clock(g,'start'))
    active=get(g,'Indexing' if index else 'QueryPending');g.get('steps','local:Steps');g.get('startedget','local:StartedAt')
    elapsed=call(g,'elapsed',KML+':Subtract_DoubleDouble',{'A':clock(g,'now'),'B':'startedget.StartedAt'})
    budget=call(g,'budget',KML+':Less_DoubleDouble',{'A':elapsed,'B':get(g,'BudgetSeconds')})
    stepbudget=call(g,'stepsbudget',KML+':Less_IntInt',{'A':'steps.Steps','B':get(g,'MaxSteps')})
    checks=[active,budget,stepbudget]
    if not index:checks.append(call(g,'indexed',KML+':Not_PreBool',{'A':get(g,'Indexing')}))
    branch(g,'loop',combine(g,'within',checks));g.call('step','self:'+('IndexStep' if index else 'QueryStep'))
    next_=call(g,'next',KML+':Add_IntInt',{'A':'steps.Steps'},B=1);set_value(g,'advance','local:Steps',next_)
    g.chain('entry','started','loop','step','advance','loop')
    return g.function('PumpIndex' if index else 'PumpQuery',locals=[v('StartedAt','double'),v('Steps','int','0')])


def cancel():
    g=Graph();g.set('pending','QueryPending','false');g.set('ready','QueryReady','false');g.set('hit','QueryComponent');g.chain('entry','pending','ready','hit')
    return g.function('CancelQuery')


def start_query():
    g=Graph();g.call('cancel','self:CancelQuery')
    for node,var,pin in [('origin','RayOrigin','entry.Origin'),('structure','QueryStructure','entry.EditStructure'),('floors','QueryFloors','entry.SelectFloors'),('walls','QueryWalls','entry.SelectWalls'),('reach','RayLimit','entry.Limit')]:set_value(g,node,var,pin)
    direction=call(g,'normal',KML+':Normal',{'A':'entry.Direction'},Tolerance=1e-8);set_value(g,'direction','RayDirection',direction)
    end=call(g,'end',KML+':Add_VectorVector',{'A':'entry.Origin','B':call(g,'offset',KML+':Multiply_VectorFloat',{'A':direction,'B':'entry.Limit'})})
    call(g,'trace',KSL+':LineTraceSingle',{'WorldContextObject':get(g,'Manager'),'Start':'entry.Origin','End':end},TraceChannel='TraceTypeQuery1',bTraceComplex='true',DrawDebugType='None',bIgnoreSelf='true')
    call(g,'hit',GS+':BreakHitResult',{'Hit':'trace.OutHit'})
    set_value(g,'hitflag','QueryHadTrace','trace.ReturnValue');branch(g,'blocked','trace.ReturnValue')
    set_value(g,'hitcomponent','QueryComponent','hit.HitComponent');set_value(g,'hitt','TraceDistance','hit.Distance')
    set_value(g,'missdistance','TraceDistance','entry.Limit');set_value(g,'nearest','BestDistance',get(g,'TraceDistance'))
    g.set('volume','SurfaceVolume','1e30');g.set('cursor','QueryCursor','0');g.set('phase','QueryPhase','0');g.set('pending','QueryPending','true')
    g.chain('entry','cancel','origin','structure','floors','walls','reach','direction','trace','hitflag','blocked','hitcomponent','hitt','nearest','volume','cursor','phase','pending');g.chain('blocked.else','missdistance','nearest')
    return g.function('RequestPick',inputs=[v('Origin','vector'),v('Direction','vector'),v('Limit','double'),v('EditStructure','bool'),v('SelectFloors','bool'),v('SelectWalls','bool')])


def query_candidate():
    g=Graph();branch(g,'valid',validity(g,'check','entry.Component'))
    visible=call(g,'visible',SCENE+':IsVisible',{'self':'entry.Component'});owner=call(g,'owner',COMP+':GetOwner',{'self':'entry.Component'})
    branch(g,'ownerok',validity(g,'ownervalid',owner));hidden=prop(g,'hidden',ACTOR,'bHidden',owner)
    branch(g,'shown',combine(g,'showncheck',[visible,call(g,'nothidden',KML+':Not_PreBool',{'A':hidden})]))
    mesh=prop(g,'mesh',SMC,'StaticMesh','entry.Component');path=call(g,'path',KSL+':GetPathName',{'Object':mesh})
    g.call('floor','self:IsFloor');g.wire((path,'floor.MeshPath'))
    floorok=combine(g,'floorok',[get(g,'QueryFloors'),call(g,'notfloor',KML+':Not_PreBool',{'A':'floor.IsFloor'})],True);branch(g,'floors',floorok)
    g.call('wall','self:IsWall');g.wire((path,'wall.MeshPath'))
    wallok=combine(g,'wallok',[get(g,'QueryWalls'),call(g,'notwall',KML+':Not_PreBool',{'A':'wall.IsWall'})],True);branch(g,'walls',wallok)
    branch(g,'surface','entry.SurfaceOnly');branch(g,'hastrace',get(g,'QueryHadTrace'))
    extra=call(g,'slack',KML+':Add_DoubleDouble',{'A':get(g,'TraceDistance')},B=3)
    set_value(g,'surfacelimit','local:MaximumT',extra);set_value(g,'boundslimit','local:MaximumT',get(g,'BestDistance'))
    g.get('limit','local:MaximumT');g.call('box','self:ComponentBox');g.wire(('entry.Component','box.Component'),(get(g,'RayOrigin'),'box.Origin'),(get(g,'RayDirection'),'box.Direction'),('limit.MaximumT','box.Limit'))
    branch(g,'hit','box.Hit');branch(g,'surfacetest','entry.SurfaceOnly')
    depth=call(g,'depth',KML+':Subtract_DoubleDouble',{'A':get(g,'TraceDistance')},B=20)
    branch(g,'close',call(g,'closecheck',KML+':GreaterEqual_DoubleDouble',{'A':'box.Distance','B':depth}))
    call(g,'bounds',KSL+':GetComponentBounds',{'Component':'entry.Component'});call(g,'extents',KML+':BreakVector',{'InVec':'bounds.BoxExtent'})
    sizes=[call(g,'extent'+axis,KML+':Add_DoubleDouble',{'A':'extents.'+axis},B=1) for axis in ['X','Y','Z']]
    volume=call(g,'volume',KML+':Multiply_DoubleDouble',{'A':call(g,'xy',KML+':Multiply_DoubleDouble',{'A':sizes[0],'B':sizes[1]}),'B':sizes[2]})
    branch(g,'smaller',call(g,'smallcheck',KML+':Less_DoubleDouble',{'A':volume,'B':get(g,'SurfaceVolume')}));set_value(g,'savevolume','SurfaceVolume',volume)
    nearest=call(g,'minimum',KML+':FMin',{'A':get(g,'TraceDistance'),'B':'box.Distance'});set_value(g,'surfacet','BestDistance',nearest)
    branch(g,'closer',call(g,'closebounds',KML+':Less_DoubleDouble',{'A':'box.Distance','B':get(g,'BestDistance')}))
    set_value(g,'boundst','BestDistance','box.Distance');set_value(g,'remember','QueryComponent','entry.Component')
    g.chain('entry','valid','ownerok','shown','floor','floors','wall','walls','surface','hastrace','surfacelimit','box','hit','surfacetest','close','smaller','savevolume','surfacet','remember')
    g.chain('surface.else','boundslimit','box');g.chain('surfacetest.else','closer','boundst','remember')
    return g.function('QueryCandidate',inputs=[v('Component','object:'+SMC),v('SurfaceOnly','bool')],locals=[v('MaximumT','double')])


def query_step():
    g=Graph();surface=call(g,'surface',KML+':EqualEqual_IntInt',{'A':get(g,'QueryPhase')},B=0);branch(g,'phase',surface)
    # Read the selected array directly. Copying it once per candidate makes a
    # query quadratic in the number of fallback meshes in a streamed Den.
    for name,var in [('surfaces','SurfaceCandidates'),('bounds','BoundsCandidates')]:
        candidates=get(g,var);arr(g,name+'len','Length',candidates)
        branch(g,name+'within',call(g,name+'check',KML+':Less_IntInt',{'A':get(g,'QueryCursor'),'B':name+'len.ReturnValue'}))
        arr(g,name+'item','Get',candidates);g.wire((get(g,'QueryCursor'),name+'item.Index'))
        g.call(name+'test','self:QueryCandidate',SurfaceOnly='true' if name=='surfaces' else 'false')
        g.wire((name+'item.Item',name+'test.Component'))
        g.chain(name+'within',name+'test','next')
    bump(g,'next','QueryCursor')
    g.set('phase2','QueryPhase','1');g.set('restart','QueryCursor','0')
    g.call('classify','self:Classify');g.wire((get(g,'Manager'),'classify.Manager'),(get(g,'QueryComponent'),'classify.Component'),(get(g,'QueryStructure'),'classify.EditStructure'),(get(g,'QueryFloors'),'classify.SelectFloors'),(get(g,'QueryWalls'),'classify.SelectWalls'))
    set_value(g,'result','QueryResult','classify.Facts');g.set('done','QueryPending','false');g.set('ready','QueryReady','true')
    g.chain('entry','phase','surfaceswithin');g.chain('phase.else','boundswithin')
    g.chain('surfaceswithin.else','phase2','restart');g.chain('boundswithin.else','classify','result','done','ready')
    return g.function('QueryStep')


def variables():
    return [v('Manager','object:'+WORLD),v('IndexActors','object:'+ACTOR+'[]'),v('IndexComponents','object:'+COMP+'[]'),v('SurfaceCandidates','object:'+SMC+'[]'),v('BoundsCandidates','object:'+SMC+'[]'),v('IndexActor','int'),v('IndexComponent','int','-1'),v('Indexing','bool'),v('BudgetSeconds','double','0.003'),v('MaxSteps','int','4096'),v('RayOrigin','vector'),v('RayDirection','vector'),v('RayLimit','double'),v('TraceDistance','double'),v('BestDistance','double'),v('SurfaceVolume','double'),v('QueryComponent','object:'+PRIMITIVE),v('QueryCursor','int'),v('QueryPhase','int'),v('QueryPending','bool'),v('QueryReady','bool'),v('QueryHadTrace','bool'),v('QueryStructure','bool'),v('QueryFloors','bool'),v('QueryWalls','bool'),v('QueryResult','struct:'+FACT)]


def functions():
    from runtime_pick_delta import functions as delta_functions
    return [*delta_functions(),begin_index(),remove_indexed_component(),index_candidate(),index_step(),pump(True),pump(False),cancel(),start_query(),query_candidate(),query_step()]
