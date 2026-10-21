"""Native catalog navigation and incremental ListView item population."""
from graph import Graph, variable as v, KML, GS
from runtime import arr
from runtime_store import call, branch, combine, STR
from runtime_world import set_value, validity
from runtime_session import prop, method
from runtime_apply import get, clear, bump, clock
from runtime_gizmo_controller import op, neg
from runtime_catalog import CATALOG, DATA, metadata
from runtime_editor_assets import UIROOT
from runtime_editor_host import widget, text

ITEM=UIROOT+'BP_DenCatalogItem'
LIST='/Script/UMG.ListView'
BOX='/Script/UMG.EditableTextBox'
DEFAULT_SHELF=next(i for i,s in enumerate(metadata()['shelves'],1) if s['collection']=='Den')


def cp(g,field):
    name='provider'+field
    if any(n['id']==name for n in g.nodes):return name+'.'+field
    return prop(g,name,CATALOG,field,get(g,'CatalogProvider'))


def data(g,field):
    name='data'+field
    if any(n['id']==name for n in g.nodes):return name+'.'+field
    return prop(g,name,DATA,field,cp(g,'Data'))


def number(g,name,value):return call(g,name,STR+'Conv_IntToString',{'InInt':value})
def join(g,name,a,b):return call(g,name,STR+'Concat_StrStr',{'A':a,'B':b})
def prefix(g,name,label,value):return call(g,name,STR+'Concat_StrStr',{'B':value},A=label)
def open_check(g):return combine(g,'opencheck',[get(g,'UIOpen'),call(g,'catalogactive',STR+'EqualEqual_StrStr',{'A':get(g,'ActivePanel')},B='catalog')])


def ensure():
    g=Graph();branch(g,'exists',validity(g,'valid',get(g,'CatalogProvider')));g.node('self','self')
    obj=call(g,'create',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=CATALOG);g.node('cast','cast',**{'class':CATALOG});g.wire((obj,'cast.Object'));set_value(g,'save','CatalogProvider','cast.AsBP Den Catalog')
    method(g,'init',CATALOG,'Initialize',get(g,'CatalogProvider'))
    method(g,'packs',CATALOG,'DiscoverPropPacks',get(g,'CatalogProvider'),{'Context':'self.self'})
    g.call('restore','self:RestoreCatalogRecents')
    g.chain('entry','exists');g.chain('exists.else','create','cast','save','init','packs','restore');return g.function('EnsureCatalog')


def new_item():
    g=Graph();g.node('self','self');obj=call(g,'create',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=ITEM)
    g.node('cast','cast',**{'class':ITEM});g.wire((obj,'cast.Object'));previous='cast'
    for field in ['Key','Title','Detail','Preview','AssetPath','EditorBus']:
        set_value(g,'set'+field,ITEM+':'+field,get(g,'InputBus') if field=='EditorBus' else 'entry.'+field);g.wire(('cast.AsBP Den Catalog Item','set'+field+'.self'));g.chain(previous,'set'+field);previous='set'+field
    set_value(g,'out','local:CreatedItem','cast.AsBP Den Catalog Item');g.get('resultitem','local:CreatedItem');g.wire(('resultitem.CreatedItem','result.Item'))
    g.chain('entry','create','cast');g.chain(previous,'out','result');g.chain('cast.CastFailed','result')
    return g.function('NewCatalogItem',inputs=[v(n,'string') for n in ['Key','Title','Detail','Preview','AssetPath']],outputs=[v('Item','object:'+ITEM)],locals=[v('CreatedItem','object:'+ITEM)])


def add_shelf():
    g=Graph();g.call('item','self:NewCatalogItem');g.wire(('entry.Key','item.Key'),('entry.Title','item.Title'));branch(g,'valid',validity(g,'itemvalid','item.Item'));arr(g,'keep','Add',get(g,'CatalogShelves'));g.wire(('item.Item','keep.NewItem'))
    branch(g,'panel',validity(g,'panelvalid',get(g,'CatalogPanel')));call(g,'add',LIST+':AddItem',{'self':widget(g,'view','CatalogPanel','Shelves'),'Item':'item.Item'})
    g.chain('entry','item','valid','keep','panel','add');return g.function('AddCatalogShelfRow',inputs=[v('Key','string'),v('Title','string')])


def shelves():
    g=Graph();clear(g,'rows','CatalogShelves');branch(g,'panel',validity(g,'panelvalid',get(g,'CatalogPanel')));call(g,'clear',LIST+':ClearListItems',{'self':widget(g,'view','CatalogPanel','Shelves')})
    g.call('recent','self:AddCatalogShelfRow',Key='recent',Title='Recently used')
    arr(g,'groups','Length',data(g,'Groups'));branch(g,'group',combine(g,'groupcheck',[op(g,'positive','GreaterEqual_IntInt',get(g,'CatalogGroup'),B=0),op(g,'max','Less_IntInt',get(g,'CatalogGroup'),'groups.ReturnValue')]))
    g.call('back','self:AddCatalogShelfRow',Key='collections',Title='‹ All collections')
    arr(g,'shelves','Length',data(g,'ShelfLabels'));g.get('index','local:Cursor');branch(g,'shelfloop',op(g,'shelfwithin','Less_IntInt','index.Cursor','shelves.ReturnValue'))
    arr(g,'owner','Get',data(g,'ShelfGroups'));g.wire(('index.Cursor','owner.Index'));branch(g,'belongs',op(g,'same','EqualEqual_IntInt','owner.Item',get(g,'CatalogGroup')))
    for name,field in [('label','ShelfLabels'),('count','ShelfCounts')]:arr(g,name,'Get',data(g,field));g.wire(('index.Cursor',name+'.Index'))
    title=join(g,'title','label.Item',prefix(g,'separator',' · ',number(g,'countstr','count.Item')))
    key=number(g,'key',op(g,'onebased','Add_IntInt','index.Cursor',B=1));g.call('row','self:AddCatalogShelfRow');g.wire((key,'row.Key'),(title,'row.Title'))
    set_value(g,'next','local:Cursor',op(g,'increment','Add_IntInt','index.Cursor',B=1))
    branch(g,'grouploop',op(g,'groupwithin','Less_IntInt','index.Cursor','groups.ReturnValue'))
    for name,field in [('grouplabel','Groups'),('groupcount','GroupCounts')]:arr(g,name,'Get',data(g,field));g.wire(('index.Cursor',name+'.Index'))
    grouptitle=join(g,'grouptitle','grouplabel.Item',prefix(g,'groupsep',' · ',number(g,'groupcountstr','groupcount.Item')))
    groupkey=prefix(g,'groupkey','group:',number(g,'groupindex','index.Cursor'));g.call('grouprow','self:AddCatalogShelfRow');g.wire((groupkey,'grouprow.Key'),(grouptitle,'grouprow.Title'))
    set_value(g,'nextgroup','local:Cursor',op(g,'incrementgroup','Add_IntInt','index.Cursor',B=1))
    g.chain('entry','rows','panel','clear','recent','group','back','shelfloop','belongs','row','next','shelfloop');g.chain('panel.else','recent');g.chain('belongs.else','next');g.chain('group.else','grouploop','grouprow','nextgroup','grouploop')
    return g.function('RefreshCatalogShelves',locals=[v('Cursor','int','0')])


def clear_items():
    g=Graph();g.call('thumbs','self:CancelThumbnailRequests');g.set('stop','CatalogRendering','false');g.set('cursor','CatalogRenderCursor','0');g.set('revision','CatalogRenderRevision','-1');clear(g,'rows','CatalogItems')
    branch(g,'panel',validity(g,'panelvalid',get(g,'CatalogPanel')));call(g,'clear',LIST+':ClearListItems',{'self':widget(g,'view','CatalogPanel','Items')});g.chain('entry','thumbs','stop','cursor','revision','rows','panel','clear');return g.function('ClearCatalogItems')


def query():
    g=Graph();g.call('clear','self:ClearCatalogItems');branch(g,'provider',validity(g,'providervalid',get(g,'CatalogProvider')))
    trimmed=call(g,'trim',STR+'Trim',{'SourceString':get(g,'CatalogQuery')});trimmed=call(g,'trailing',STR+'TrimTrailing',{'SourceString':trimmed})
    branch(g,'search',call(g,'nonempty',STR+'NotEqual_StrStr',{'A':trimmed},B=''))
    method(g,'searchquery',CATALOG,'Search',get(g,'CatalogProvider'),{'Text':get(g,'CatalogQuery')});method(g,'browse',CATALOG,'Browse',get(g,'CatalogProvider'),{'Shelf':get(g,'CatalogShelf')})
    branch(g,'panel',validity(g,'panelvalid',get(g,'CatalogPanel')));text(g,'waiting','CatalogPanel','Empty',constant='Finding props…');text(g,'footer','CatalogPanel','Footer',constant='Choose a prop, then click in the Den to place it.')
    g.chain('entry','clear','provider','search','searchquery','panel','waiting','footer');g.chain('search.else','browse','panel');return g.function('StartCatalogQuery')


def panel_changed():
    g=Graph();branch(g,'open',open_check(g));g.call('ensure','self:EnsureCatalog');g.call('shelves','self:RefreshCatalogShelves');g.call('query','self:StartCatalogQuery')
    branch(g,'provider',validity(g,'valid',get(g,'CatalogProvider')));method(g,'cancel',CATALOG,'Cancel',get(g,'CatalogProvider'));g.call('clear','self:ClearCatalogItems')
    g.chain('entry','open','ensure','shelves','query');g.chain('open.else','provider','cancel','clear');g.chain('provider.else','clear');return g.function('CatalogPanelChanged')


def search():
    g=Graph();branch(g,'open',open_check(g));set_value(g,'query','CatalogQuery','entry.Text');g.call('start','self:StartCatalogQuery');g.chain('entry','open','query','start')
    return g.function('SearchCatalog',inputs=[v('Text','string')])


def choose_shelf():
    g=Graph();branch(g,'open',open_check(g));branch(g,'collections',call(g,'all',STR+'EqualEqual_StrStr',{'A':'entry.Key'},B='collections'))
    g.set('root','CatalogGroup','-1');g.call('refresh','self:RefreshCatalogShelves')
    branch(g,'recent',call(g,'isrecent',STR+'EqualEqual_StrStr',{'A':'entry.Key'},B='recent'));g.set('recentkey','CatalogShelf','-1')
    prefix_=call(g,'prefix',STR+'StartsWith',{'SourceString':'entry.Key'},InPrefix='group:');branch(g,'group',prefix_)
    suffix=call(g,'suffix',STR+'RightChop',{'SourceString':'entry.Key'},Count=6)
    group=call(g,'groupnumber',STR+'Conv_StringToInt',{'InString':suffix});arr(g,'groups','Length',data(g,'Groups'))
    # Exact round trip rejects malformed strings that Conv_StringToInt accepts.
    validgroup=combine(g,'groupcheck',[op(g,'groupmin','GreaterEqual_IntInt',group,B=0),op(g,'groupmax','Less_IntInt',group,'groups.ReturnValue'),call(g,'groupexact',STR+'EqualEqual_StrStr',{'A':suffix,'B':number(g,'grouptext',group)})]);branch(g,'validgroup',validgroup)
    set_value(g,'savegroup','CatalogGroup',group);arr(g,'first','Find',data(g,'ShelfGroups'));g.wire((group,'first.ItemToFind'));branch(g,'found',op(g,'foundcheck','GreaterEqual_IntInt','first.ReturnValue',B=0));set_value(g,'firstshelf','CatalogShelf',op(g,'firstid','Add_IntInt','first.ReturnValue',B=1));g.call('shelves','self:RefreshCatalogShelves')
    shelf=call(g,'shelfnumber',STR+'Conv_StringToInt',{'InString':'entry.Key'});arr(g,'count','Length',data(g,'ShelfLabels'))
    validshelf=combine(g,'shelfcheck',[op(g,'min','GreaterEqual_IntInt',shelf,B=1),op(g,'max','LessEqual_IntInt',shelf,'count.ReturnValue'),call(g,'exact',STR+'EqualEqual_StrStr',{'A':'entry.Key','B':number(g,'shelftext',shelf)})]);branch(g,'validshelf',validshelf);set_value(g,'saveshelf','CatalogShelf',shelf)
    g.set('clearquery','CatalogQuery','');branch(g,'panel',validity(g,'panelvalid',get(g,'CatalogPanel')));call(g,'cleartext',BOX+':SetText',{'self':widget(g,'box','CatalogPanel','Search')},InText='');g.call('start','self:StartCatalogQuery')
    g.chain('entry','open','collections','root','refresh');g.chain('collections.else','recent','recentkey','clearquery','panel','cleartext','start');g.chain('panel.else','start')
    g.chain('recent.else','group','validgroup','savegroup','found','firstshelf','shelves','clearquery');g.chain('group.else','validshelf','saveshelf','clearquery')
    return g.function('ChooseCatalogShelf',inputs=[v('Key','string')])


def render_step():
    g=Graph();arr(g,'len','Length',cp(g,'Results'));branch(g,'more',op(g,'within','Less_IntInt',get(g,'CatalogRenderCursor'),'len.ReturnValue'))
    arr(g,'index','Get',cp(g,'Results'));g.wire((get(g,'CatalogRenderCursor'),'index.Index'));method(g,'read',CATALOG,'ReadItem',get(g,'CatalogProvider'),{'Index':'index.Item'});branch(g,'found','read.Found')
    key=join(g,'key',number(g,'revision',cp(g,'Revision')),prefix(g,'indexkey',':',number(g,'indextext','index.Item')))
    g.call('create','self:NewCatalogItem',Preview='Preview unavailable');g.wire((key,'create.Key'),('read.Label','create.Title'),('read.Detail','create.Detail'),('read.Path','create.AssetPath'))
    arr(g,'keep','Add',get(g,'CatalogItems'));g.wire(('create.Item','keep.NewItem'));branch(g,'panel',validity(g,'panelvalid',get(g,'CatalogPanel')));call(g,'add',LIST+':AddItem',{'self':widget(g,'view','CatalogPanel','Items'),'Item':'create.Item'})
    bump(g,'next','CatalogRenderCursor');g.set('stop','CatalogRendering','false');g.chain('entry','more','read','found','create','keep','panel','add','next');g.chain('found.else','next');g.chain('panel.else','next');g.chain('more.else','stop')
    return g.function('RenderCatalogStep')


def labels():
    g=Graph();branch(g,'panel',validity(g,'panelvalid',get(g,'CatalogPanel')));arr(g,'len','Length',get(g,'CatalogItems'))
    branch(g,'empty',op(g,'zero','EqualEqual_IntInt','len.ReturnValue',B=0));text(g,'none','CatalogPanel','Empty',constant='No props found. Try another collection or search.');text(g,'clear','CatalogPanel','Empty',constant='')
    title=join(g,'counts',number(g,'total',cp(g,'MatchCount')),prefix(g,'shown',' props · Showing ',number(g,'visible','len.ReturnValue')))
    caption=call(g,'caption',STR+'Concat_StrStr',{'A':title},B='\nChoose a prop, then click in the Den to place it.')
    text(g,'footer','CatalogPanel','Footer',value=caption)
    arr(g,'issues','Length',cp(g,'PackIssues'));branch(g,'hasissues',op(g,'anyissues','Greater_IntInt','issues.ReturnValue',B=0));arr(g,'firstissue','Get',cp(g,'PackIssues'),Index=0)
    diagnostic=join(g,'diagnostic',caption,prefix(g,'issueline','\n','firstissue.Item'));text(g,'issuefooter','CatalogPanel','Footer',value=diagnostic)
    g.chain('entry','panel','empty','none','footer','hasissues','issuefooter');g.chain('empty.else','clear','footer');return g.function('RefreshCatalogLabels')


def poll():
    g=Graph();branch(g,'open',open_check(g));branch(g,'provider',validity(g,'valid',get(g,'CatalogProvider')));method(g,'pump',CATALOG,'Pump',get(g,'CatalogProvider'));branch(g,'ready',cp(g,'Ready'))
    branch(g,'revision',op(g,'changed','NotEqual_IntInt',get(g,'CatalogRenderRevision'),cp(g,'Revision')));set_value(g,'remember','CatalogRenderRevision',cp(g,'Revision'));g.set('cursor','CatalogRenderCursor','0');g.set('render','CatalogRendering','true')
    branch(g,'rendering',get(g,'CatalogRendering'));set_value(g,'start','local:CatalogBatchStarted',clock(g,'clock'));g.get('started','local:CatalogBatchStarted');g.get('steps','local:Steps')
    elapsed=op(g,'elapsed','Subtract_DoubleDouble',clock(g,'now'),'started.CatalogBatchStarted')
    branch(g,'loop',combine(g,'budget',[get(g,'CatalogRendering'),op(g,'time','Less_DoubleDouble',elapsed,B=.003),op(g,'limit','Less_IntInt','steps.Steps',B=8)]))
    g.call('step','self:RenderCatalogStep');set_value(g,'next','local:Steps',op(g,'increment','Add_IntInt','steps.Steps',B=1));branch(g,'done',neg(g,'finished',get(g,'CatalogRendering')));g.call('labels','self:RefreshCatalogLabels')
    branch(g,'loading',cp(g,'PacksLoading'));method(g,'packpump',CATALOG,'PumpPropPacks',get(g,'CatalogProvider'));branch(g,'loaded',neg(g,'packdone',cp(g,'PacksLoading')));g.call('packshelves','self:RefreshCatalogShelves');g.call('packquery','self:StartCatalogQuery');g.call('packrecents','self:RestoreCatalogRecents')
    text(g,'packloading','CatalogPanel','Empty',constant='Loading prop packs…')
    g.chain('entry','open','provider','loading','packloading','packpump','loaded','packrecents','packshelves','packquery');g.chain('loading.else','pump');g.chain('pump','ready','revision','remember','cursor','render','rendering','start','loop','step','next','loop');g.chain('revision.else','rendering');g.chain('loop.else','done','labels');return g.function('PollCatalogUI',locals=[v('CatalogBatchStarted','double'),v('Steps','int','0')])


def release():
    g=Graph();branch(g,'provider',validity(g,'valid',get(g,'CatalogProvider')));method(g,'cancel',CATALOG,'Cancel',get(g,'CatalogProvider'));g.call('clear','self:ClearCatalogItems');clear(g,'shelves','CatalogShelves');g.set('drop','CatalogProvider')
    g.chain('entry','provider','cancel','clear','shelves','drop');g.chain('provider.else','clear');return g.function('ReleaseCatalog')


def variables():return [v('CatalogProvider','object:'+CATALOG),v('CatalogItems','object:'+ITEM+'[]'),v('CatalogShelves','object:'+ITEM+'[]'),v('CatalogGroup','int','0'),v('CatalogShelf','int',str(DEFAULT_SHELF)),v('CatalogQuery','string'),v('CatalogRenderRevision','int','-1'),v('CatalogRenderCursor','int'),v('CatalogRendering','bool')]
def functions():return [ensure(),new_item(),add_shelf(),shelves(),clear_items(),query(),panel_changed(),search(),choose_shelf(),render_step(),labels(),poll(),release()]
