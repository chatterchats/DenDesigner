"""Opt-in, content-only pack providers. Metadata imports are bounded; meshes stay soft paths."""
from graph import Graph, variable as v, GS, KSL
from runtime import ROOT, arr
from runtime_store import call, branch, combine, STR, valid_key
from runtime_world import set_value, validity
from runtime_session import prop, method
from runtime_apply import get, clear, bump, clock
from runtime_gizmo_controller import op, neg

PACK=ROOT+'BP_DenPropPack'
FIELDS={'Paths':'string','Labels':'string','Details':'string','Dimensions':'vector','Solid':'bool','SearchTexts':'string'}
MAX_PACKS=32
MAX_ROWS=2048


def types():
    key=valid_key();key['name']='ValidPackID'
    yield '18da_BP_DenPropPack',dict(kind='blueprint',path=PACK,parent='/Script/Engine.ActorComponent',
        defaults={'PrimaryComponentTick.bCanEverTick':'false'},variables=[v('SchemaVersion','int','1'),
        v('PackID','string'),v('Title','string'),v('Author','string'),v('Version','string'),
        *[v(n,k+'[]') for n,k in FIELDS.items()]],functions=[key])


def p(g,field):
    name='pack'+field
    if any(n['id']==name for n in g.nodes):return name+'.'+field
    return prop(g,name,PACK,field,get(g,'CurrentPack'))


def add(g,name,target,value):
    arr(g,name,'Add',target);g.wire((value,name+'.NewItem'))


def issue():
    g=Graph();arr(g,'len','Length',get(g,'PackIssues'));branch(g,'room',op(g,'under','Less_IntInt','len.ReturnValue',B=128))
    add(g,'append',get(g,'PackIssues'),'entry.Message');g.chain('entry','room','append')
    return g.function('PackIssue',inputs=[v('Message','string')])


def queue():
    g=Graph();branch(g,'idle',neg(g,'notbusy',get(g,'PacksLoading')))
    arr(g,'len','Length','entry.Providers');branch(g,'limit',op(g,'max','LessEqual_IntInt','len.ReturnValue',B=MAX_PACKS))
    set_value(g,'providers','PendingPacks','entry.Providers');g.set('cursor','PackCursor','0');g.set('row','PackRow','0');g.set('active','PacksLoading','true');g.set('current','CurrentPack')
    g.call('issue','self:PackIssue',Message='Too many prop packs (maximum 32); pack import skipped.')
    g.chain('entry','idle','limit','providers','cursor','row','current','active');g.chain('limit.else','issue')
    return g.function('QueuePropPacks',inputs=[v('Providers','object:/Script/Engine.ActorComponent[]')])


def discover():
    g=Graph();g.call('init','self:Initialize');state=call(g,'state',GS+':GetGameState',{'WorldContextObject':'entry.Context'})
    branch(g,'valid',validity(g,'statevalid',state))
    components=call(g,'components','/Script/Engine.Actor:K2_GetComponentsByClass',{'self':state},ComponentClass=PACK)
    g.call('queue','self:QueuePropPacks');g.wire((components,'queue.Providers'));g.chain('entry','init','valid','queue')
    return g.function('DiscoverPropPacks',inputs=[v('Context','object:/Script/CoreUObject.Object')])


def begin():
    g=Graph();branch(g,'valid',validity(g,'object',get(g,'CurrentPack')))
    method(g,'id',PACK,'ValidPackID',get(g,'CurrentPack'),{'Key':p(g,'PackID')})
    arr(g,'rows','Length',p(g,'Paths'))
    tests=['id.Valid',op(g,'schema','EqualEqual_IntInt',p(g,'SchemaVersion'),B=1),
        op(g,'nonempty','Greater_IntInt','rows.ReturnValue',B=0),op(g,'limit','LessEqual_IntInt','rows.ReturnValue',B=MAX_ROWS)]
    for name in ['Title','Author','Version']:
        length=call(g,'len'+name,STR+'Len',{'S':p(g,name)})
        tests += [op(g,'max'+name,'LessEqual_IntInt',length,B=96)]
        if name=='Title':tests += [op(g,'min'+name,'Greater_IntInt',length,B=0)]
    for field in FIELDS:
        if field=='Paths':continue
        arr(g,'len'+field,'Length',p(g,field));tests += [op(g,'aligned'+field,'EqualEqual_IntInt','len'+field+'.ReturnValue','rows.ReturnValue')]
    branch(g,'header',combine(g,'headerok',tests))
    # Reject every provider with a conflicting ID, independent of component order.
    g.get('scan','local:Scan');arr(g,'total','Length',get(g,'PendingPacks'));branch(g,'loop',op(g,'more','Less_IntInt','scan.Scan','total.ReturnValue'))
    arr(g,'other','Get',get(g,'PendingPacks'));g.wire(('scan.Scan','other.Index'));g.node('cast','cast',**{'class':PACK});g.wire(('other.Item','cast.Object'))
    otherid=prop(g,'otherid',PACK,'PackID','cast.AsBP Den Prop Pack')
    same=call(g,'sameid',STR+'EqualEqual_StriStri',{'A':otherid,'B':p(g,'PackID')})
    branch(g,'conflict',combine(g,'conflictcheck',[same,op(g,'different','NotEqual_IntInt','scan.Scan',get(g,'PackCursor'))]))
    set_value(g,'next','local:Scan',op(g,'inc','Add_IntInt','scan.Scan',B=1))
    arr(g,'known','Contains',get(g,'RegisteredPackIDs'));g.wire((p(g,'PackID'),'known.ItemToFind'));branch(g,'new',neg(g,'unknown','known.ReturnValue'))
    add(g,'remember',get(g,'RegisteredPackIDs'),p(g,'PackID'));g.set('row','PackRow','0');g.set('shelf','PackShelf','-1');g.set('yes','local:WasAccepted','true')
    g.get('accepted','local:WasAccepted');g.wire(('accepted.WasAccepted','result.Accepted'))
    msg=call(g,'message',STR+'Concat_StrStr',{'B':p(g,'PackID')},A='Ignored invalid or conflicting prop pack: ')
    g.call('issue','self:PackIssue');g.wire((msg,'issue.Message'))
    g.chain('entry','valid','id','header','loop','cast','conflict');g.chain('conflict.else','next','loop');g.chain('cast.CastFailed','next')
    g.chain('loop.else','new','remember','row','shelf','yes','result');g.chain('new.else','result')
    g.chain('valid.else','result');g.chain('header.else','issue','result');g.chain('conflict','issue')
    return g.function('BeginPropPack',outputs=[v('Accepted','bool')],locals=[v('WasAccepted','bool','false'),v('Scan','int','0')])


def shelf():
    from runtime_catalog import DATA,d
    g=Graph();branch(g,'needed',op(g,'noshelf','Less_IntInt',get(g,'PackShelf'),B=0))
    branch(g,'group',op(g,'nogroup','Less_IntInt',get(g,'PackGroup'),B=0))
    arr(g,'groupcount','Length',d(g,'Groups'));set_value(g,'groupid','PackGroup','groupcount.ReturnValue')
    g.get('grouptext','local:GroupTitle');g.get('zero','local:Zero');add(g,'groupname',d(g,'Groups'),'grouptext.GroupTitle');add(g,'count',d(g,'GroupCounts'),'zero.Zero')
    arr(g,'shelflen','Length',d(g,'ShelfLabels'));set_value(g,'shelfid','PackShelf','shelflen.ReturnValue')
    prev='shelfid'
    for field,value in [('ShelfLabels',p(g,'Title')),('ShelfTitles',p(g,'Title')),('ShelfStarts',d(g,'Count')),('ShelfGroups',get(g,'PackGroup'))]:
        add(g,field,d(g,field),value);g.chain(prev,field);prev=field
    add(g,'shelfcount',d(g,'ShelfCounts'),'zero.Zero')
    g.chain('entry','needed','group','groupid','groupname','count','shelfid');g.chain('group.else','shelfid');g.chain(prev,'shelfcount')
    return g.function('EnsurePackShelf',locals=[v('GroupTitle','string','Prop packs'),v('Zero','int','0')])


def row():
    from runtime_catalog import DATA,d
    g=Graph()
    for field in FIELDS:
        arr(g,'read'+field,'Get',p(g,field));g.wire((get(g,'PackRow'),'read'+field+'.Index'))
    path='readPaths.Item';label='readLabels.Item'
    checks=[call(g,'prefix',STR+'StartsWith',{'SourceString':path},InPrefix='/'),
        call(g,'dot',STR+'Contains',{'SearchIn':path},Substring='.',bUseCase='true'),
        neg(g,'nosub',call(g,'sub',STR+'Contains',{'SearchIn':path},Substring=':',bUseCase='true')),
        op(g,'pathmax','LessEqual_IntInt',call(g,'pathlen',STR+'Len',{'S':path}),B=1023),
        op(g,'labelmin','Greater_IntInt',call(g,'labellen',STR+'Len',{'S':label}),B=0),
        op(g,'labelmax','LessEqual_IntInt','labellen.ReturnValue',B=96)]
    for field in ['Details','SearchTexts']:
        checks.append(op(g,'max'+field,'LessEqual_IntInt',call(g,'len'+field,STR+'Len',{'S':'read'+field+'.Item'}),B=512))
    # Bad dimensions are metadata only, but reject NaNs, negatives and extreme sizes.
    g.call('xyz','/Script/Engine.KismetMathLibrary:BreakVector');g.wire(('readDimensions.Item','xyz.InVec'))
    for axis in 'XYZ':
        checks.extend([op(g,'min'+axis,'GreaterEqual_DoubleDouble','xyz.'+axis,B=0),op(g,'max'+axis,'LessEqual_DoubleDouble','xyz.'+axis,B=100000)])
    branch(g,'valid',combine(g,'rowok',checks))
    g.call('find','self:FindPath');g.wire((path,'find.Path'));branch(g,'unique',op(g,'missing','Less_IntInt','find.Index',B=0))
    g.call('shelf','self:EnsurePackShelf');previous='shelf'
    for field in FIELDS:
        value='read'+field+'.Item'
        if field=='SearchTexts':
            for i,extra in enumerate([label,path,p(g,'PackID'),p(g,'Title'),p(g,'Author')]):
                value=call(g,'searchspace'+str(i),STR+'Concat_StrStr',{'A':value},B=' ')
                value=call(g,'searchjoin'+str(i),STR+'Concat_StrStr',{'A':value,'B':extra})
            value=call(g,'lower',STR+'ToLower',{'SourceString':value})
        add(g,'add'+field,d(g,field),value);g.chain(previous,'add'+field);previous='add'+field
    add(g,'shelfref',d(g,'ShelfIDs'),op(g,'shelfnumber','Add_IntInt',get(g,'PackShelf'),B=1));g.chain(previous,'shelfref')
    count=op(g,'newcount','Add_IntInt',d(g,'Count'),B=1);set_value(g,'count',DATA+':Count',count);g.wire((get(g,'Data'),'count.self'));g.chain('shelfref','count');previous='count'
    for field,index in [('ShelfCounts',get(g,'PackShelf')),('GroupCounts',get(g,'PackGroup'))]:
        arr(g,'old'+field,'Get',d(g,field));g.wire((index,'old'+field+'.Index'))
        arr(g,'set'+field,'Set',d(g,field));g.wire((index,'set'+field+'.Index'),(op(g,'plus'+field,'Add_IntInt','old'+field+'.Item',B=1),'set'+field+'.Item'));g.chain(previous,'set'+field);previous='set'+field
    bump(g,'next','PackRow');g.call('issue','self:PackIssue');g.wire((call(g,'message',STR+'Concat_StrStr',{'B':path},A='Skipped invalid or duplicate prop: '),'issue.Message'))
    g.chain('entry','valid','find','unique','shelf');g.chain(previous,'next');g.chain('valid.else','issue','next');g.chain('unique.else','issue')
    return g.function('ImportPackRow')


def step():
    g=Graph();branch(g,'active',get(g,'PacksLoading'));arr(g,'len','Length',get(g,'PendingPacks'))
    branch(g,'more',op(g,'within','Less_IntInt',get(g,'PackCursor'),'len.ReturnValue'))
    branch(g,'current',validity(g,'valid',get(g,'CurrentPack')));arr(g,'rows','Length',p(g,'Paths'));branch(g,'row',op(g,'rowwithin','Less_IntInt',get(g,'PackRow'),'rows.ReturnValue'))
    g.call('import','self:ImportPackRow');bump(g,'next','PackCursor');g.set('reset','CurrentPack')
    arr(g,'pack','Get',get(g,'PendingPacks'));g.wire((get(g,'PackCursor'),'pack.Index'));g.node('cast','cast',**{'class':PACK});g.wire(('pack.Item','cast.Object'))
    set_value(g,'currentpack','CurrentPack','cast.AsBP Den Prop Pack');g.call('begin','self:BeginPropPack');branch(g,'accepted','begin.Accepted')
    g.set('done','PacksLoading','false');clear(g,'clear','PendingPacks')
    g.chain('entry','active','more','current','row','import');g.chain('row.else','next','reset')
    g.chain('current.else','cast','currentpack','begin','accepted');g.chain('accepted.else','next');g.chain('cast.CastFailed','next')
    g.chain('more.else','done','clear')
    return g.function('StepPropPacks')


def pump():
    g=Graph();set_value(g,'start','local:StartedAt',clock(g,'clock'));g.get('started','local:StartedAt');g.get('steps','local:Steps')
    branch(g,'loop',combine(g,'budget',[get(g,'PacksLoading'),op(g,'max','Less_IntInt','steps.Steps',B=8),op(g,'time','Less_DoubleDouble',op(g,'elapsed','Subtract_DoubleDouble',clock(g,'now'),'started.StartedAt'),B=.003)]))
    g.call('step','self:StepPropPacks');set_value(g,'next','local:Steps',op(g,'inc','Add_IntInt','steps.Steps',B=1));g.chain('entry','start','loop','step','next','loop')
    return g.function('PumpPropPacks',locals=[v('StartedAt','double'),v('Steps','int','0')])


def variables():
    return [v('PendingPacks','object:/Script/Engine.ActorComponent[]'),v('CurrentPack','object:'+PACK),v('PacksLoading','bool'),
        v('PackCursor','int'),v('PackRow','int'),v('PackShelf','int','-1'),v('PackGroup','int','-1'),v('RegisteredPackIDs','string[]'),v('PackIssues','string[]')]


def functions():return [issue(),queue(),discover(),begin(),shelf(),row(),step(),pump()]
