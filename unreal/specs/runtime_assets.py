"""One immutable asynchronous asset request per transient actor.

The caller sets a request once, polls Done, then consumes Result or destroys the
job to cancel it. Jobs never call back into editor widgets or mutate world props.
Destroying a job/world invalidates its latent callback target and releases refs.
"""
from graph import Graph, variable as v, KML, KSL
from runtime_store import call, branch, combine, STR

ROOT='/DenDesignerGF/Runtime/'
JOB=ROOT+'BP_DenAssetJob'
ACTOR='/Script/Engine.Actor'


def valid_asset_path():
    g=Graph()
    length=call(g,'length',STR+'Len',{'S':'entry.Path'})
    minimum=call(g,'minimum',KML+':Greater_IntInt',{'A':length},B=3)
    maximum=call(g,'maximum',KML+':LessEqual_IntInt',{'A':length},B=1023)
    starts=call(g,'starts',STR+'StartsWith',{'SourceString':'entry.Path'},InPrefix='/')
    subobject=call(g,'subobject',STR+'Contains',{'SearchIn':'entry.Path'},Substring=':',bUseCase='true',bSearchFromEnd='false')
    assetonly=call(g,'assetonly',KML+':Not_PreBool',{'A':subobject})
    dot=call(g,'dot',STR+'Contains',{'SearchIn':'entry.Path'},Substring='.',bUseCase='true',bSearchFromEnd='false')
    valid=combine(g,'validpath',[minimum,maximum,starts,assetonly,dot])
    g.wire((valid,'result.Valid'));g.chain('entry','result')
    return g.function('ValidAssetPath',inputs=[v('Path','string')],outputs=[v('Valid','bool')])


def request():
    g=Graph()
    g.get('has','HasRequest')
    unused=call(g,'unused',KML+':Not_PreBool',{'A':'has.HasRequest'})
    g.call('pathvalid','self:ValidAssetPath');g.wire(('entry.Path','pathvalid.Path'))
    branch(g,'valid',combine(g,'validrequest',[unused,'pathvalid.Valid']))
    g.set('path','RequestedPath');g.wire(('entry.Path','path.RequestedPath'))
    g.set('hasflag','HasRequest','true')
    g.set('yes','local:OK','true')
    g.get('ok','local:OK');g.wire(('ok.OK','result.Accepted'))
    g.chain('entry','pathvalid','valid','path','hasflag','yes','result');g.chain('valid.else','result')
    return g.function('Request',inputs=[v('Path','string')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def finish():
    g=Graph()
    g.get('started','Started');g.get('done','Done')
    notdone=call(g,'notdone',KML+':Not_PreBool',{'A':'done.Done'})
    branch(g,'valid',combine(g,'pending',['started.Started',notdone]))
    g.set('store','Result');g.wire(('entry.LoadedObject','store.Result'))
    valid=call(g,'loaded',KSL+':IsValid',{'Object':'entry.LoadedObject'})
    failed=call(g,'failed',KML+':Not_PreBool',{'A':valid})
    g.set('error','Failed');g.wire((failed,'error.Failed'))
    g.set('doneflag','Done','true')
    call(g,'stop',ACTOR+':SetActorTickEnabled',bEnabled='false')
    g.chain('entry','valid','store','error','doneflag','stop')
    return g.function('FinishRequest',inputs=[v('LoadedObject','object:/Script/CoreUObject.Object')])


def spec():
    g=Graph()
    g.node('tick','event',name='ReceiveTick')
    g.get('requested','HasRequest');g.get('started','Started')
    notstarted=call(g,'notstarted',KML+':Not_PreBool',{'A':'started.Started'})
    branch(g,'ready',combine(g,'start',['requested.HasRequest',notstarted]))
    g.set('mark','Started','true')
    g.get('path','RequestedPath')
    path=call(g,'softpath',KSL+':MakeSoftObjectPath',{'PathString':'path.RequestedPath'})
    reference=call(g,'reference',KSL+':Conv_SoftObjPathToSoftObjRef',{'SoftObjectPath':path})
    g.node('load','load_asset');g.wire((reference,'load.Asset'))
    g.call('finish','self:FinishRequest');g.wire(('load.Object','finish.LoadedObject'))
    g.chain('tick','ready','mark','load');g.chain('load.Completed','finish')
    return dict(kind='blueprint',path=JOB,parent=ACTOR,
        defaults={'PrimaryActorTick.bCanEverTick':'true','PrimaryActorTick.bStartWithTickEnabled':'true'},
        variables=[v('RequestedPath','string'),v('HasRequest','bool','false'),v('Started','bool','false'),
                   v('Done','bool','false'),v('Failed','bool','false'),v('Result','object:/Script/CoreUObject.Object')],
        graph=g.spec(),functions=[valid_asset_path(),request(),finish()])
