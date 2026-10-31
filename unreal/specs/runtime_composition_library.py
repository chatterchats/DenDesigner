"""An isolated composition library using the existing rotating native store."""
from graph import Graph, variable as v, KML, GS
from runtime import LAYOUT, arr
from runtime_store import call, branch, combine, STR
from runtime_apply import get
from runtime_world import validity,set_value
from runtime_session import method
from runtime_layout_ui import PRESETS, LIBRARY
from runtime_editor_host import text,widget,WIDGET
from runtime_gizmo_controller import op,neg
from runtime_catalog_ui import prefix,number
import runtime_layout_ui as layout_ui


def adapt(value):
    """Reuse the proven listing/card freshness checks, retaining the external store API."""
    if isinstance(value,list):return [adapt(x) for x in value]
    if isinstance(value,dict):return {adapt(k):adapt(x) for k,x in value.items()}
    if not isinstance(value,str):return value
    if value.startswith((PRESETS,LIBRARY)):return value
    value=value.replace(PRESETS,'__PRESETS__').replace(LIBRARY,'__LIBRARY__').replace('self:ShowLayoutConfirmation','__CONFIRM__').replace('AsBP Den Presets','__SERVICE__')
    value=value.replace('RefreshLayoutPresets','RefreshCompositionLibrary').replace('RefreshLayoutFeedback','RefreshCompositionFeedback')
    return value.replace('Preset','Composition').replace('preset','composition').replace('Layouts','Compositions').replace('layouts','compositions').replace('Layout','Composition').replace('__SERVICE__','AsBP Den Presets').replace('__PRESETS__',PRESETS).replace('__LIBRARY__',LIBRARY).replace('__CONFIRM__','self:ShowLayoutConfirmation')


def feedback():
    g=Graph();branch(g,'valid',validity(g,'panel',get(g,'CompositionsPanel')))
    arr(g,'count','Length',get(g,'CompositionParts'));suffix=call(g,'suffix',KML+':SelectString',{'bPickA':op(g,'single','EqualEqual_IntInt','count.ReturnValue',B=1)},A=' part selected',B=' parts selected');caption=call(g,'caption',STR+'Concat_StrStr',{'A':number(g,'number','count.ReturnValue'),'B':suffix})
    text(g,'counttext','CompositionsPanel','SelectionCount',value=caption);text(g,'message','CompositionsPanel','Footer',value=get(g,'CompositionMessage'))
    label=call(g,'label',KML+':SelectString',{'bPickA':get(g,'CompositionSelecting')},A='Finish selecting',B='Select parts');text(g,'selecttext','CompositionsPanel','SelectPartsLabel',value=label)
    selected=call(g,'selected',STR+'NotEqual_StrStr',{'A':get(g,'SelectedComposition')},B='');g.call('ready','self:CanEdit')
    enabled=combine(g,'enabled',['ready.Ready',selected,op(g,'healthy','LessEqual_IntInt',get(g,'CompositionListStatus'),B=2)])
    previous='selecttext'
    for field in ['LoadComposition','DeleteComposition']:
        call(g,field,WIDGET+':SetIsEnabled',{'self':widget(g,field+'widget','CompositionsPanel',field),'bInIsEnabled':enabled});g.chain(previous,field);previous=field
    g.chain('entry','valid','ready','counttext','message','selecttext');return g.function('RefreshCompositionFeedback')


def changed():
    g=Graph();branch(g,'active',call(g,'same',STR+'EqualEqual_StrStr',{'A':get(g,'ActivePanel')},B='compositions'));g.call('refresh','self:RefreshCompositionLibrary');g.chain('entry','active','refresh');return g.function('CompositionsPanelChanged')


def save(replace=False):
    g=Graph();g.call('ready','self:CanEdit');branch(g,'available',combine(g,'availablecheck',[get(g,'UIOpen'),'ready.Ready']))
    g.call('ensure','self:EnsureCompositionService');g.call('current','self:CompositionLibraryCurrent');branch(g,'fresh','current.Accepted')
    if not replace:
        g.call('capture','self:CaptureComposition');branch(g,'captured','capture.Ready');set_value(g,'remember','PendingCompositionDocument','capture.Document')
        method(g,'normalize',PRESETS,'NormalizeName',get(g,'CompositionService'),{'Name':'entry.Name'});branch(g,'validname','normalize.Valid')
        arr(g,'exists','Contains',get(g,'CompositionNames'));g.wire(('normalize.CleanName','exists.ItemToFind'));branch(g,'existing','exists.ReturnValue')
        set_value(g,'name','PendingCompositionName','normalize.CleanName');g.call('confirm','self:ShowLayoutConfirmation',Action='replace_composition',Title='Replace this composition?',Button='Replace');g.wire(('normalize.CleanName','confirm.Name'),(prefix(g,'message','Replace the saved composition: ','normalize.CleanName'),'confirm.Message'))
        g.call('write','self:WriteCapturedComposition');g.chain('fresh','capture','captured','remember','normalize','validname','name','existing','confirm');g.chain('existing.else','write')
        g.set('missing','CompositionMessage','Select at least one editable part. Changed, unavailable or protected parts must be selected again.');g.set('badname','CompositionMessage','Use a composition name of 1–40 characters.');g.call('labels','self:RefreshCompositionFeedback');g.chain('captured.else','missing','labels');g.chain('validname.else','badname','labels')
    else:
        branch(g,'document',validity(g,'validdocument',get(g,'PendingCompositionDocument')))
        method(g,'save',PRESETS,'SavePreset',get(g,'CompositionService'),{'Name':get(g,'PendingCompositionName'),'Document':get(g,'PendingCompositionDocument')});branch(g,'saved',op(g,'success','EqualEqual_IntInt','save.Status',B=1))
        set_value(g,'selected','SelectedComposition','save.CleanName');g.set('done','CompositionMessage','Composition saved. The original parts have not changed.');g.set('release','PendingCompositionDocument');g.call('refresh','self:RefreshCompositionLibrary')
        g.set('error','CompositionMessage','Composition could not be saved. Existing library files have been kept.');g.call('labels','self:RefreshCompositionFeedback')
        g.chain('fresh','document','save','saved','selected','done','release','refresh');g.chain('saved.else','error','labels')
    g.chain('entry','ready','available','ensure','current','fresh')
    return g.function('WriteCapturedComposition' if replace else 'SaveEditorComposition',inputs=[] if replace else [v('Name','string')])


def variables():
    return [adapt(x) for x in layout_ui.variables() if x['name'] not in ['PendingLayoutAction','PendingLayoutName','PendingLayoutVersion','PendingLayoutGeneration']]+[v('PendingCompositionDocument','object:'+LAYOUT),v('PendingCompositionName','string')]

def refresh():
    spec=adapt(layout_ui.refresh())
    spec['nodes'].append(dict(id='decorate',kind='call',function='self:DecorateCompositionCard'))
    spec['links'].remove(['item.then','keep.execute'])
    spec['links'] += [['item.then','decorate.execute'],['decorate.then','keep.execute'],['item.Item','decorate.Item'],['name.Item','decorate.Name'],['open.Library','decorate.Library']]
    # The same safe placeholder used by Catalog/Storeroom is replaced when ready.
    next(n for n in spec['nodes'] if n['id']=='item').setdefault('defaults',{})['Preview']='Preview unavailable'
    return spec


def ensure():
    """EnsurePresetService for compositions; a new service first adopts old imports' codes (AdoptShareCodes)."""
    g=Graph();branch(g,'exists',validity(g,'valid',get(g,'CompositionService')));g.node('self','self')
    obj=call(g,'create',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=PRESETS);g.node('cast','cast',**{'class':PRESETS});g.wire((obj,'cast.Object'));set_value(g,'remember','CompositionService','cast.AsBP Den Presets')
    for name in ['key','newkey']:
        set_value(g,name,PRESETS+':LibraryKey',get(g,'CompositionStorageKey'));g.wire((get(g,'CompositionService'),name+'.self'))
    method(g,'adopt',PRESETS,'AdoptShareCodes',get(g,'CompositionService'))
    g.chain('entry','exists','key');g.chain('exists.else','create','cast','remember','newkey','adopt');return g.function('EnsureCompositionService')


def functions():
    from runtime_composition_thumbnails import decorate
    return [ensure()]+[adapt(fn()) for fn in [layout_ui.read_key,layout_ui.select,layout_ui.library_current,layout_ui.delete,layout_ui.request_delete,layout_ui.queue,layout_ui.run_action]]+[refresh(),decorate(),feedback(),changed(),save(),save(True)]
