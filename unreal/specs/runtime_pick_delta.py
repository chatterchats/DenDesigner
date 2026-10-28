"""Refresh only objects touched by an incremental world batch, never a Den scan."""
from graph import Graph,variable as v,KML
from runtime import arr,unpack,ENTRY,MUTATION
from runtime_store import call,branch
from runtime_world import ACTOR,SMC,RECORD,WORLD,validity,set_value
from runtime_session import prop
from runtime_apply import get


def refresh_actor():
    g=Graph();branch(g,'valid',validity(g,'actorvalid','entry.Actor'))
    components=call(g,'components',ACTOR+':K2_GetComponentsByClass',{'self':'entry.Actor'},ComponentClass=SMC)
    arr(g,'length','Length',components);g.get('cursor','local:ChangedComponentIndex')
    branch(g,'within',call(g,'withincheck',KML+':Less_IntInt',{'A':'cursor.ChangedComponentIndex','B':'length.ReturnValue'}))
    arr(g,'item','Get',components);g.wire(('cursor.ChangedComponentIndex','item.Index'))
    g.node('cast','cast',**{'class':SMC});g.wire(('item.Item','cast.Object'))
    g.call('remove','self:RemoveIndexedComponent');g.wire(('cast.AsStatic Mesh Component','remove.Component'))
    g.call('add','self:IndexCandidate');g.wire(('cast.AsStatic Mesh Component','add.Component'))
    set_value(g,'advance','local:ChangedComponentIndex',call(g,'next',KML+':Add_IntInt',{'A':'cursor.ChangedComponentIndex'},B=1))
    g.chain('entry','valid','within','cast','remove','add','advance','within');g.chain('cast.CastFailed','advance')
    return g.function('RefreshIndexedActor',inputs=[v('Actor','object:'+ACTOR)],locals=[v('ChangedComponentIndex','int','0')])


def prune():
    g=Graph();previous='entry';locals_=[]
    for prefix,var in [('surface','SurfaceCandidates'),('bounds','BoundsCandidates')]:
        local=prefix+'PruneIndex';locals_.append(v(local,'int'))
        arr(g,prefix+'length','Length',get(g,var))
        set_value(g,prefix+'start','local:'+local,call(g,prefix+'last',KML+':Subtract_IntInt',{'A':prefix+'length.ReturnValue'},B=1));g.get(prefix+'cursor','local:'+local)
        cursor=prefix+'cursor.'+local
        branch(g,prefix+'within',call(g,prefix+'check',KML+':GreaterEqual_IntInt',{'A':cursor},B=0))
        arr(g,prefix+'item','Get',get(g,var));g.wire((cursor,prefix+'item.Index'))
        branch(g,prefix+'valid',validity(g,prefix+'alive',prefix+'item.Item'))
        arr(g,prefix+'remove','Remove',get(g,var));g.wire((cursor,prefix+'remove.IndexToRemove'))
        set_value(g,prefix+'advance','local:'+local,call(g,prefix+'next',KML+':Subtract_IntInt',{'A':cursor},B=1))
        g.chain(previous,prefix+'start',prefix+'within',prefix+'valid',prefix+'advance',prefix+'within')
        g.chain(prefix+'valid.else',prefix+'remove',prefix+'advance');previous=prefix+'within.else'
    return g.function('PruneInvalidIndexCandidates',locals=locals_)


def refresh_changes():
    g=Graph();set_value(g,'pending','local:RestartQuery',get(g,'QueryPending'));g.call('cancel','self:CancelQuery');g.call('prune','self:PruneInvalidIndexCandidates')
    branch(g,'manager',validity(g,'managercheck',get(g,'Manager')))
    arr(g,'length','Length','entry.Mutations');g.get('cursor','local:ChangedEntryIndex')
    branch(g,'within',call(g,'withincheck',KML+':Less_IntInt',{'A':'cursor.ChangedEntryIndex','B':'length.ReturnValue'}))
    arr(g,'item','Get','entry.Mutations');g.wire(('cursor.ChangedEntryIndex','item.Index'));unpack(g,'mutation',MUTATION,'item.Item');unpack(g,'data',ENTRY,'mutation.Value')
    branch(g,'placed',call(g,'placedkind',KML+':EqualEqual_IntInt',{'A':'data.Kind'},B=0))
    branch(g,'native',call(g,'nativekind',KML+':EqualEqual_IntInt',{'A':'data.Kind'},B=2))
    for prefix,collection,method in [('placed','Placed','FindPlaced'),('native','Records','FindRecord')]:
        call(g,prefix+'find',WORLD+':'+method,{'self':get(g,'Manager'),'Key':'data.Key'})
        branch(g,prefix+'found',call(g,prefix+'exists',KML+':GreaterEqual_IntInt',{'A':prefix+'find.Index'},B=0))
        objects=prop(g,prefix+'objects',WORLD,collection,get(g,'Manager'))
        arr(g,prefix+'object','Get',objects);g.wire((prefix+'find.Index',prefix+'object.Index'))
        actor=prefix+'object.Item' if prefix=='placed' else prop(g,'recordactor',RECORD,'Actor',prefix+'object.Item')
        g.call(prefix+'refresh','self:RefreshIndexedActor');g.wire((actor,prefix+'refresh.Actor'))
        g.chain(prefix,prefix+'find',prefix+'found',prefix+'refresh','advance');g.chain(prefix+'found.else','advance')
    set_value(g,'advance','local:ChangedEntryIndex',call(g,'next',KML+':Add_IntInt',{'A':'cursor.ChangedEntryIndex'},B=1))
    g.get('restart','local:RestartQuery');branch(g,'restartquery','restart.RestartQuery')
    g.call('query','self:RequestPick')
    for pin,field in [('Origin','RayOrigin'),('Direction','RayDirection'),('Limit','RayLimit'),('EditStructure','QueryStructure'),('SelectFloors','QueryFloors'),('SelectWalls','QueryWalls')]:g.wire((get(g,field),'query.'+pin))
    g.chain('entry','pending','cancel','prune','manager','within','placed');g.chain('placed.else','native');g.chain('native.else','advance','within')
    g.chain('within.else','restartquery','query')
    return g.function('RefreshIndexChanges',inputs=[v('Mutations','struct:'+MUTATION+'[]')],locals=[v('ChangedEntryIndex','int','0'),v('RestartQuery','bool')])


def functions():return [refresh_actor(),prune(),refresh_changes()]
