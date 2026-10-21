"""Cooked catalog metadata and cancellable, budgeted native search/browse queries."""
import json
import sys
from functools import lru_cache
from pathlib import Path
from graph import Graph, variable as v, KML, KSL, GS
from runtime import ROOT, arr
from runtime_store import call, branch, combine, STR
from runtime_world import set_value, validity, finish_bool
from runtime_session import prop
from runtime_apply import get, clear, clock, bump
from runtime_gizmo_controller import op, neg

DATA=ROOT+'BP_DenCatalogData'
CATALOG=ROOT+'BP_DenCatalog'


@lru_cache(maxsize=1)
def metadata():
    source=Path(__file__).resolve().parents[1]/'data/catalog.json'
    data=json.loads(source.read_text())
    assert data['items'] and data['shelves'] and data['source_hash'], 'Incomplete catalog data'
    return data



def array_text(values,kind):
    if kind=='string':parts=[json.dumps(x,ensure_ascii=False) for x in values]
    elif kind=='vector':parts=['('+','.join(f'{a}={n}' for a,n in zip('XYZ',x))+')' for x in values]
    elif kind=='bool':parts=['True' if x else 'False' for x in values]
    else:parts=[str(x) for x in values]
    return '('+','.join(parts)+')'


def data_spec():
    data=metadata();items=data['items'];shelves=data['shelves'];collections=data['collections']
    groups={c['key']:i for i,c in enumerate(collections)}
    variables=[v('Count','int',str(len(items))),v('SourceHash','string',data['source_hash'])]
    fields=[('Paths','string',[e['path'] for e in items]),('Labels','string',[e['label'] for e in items]),
            ('Details','string',[e['detail'] for e in items]),('Dimensions','vector',[e['size'] for e in items]),
            ('ShelfIDs','int',[e['shelf'] for e in items]),('Solid','bool',[e['collision'] for e in items]),
            ('SearchTexts','string',[e['search'] for e in items]),
            ('ShelfTitles','string',[e['title'] for e in shelves]),('ShelfLabels','string',[e['label'] for e in shelves]),
            ('ShelfStarts','int',[e['first']-1 for e in shelves]),('ShelfCounts','int',[e['count'] for e in shelves]),
            ('ShelfGroups','int',[groups[e['collection']] for e in shelves]),
            ('Groups','string',[e['key'] for e in collections]),('GroupCounts','int',[e['count'] for e in collections])]
    variables += [v(name,kind+'[]',array_text(values,kind)) for name,kind,values in fields]
    return dict(kind='blueprint',path=DATA,parent='/Script/CoreUObject.Object',variables=variables)


def d(g,field):
    name='data'+field
    if any(n['id']==name for n in g.nodes):return name+'.'+field
    return prop(g,name,DATA,field,get(g,'Data'))


def initialize():
    g=Graph();branch(g,'exists',validity(g,'valid',get(g,'Data')));g.node('self','self')
    obj=call(g,'create',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=DATA);g.node('cast','cast',**{'class':DATA});g.wire((obj,'cast.Object'));set_value(g,'data','Data','cast.AsBP Den Catalog Data')
    g.chain('entry','exists');g.chain('exists.else','create','cast','data')
    return g.function('Initialize')


def cancel():
    g=Graph();g.set('inactive','Active','false');g.set('notready','Ready','false');clear(g,'results','Results');clear(g,'recent','QueryRecent');g.set('total','MatchCount','0');g.set('cursor','Cursor','0');g.set('token','TokenCursor','0');bump(g,'revision','Revision')
    g.chain('entry','inactive','notready','results','recent','total','cursor','token','revision');return g.function('Cancel')


def read_item():
    g=Graph();branch(g,'valid',validity(g,'data',get(g,'Data')))
    branch(g,'range',combine(g,'rangecheck',[op(g,'min','GreaterEqual_IntInt','entry.Index',B=0),op(g,'max','Less_IntInt','entry.Index',d(g,'Count'))]))
    fields=[('Path','Paths','string'),('Label','Labels','string'),('Detail','Details','string'),('Size','Dimensions','vector'),('Shelf','ShelfIDs','int'),('HasCollision','Solid','bool')]
    previous='range'
    for name,field,kind in fields:
        arr(g,'read'+name,'Get',d(g,field));g.wire(('entry.Index','read'+name+'.Index'));set_value(g,'save'+name,'local:Out'+name,'read'+name+'.Item');g.chain(previous,'save'+name);previous='save'+name
        g.get('out'+name,'local:Out'+name);g.wire(('out'+name+'.Out'+name,'result.'+name))
    g.set('yes','local:OK','true');finish_bool(g,'Found');g.chain('entry','valid','range');g.chain(previous,'yes','result');g.chain('valid.else','result');g.chain('range.else','result')
    return g.function('ReadItem',inputs=[v('Index','int')],outputs=[v('Found','bool'),*[v(n,k) for n,_,k in fields]],locals=[v('OK','bool','false'),*[v('Out'+n,k) for n,_,k in fields]])


def find_path():
    g=Graph();branch(g,'valid',validity(g,'data',get(g,'Data')));arr(g,'find','Find',d(g,'Paths'));g.wire(('entry.Path','find.ItemToFind'));set_value(g,'found','local:FoundIndex','find.ReturnValue');g.get('out','local:FoundIndex');g.wire(('out.FoundIndex','result.Index'))
    g.chain('entry','valid','found','result');g.chain('valid.else','result')
    return g.function('FindPath',inputs=[v('Path','string')],outputs=[v('Index','int')],locals=[v('FoundIndex','int','-1')])


def search():
    g=Graph();g.call('init','self:Initialize');g.call('cancel','self:Cancel');set_value(g,'query','Query','entry.Text');g.set('kind','QueryKind','0')
    text=call(g,'lower',STR+'ToLower',{'SourceString':'entry.Text'})
    for i,ch in enumerate(['\t','\r','\n','\v','\f']):text=call(g,'space'+str(i),STR+'Replace',{'SourceString':text},From=ch,To=' ',SearchCase='CaseSensitive')
    tokens=call(g,'split',STR+'ParseIntoArray',{'SourceString':text},Delimiter=' ',CullEmptyStrings='true');set_value(g,'tokens','Tokens',tokens)
    set_value(g,'end','EndIndex',d(g,'Count'));arr(g,'len','Length',get(g,'Tokens'));branch(g,'any',op(g,'words','Greater_IntInt','len.ReturnValue',B=0))
    g.set('active','Active','true');g.set('empty','Ready','true');g.chain('entry','init','cancel','query','kind','tokens','end','any','active');g.chain('any.else','empty')
    return g.function('Search',inputs=[v('Text','string')])


def browse():
    g=Graph();g.call('init','self:Initialize');g.call('cancel','self:Cancel');branch(g,'recent',op(g,'isrecent','EqualEqual_IntInt','entry.Shelf',B=-1))
    g.set('recentkind','QueryKind','2');set_value(g,'recentcopy','QueryRecent',get(g,'Recent'));arr(g,'recentlen','Length',get(g,'QueryRecent'));set_value(g,'recentend','EndIndex','recentlen.ReturnValue')
    arr(g,'shelves','Length',d(g,'ShelfStarts'));branch(g,'valid',combine(g,'range',[op(g,'min','GreaterEqual_IntInt','entry.Shelf',B=1),op(g,'max','LessEqual_IntInt','entry.Shelf','shelves.ReturnValue')]))
    index=op(g,'index','Subtract_IntInt','entry.Shelf',B=1)
    for name,field in [('start','ShelfStarts'),('count','ShelfCounts')]:arr(g,name,'Get',d(g,field));g.wire((index,name+'.Index'))
    g.set('kind','QueryKind','1');set_value(g,'cursor','Cursor','start.Item');set_value(g,'end','EndIndex',op(g,'endvalue','Add_IntInt','start.Item','count.Item'))
    g.set('active','Active','true');g.set('empty','Ready','true');g.chain('entry','init','cancel','recent','recentkind','recentcopy','recentend','active');g.chain('recent.else','valid','kind','cursor','end','active');g.chain('valid.else','empty')
    return g.function('Browse',inputs=[v('Shelf','int')])


def remember():
    g=Graph();branch(g,'valid',validity(g,'data',get(g,'Data')));branch(g,'range',combine(g,'limits',[op(g,'min','GreaterEqual_IntInt','entry.Index',B=0),op(g,'max','Less_IntInt','entry.Index',d(g,'Count'))]))
    arr(g,'remove','RemoveItem',get(g,'Recent'));g.wire(('entry.Index','remove.Item'));arr(g,'insert','Insert',get(g,'Recent'),Index=0);g.wire(('entry.Index','insert.NewItem'))
    arr(g,'len','Length',get(g,'Recent'));branch(g,'full',op(g,'limit','Greater_IntInt','len.ReturnValue',B=40));arr(g,'trim','Resize',get(g,'Recent'),Size=40)
    g.chain('entry','valid','range','remove','insert','full','trim');return g.function('Remember',inputs=[v('Index','int')])


def advance():
    g=Graph();bump(g,'next','Cursor');g.set('token','TokenCursor','0');g.chain('entry','next','token');return g.function('Advance')


def matched():
    g=Graph();arr(g,'len','Length',get(g,'Results'));notsearch=op(g,'browse','NotEqual_IntInt',get(g,'QueryKind'),B=0)
    branch(g,'room',combine(g,'roomcheck',[notsearch,op(g,'underlimit','Less_IntInt','len.ReturnValue',B=300)],True))
    arr(g,'append','Add',get(g,'Results'));g.wire(('entry.Index','append.NewItem'));bump(g,'total','MatchCount');g.call('advance','self:Advance')
    g.chain('entry','room','append','total','advance');g.chain('room.else','total')
    return g.function('Match',inputs=[v('Index','int')])


def step():
    g=Graph();branch(g,'active',get(g,'Active'));branch(g,'more',op(g,'within','Less_IntInt',get(g,'Cursor'),get(g,'EndIndex')))
    branch(g,'search',op(g,'issearch','EqualEqual_IntInt',get(g,'QueryKind'),B=0));arr(g,'len','Length',get(g,'Tokens'));branch(g,'words',op(g,'morewords','Less_IntInt',get(g,'TokenCursor'),'len.ReturnValue'))
    arr(g,'word','Get',get(g,'Tokens'));g.wire((get(g,'TokenCursor'),'word.Index'));arr(g,'text','Get',d(g,'SearchTexts'));g.wire((get(g,'Cursor'),'text.Index'))
    found=call(g,'contains',STR+'Contains',{'SearchIn':'text.Item','Substring':'word.Item'},bUseCase='true',bSearchFromEnd='false');branch(g,'found',found);bump(g,'token','TokenCursor');g.call('skip','self:Advance')
    branch(g,'recent',op(g,'isrecent','EqualEqual_IntInt',get(g,'QueryKind'),B=2));arr(g,'recentitem','Get',get(g,'QueryRecent'));g.wire((get(g,'Cursor'),'recentitem.Index'))
    g.call('recentmatch','self:Match');g.wire(('recentitem.Item','recentmatch.Index'));g.call('match','self:Match');g.wire((get(g,'Cursor'),'match.Index'))
    g.set('done','Active','false');g.set('ready','Ready','true')
    g.chain('entry','active','more','search','words','found','token');g.chain('found.else','skip');g.chain('words.else','match');g.chain('search.else','recent','recentmatch');g.chain('recent.else','match');g.chain('more.else','done','ready')
    return g.function('Step')


def pump():
    g=Graph();set_value(g,'start','local:StartedAt',clock(g,'clock'));g.get('started','local:StartedAt');g.get('steps','local:Steps')
    elapsed=op(g,'elapsed','Subtract_DoubleDouble',clock(g,'now'),'started.StartedAt')
    branch(g,'loop',combine(g,'budget',[get(g,'Active'),op(g,'time','Less_DoubleDouble',elapsed,get(g,'BudgetSeconds')),op(g,'limit','Less_IntInt','steps.Steps',get(g,'MaxSteps'))]))
    g.call('step','self:Step');set_value(g,'next','local:Steps',op(g,'increment','Add_IntInt','steps.Steps',B=1));g.chain('entry','start','loop','step','next','loop')
    return g.function('Pump',locals=[v('StartedAt','double'),v('Steps','int','0')])


def specs():
    from runtime_prop_packs import variables as pack_variables, functions as pack_functions
    yield '18e_BP_DenCatalogData',data_spec()
    yield '18f_BP_DenCatalog',dict(kind='blueprint',path=CATALOG,parent='/Script/CoreUObject.Object',variables=[v('Data','object:'+DATA),v('Recent','int[]'),v('QueryRecent','int[]'),v('Results','int[]'),v('Tokens','string[]'),v('Query','string'),v('QueryKind','int'),v('Revision','int'),v('Cursor','int'),v('TokenCursor','int'),v('EndIndex','int'),v('MatchCount','int'),v('Active','bool'),v('Ready','bool'),v('BudgetSeconds','double','0.003'),v('MaxSteps','int','512'),*pack_variables()],functions=[initialize(),cancel(),read_item(),find_path(),search(),browse(),remember(),advance(),matched(),step(),pump(),*pack_functions()])
