"""Asynchronous game-font loading; ordinary widget references own their lifetime."""
from graph import Graph, variable as v, KML, GS
from runtime import arr
from runtime_store import call, branch, combine
from runtime_world import ACTOR, set_value, validity
from runtime_apply import get, bump, clock
from runtime_session import method, prop
from runtime_assets import JOB
from runtime_editor_assets import UIROOT, BUS, FONT
from runtime_editor_host import PANELS, widget, widget_class

FONTS=[('TitleFont','Title_Font_TTFirsNeue'),('SecondaryFont','Secondary_Font_FSIndustrieCD'),('PrimaryFont','Primary_Font_FSIndustrie')]


def style_list():
    g=Graph();branch(g,'valid',validity(g,'listvalid','entry.List'))
    rows=call(g,'rows','/Script/UMG.ListViewBase:GetDisplayedEntryWidgets',{'self':'entry.List'})
    g.get('i','local:EntryIndex');arr(g,'len','Length',rows)
    branch(g,'loop',call(g,'within',KML+':Less_IntInt',{'A':'i.EntryIndex','B':'len.ReturnValue'}))
    arr(g,'item','Get',rows);g.wire(('i.EntryIndex','item.Index'))
    g.node('tile','cast',**{'class':UIROOT+'WBP_DenCatalogEntry'});g.wire(('item.Item','tile.Object'))
    call(g,'tilestyle',UIROOT+'WBP_DenCatalogEntry:ApplyNativeStyle',{'self':'tile.AsWBP Den Catalog Entry'})
    g.node('shelf','cast',**{'class':UIROOT+'WBP_DenCatalogShelf'});g.wire(('item.Item','shelf.Object'))
    call(g,'shelfstyle',UIROOT+'WBP_DenCatalogShelf:ApplyNativeStyle',{'self':'shelf.AsWBP Den Catalog Shelf'})
    g.node('chip','cast',**{'class':UIROOT+'WBP_DenCatalogChip'});g.wire(('item.Item','chip.Object'))
    call(g,'chipstyle',UIROOT+'WBP_DenCatalogChip:ApplyNativeStyle',{'self':'chip.AsWBP Den Catalog Chip'})
    set_value(g,'advance','local:EntryIndex',call(g,'next',KML+':Add_IntInt',{'A':'i.EntryIndex'},B=1))
    g.chain('entry','valid','loop','tile','tilestyle','advance','loop');g.chain('tile.CastFailed','shelf','shelfstyle','advance');g.chain('shelf.CastFailed','chip','chipstyle','advance');g.chain('chip.CastFailed','advance')
    return g.function('StyleEditorList',inputs=[v('List','object:/Script/UMG.ListViewBase')],locals=[v('EntryIndex','int','0')])


def style_panels():
    g=Graph();previous='entry'
    for var,cls,_ in PANELS:
        branch(g,var+'valid',validity(g,var+'check',get(g,var)));call(g,var+'style',UIROOT+cls+':ApplyNativeStyle',{'self':get(g,var)})
        g.node(var+'next','sequence',outputs=1);g.chain(previous,var+'valid',var+'style',var+'next');g.chain(var+'valid.else',var+'next');previous=var+'next.then_0'
    for i,(panel,field) in enumerate([('CatalogPanel','Shelves'),('CatalogPanel','Items'),('LayoutsPanel','Presets'),('CompositionsPanel','Compositions'),('StoreroomPanel','Stored'),('StoreroomPanel','Dormant')]):
        name='list'+str(i);branch(g,name+'valid',validity(g,name+'check',get(g,panel)))
        obj=widget(g,name+'widget',panel,field);g.call(name,'self:StyleEditorList');g.wire((obj,name+'.List'))
        g.node(name+'next','sequence',outputs=1);g.chain(previous,name+'valid',name,name+'next');g.chain(name+'valid.else',name+'next');previous=name+'next.then_0'
    return g.function('StyleEditorPanels')


def advance():
    g=Graph();branch(g,'valid',validity(g,'jobvalid',get(g,'FontJob')));call(g,'destroy',ACTOR+':K2_DestroyActor',{'self':get(g,'FontJob')})
    g.set('clear','FontJob');bump(g,'advance','FontIndex');g.call('style','self:StyleEditorPanels')
    g.chain('entry','valid','destroy','clear','advance','style');g.chain('valid.else','clear')
    return g.function('AdvanceEditorFont')


def poll():
    g=Graph();within=call(g,'within',KML+':Less_IntInt',{'A':get(g,'FontIndex')},B=3)
    branch(g,'ready',combine(g,'readycheck',[get(g,'UIOpen'),validity(g,'busvalid',get(g,'InputBus')),within]))
    branch(g,'pending',validity(g,'jobvalid',get(g,'FontJob')))
    done=prop(g,'done',JOB,'Done',get(g,'FontJob'));branch(g,'complete',done)
    result=prop(g,'result',JOB,'Result',get(g,'FontJob'));g.node('font','cast',**{'class':FONT});g.wire((result,'font.Object'))
    previous='font'
    for i,(field,_) in enumerate(FONTS):
        name='font'+str(i);branch(g,name,call(g,name+'index',KML+':EqualEqual_IntInt',{'A':get(g,'FontIndex')},B=i))
        set_value(g,name+'save',BUS+':'+field,'font.AsFont');g.wire((get(g,'InputBus'),name+'save.self'));g.chain(previous,name,name+'save');previous=name+'.else'
    g.call('advance','self:AdvanceEditorFont')
    for i in range(3):g.chain('font'+str(i)+'save','advance')
    g.chain('font.CastFailed','advance')
    elapsed=call(g,'elapsed',KML+':Subtract_DoubleDouble',{'A':clock(g,'now'),'B':get(g,'FontRequestAt')})
    branch(g,'expired',call(g,'timeout',KML+':GreaterEqual_DoubleDouble',{'A':elapsed},B=30))
    g.chain('complete.else','expired','advance')
    # One independent job at a time. Never reuse the world's PendingJob slot.
    previous='pending.else'
    for i,(_,asset) in enumerate(FONTS):
        name='path'+str(i);branch(g,name,call(g,name+'index',KML+':EqualEqual_IntInt',{'A':get(g,'FontIndex')},B=i))
        g.set(name+'save','local:FontPath','/Game/Game/UI/Fonts/'+asset+'.'+asset);g.chain(previous,name,name+'save');previous=name+'.else'
    g.node('self','self');xf=call(g,'identity',KML+':MakeTransform',Scale='1,1,1')
    pending=call(g,'spawn',GS+':BeginDeferredActorSpawnFromClass',{'WorldContextObject':'self.self','Owner':'self.self','SpawnTransform':xf},ActorClass=JOB,CollisionHandlingOverride='AlwaysSpawn')
    spawned=call(g,'finish',GS+':FinishSpawningActor',{'Actor':pending,'SpawnTransform':xf})
    g.node('cast','cast',**{'class':JOB});g.wire((spawned,'cast.Object'));set_value(g,'remember','FontJob','cast.AsBP Den Asset Job')
    g.get('path','local:FontPath');method(g,'request',JOB,'Request',get(g,'FontJob'),{'Path':'path.FontPath'});set_value(g,'time','FontRequestAt',clock(g,'started'))
    for i in range(3):g.chain('path'+str(i)+'save','spawn')
    g.chain('spawn','finish','cast','remember','request','time');g.chain('cast.CastFailed','advance')
    g.chain('entry','ready','pending','complete','font')
    return g.function('PollEditorFonts',locals=[v('FontPath','string')])


def functions():return [style_list(),style_panels(),advance(),poll()]
