"""Visible catalog/Storeroom tiles share one native thumbnail service.

Requests contain mesh paths only, never recycled widget references. Delivery
updates whichever item is actually assigned to the visible tile at that moment.
"""
from graph import Graph, variable as v, KML, GS
from runtime import arr
from runtime_store import call, branch, combine, STR
from runtime_world import ACTOR, validity, set_value
from runtime_apply import get
from runtime_session import prop, method
from runtime_gizmo_controller import op
from runtime_editor_assets import UIROOT
from runtime_editor_host import widget
from runtime_thumbnail_queue import QUEUE, spawn
from runtime_thumbnails import TEXTURE

ITEM=UIROOT+'BP_DenCatalogItem'
TILE=UIROOT+'WBP_DenCatalogEntry'
LIST='/Script/UMG.ListViewBase'
WIDGET='/Script/UMG.Widget'


def refresh_tile():
    g=Graph();branch(g,'item',validity(g,'itemvalid',get(g,'NativeItem')))
    texture=prop(g,'texture',ITEM,'Thumb',get(g,'NativeItem'));branch(g,'valid',validity(g,'texturevalid',texture))
    call(g,'brush','/Script/UMG.Image:SetBrushFromTexture',{'self':get(g,'Picture'),'Texture':texture},bMatchSize='false')
    call(g,'show',WIDGET+':SetVisibility',{'self':get(g,'Picture')},InVisibility='Visible');call(g,'hide',WIDGET+':SetVisibility',{'self':get(g,'Placeholder')},InVisibility='Hidden')
    g.chain('entry','item','valid','brush','show','hide');return g.function('RefreshNativeThumbnail')


def ensure():
    g=Graph();g.node('self','self');branch(g,'valid',validity(g,'alive',get(g,'ThumbnailWorker')));spawn(g,'worker',QUEUE,'ThumbnailWorker','AsBP Den Thumbnails');set_value(g,'enabled',QUEUE+':Enabled',get(g,'ThumbnailsEnabled'));g.wire((get(g,'ThumbnailWorker'),'enabled.self'));g.chain('entry','valid','enabled');g.chain('valid.else','workerspawn');g.chain('workersave','enabled');return g.function('EnsureThumbnailWorker')


def cancel():
    g=Graph();branch(g,'valid',validity(g,'alive',get(g,'ThumbnailWorker')));method(g,'cancel',QUEUE,'CancelPending',get(g,'ThumbnailWorker'));g.set('cursor','ThumbnailCursor','0');g.chain('entry','valid','cancel','cursor');g.chain('valid.else','cursor');return g.function('CancelThumbnailRequests')


def release():
    g=Graph();branch(g,'valid',validity(g,'alive',get(g,'ThumbnailWorker')));call(g,'destroy',ACTOR+':K2_DestroyActor',{'self':get(g,'ThumbnailWorker')});g.set('clear','ThumbnailWorker');g.chain('entry','valid','destroy','clear');g.chain('valid.else','clear');return g.function('ReleaseThumbnails')


def poll():
    g=Graph();branch(g,'open',get(g,'UIOpen'))
    branch(g,'catalog',call(g,'iscatalog',STR+'EqualEqual_StrStr',{'A':get(g,'ActivePanel')},B='catalog'));branch(g,'catalogvalid',validity(g,'cpvalid',get(g,'CatalogPanel')))
    set_value(g,'cataloglist','local:ThumbnailList',widget(g,'catalogitems','CatalogPanel','Items'))
    branch(g,'stored',call(g,'isstored',STR+'EqualEqual_StrStr',{'A':get(g,'ActivePanel')},B='storeroom'));branch(g,'storedvalid',validity(g,'spvalid',get(g,'StoreroomPanel')))
    set_value(g,'storedlist','local:ThumbnailList',widget(g,'storeditems','StoreroomPanel','Stored'));g.get('list','local:ThumbnailList')
    branch(g,'compositions',call(g,'iscompositions',STR+'EqualEqual_StrStr',{'A':get(g,'ActivePanel')},B='compositions'));branch(g,'compositionsvalid',validity(g,'covvalid',get(g,'CompositionsPanel')));set_value(g,'compositionslist','local:ThumbnailList',widget(g,'compositionitems','CompositionsPanel','Compositions'))
    g.call('ensure','self:EnsureThumbnailWorker');branch(g,'worker',validity(g,'workervalid',get(g,'ThumbnailWorker')))
    rows=call(g,'rows',LIST+':GetDisplayedEntryWidgets',{'self':'list.ThumbnailList'});arr(g,'count','Length',rows)
    branch(g,'wrap',op(g,'beyond','GreaterEqual_IntInt',get(g,'ThumbnailCursor'),'count.ReturnValue'));g.set('reset','ThumbnailCursor','0')
    g.get('steps','local:Steps');branch(g,'loop',combine(g,'bounded',[op(g,'within','Less_IntInt',get(g,'ThumbnailCursor'),'count.ReturnValue'),op(g,'budget','Less_IntInt','steps.Steps',B=8)]))
    arr(g,'row','Get',rows);g.wire((get(g,'ThumbnailCursor'),'row.Index'));g.node('tile','cast',**{'class':TILE});g.wire(('row.Item','tile.Object'))
    item=prop(g,'item',TILE,'NativeItem','tile.AsWBP Den Catalog Entry');branch(g,'itemvalid',validity(g,'hasitem',item));path=prop(g,'path',ITEM,'AssetPath',item)
    document=prop(g,'document',ITEM,'ThumbnailDocument',item);branch(g,'composition',validity(g,'documentvalid',document));method(g,'requestcomposition',QUEUE,'RequestComposition',get(g,'ThumbnailWorker'),{'Path':path,'Document':document});set_value(g,'compositiontexture','local:RequestedTexture','requestcomposition.Texture')
    method(g,'request',QUEUE,'Request',get(g,'ThumbnailWorker'),{'Path':path});set_value(g,'meshtexture','local:RequestedTexture','request.Texture');g.get('requested','local:RequestedTexture');branch(g,'texture',validity(g,'ready','requested.RequestedTexture'))
    current=prop(g,'current',ITEM,'Thumb',item);branch(g,'changed',call(g,'different',KML+':NotEqual_ObjectObject',{'A':current,'B':'requested.RequestedTexture'}));set_value(g,'assign',ITEM+':Thumb','requested.RequestedTexture');g.wire((item,'assign.self'));method(g,'refresh',TILE,'RefreshNativeThumbnail','tile.AsWBP Den Catalog Entry')
    set_value(g,'next','ThumbnailCursor',op(g,'increment','Add_IntInt',get(g,'ThumbnailCursor'),B=1));set_value(g,'step','local:Steps',op(g,'stepnext','Add_IntInt','steps.Steps',B=1))
    g.chain('entry','open','catalog','catalogvalid','cataloglist','ensure','worker','wrap','reset','loop','tile','itemvalid','composition','requestcomposition','compositiontexture','texture','changed','assign','refresh','next','step','loop');g.chain('catalog.else','stored','storedvalid','storedlist','ensure');g.chain('wrap.else','loop');g.chain('stored.else','compositions','compositionsvalid','compositionslist','ensure');g.chain('composition.else','request','meshtexture','texture')
    for pin in ['tile.CastFailed','itemvalid.else','texture.else','changed.else']:g.chain(pin,'next')
    return g.function('PollThumbnailUI',locals=[v('ThumbnailList','object:'+LIST),v('Steps','int','0'),v('RequestedTexture','object:'+TEXTURE)])


def variables():return [v('ThumbnailWorker','object:'+QUEUE),v('ThumbnailCursor','int','0')]
def functions():return [ensure(),cancel(),release(),poll()]
