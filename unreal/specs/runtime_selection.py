"""Native editor selection lifecycle; no blocking loads."""
from graph import Graph, variable as v, KML, GS
from runtime import unpack
from runtime_store import call, branch, combine, STR
from runtime_world import PRIMITIVE, set_value, validity
from runtime_session import prop, method
from runtime_apply import get
from runtime_pick import PICKER, FACT
from runtime_editor_host import PC, widget, text, visibility


def initialize():
    g=Graph();g.node('self','self');g.call('clear','self:ClearSelection')
    obj=call(g,'create',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=PICKER)
    g.node('cast','cast',**{'class':PICKER});g.wire((obj,'cast.Object'));set_value(g,'save','Picker','cast.AsBP Den Picker')
    method(g,'index',PICKER,'BeginIndex',get(g,'Picker'),{'WorldManager':'self.self'})
    g.set('busy','SelectionWasBusy','false');set_value(g,'generation','SelectionGeneration',get(g,'Generation'));g.chain('entry','clear','create','cast','save','index','busy','generation')
    return g.function('InitializeSelection')


def clear_selection():
    g=Graph();unpack(g,'selected',FACT,get(g,'Selected'))
    g.call('dragcancel','self:EndSelectionDrag',Commit='false')
    branch(g,'valid',validity(g,'check','selected.Component'))
    call(g,'depth',PRIMITIVE+':SetRenderCustomDepth',{'self':'selected.Component','bValue':get(g,'SelectedHadDepth')})
    call(g,'stencil',PRIMITIVE+':SetCustomDepthStencilValue',{'self':'selected.Component','Value':get(g,'SelectedStencil')})
    g.set('clear','Selected');g.set('flag','HasSelection','false');g.set('reason','SelectionMessage','')
    branch(g,'picker',validity(g,'pickervalid',get(g,'Picker')));method(g,'cancel',PICKER,'CancelQuery',get(g,'Picker'))
    g.call('ui','self:RefreshSelectionUI')
    g.chain('entry','dragcancel','valid','depth','stencil','clear','flag','reason','picker','cancel','ui');g.chain('valid.else','clear');g.chain('picker.else','ui')
    return g.function('ClearSelection')


def accept():
    g=Graph();g.call('clear','self:ClearSelection');unpack(g,'facts',FACT,'entry.Facts')
    branch(g,'allowed',combine(g,'usable',['facts.Allowed',validity(g,'valid','facts.Component')]))
    branch(g,'vanilla',call(g,'native',KML+':EqualEqual_IntInt',{'A':'facts.Kind'},B=2))
    g.call('bind','self:BindVanilla');g.wire(('facts.Key','bind.Key'),('facts.Target','bind.Object'));branch(g,'bound','bind.Accepted')
    set_value(g,'save','Selected','entry.Facts')
    set_value(g,'olddepth','SelectedHadDepth',prop(g,'depth',PRIMITIVE,'bRenderCustomDepth','facts.Component'))
    set_value(g,'oldstencil','SelectedStencil',prop(g,'stencil',PRIMITIVE,'CustomDepthStencilValue','facts.Component'))
    call(g,'outline',PRIMITIVE+':SetCustomDepthStencilValue',{'self':'facts.Component'},Value=32)
    call(g,'enable',PRIMITIVE+':SetRenderCustomDepth',{'self':'facts.Component'},bValue='true')
    set_value(g,'generation','SelectionGeneration',get(g,'Generation'));g.set('selected','HasSelection','true');set_value(g,'reason','SelectionMessage','facts.Reason');g.set('bindingfailure','SelectionMessage','This object changed while selecting it. Try selecting it again.')
    g.call('ui','self:RefreshSelectionUI');g.call('toolbar','self:RefreshEditorUI')
    g.chain('entry','clear','allowed','vanilla','bind','bound','save','olddepth','oldstencil','outline','enable','selected','generation','ui','toolbar')
    g.chain('vanilla.else','save');g.chain('allowed.else','reason','ui');g.chain('bound.else','bindingfailure','ui')
    return g.function('AcceptSelection',inputs=[v('Facts','struct:'+FACT)])


def request():
    g=Graph();g.call('ready','self:CanEdit')
    pressed=call(g,'pressed',KML+':Greater_DoubleDouble',{'A':'entry.Value'},B=.5)
    nomodal=call(g,'nomodal',KML+':EqualEqual_IntInt',{'A':get(g,'ConfirmMode')},B=0)
    branch(g,'allowed',combine(g,'allowedcheck',[pressed,'ready.Ready',get(g,'UIOpen'),nomodal,validity(g,'pcvalid',get(g,'EditorController')),validity(g,'pickervalid',get(g,'Picker'))]))
    call(g,'ray',PC+':DeprojectMousePositionToWorld',{'self':get(g,'EditorController')});branch(g,'rayok','ray.ReturnValue')
    method(g,'pick',PICKER,'RequestPick',get(g,'Picker'),{'Origin':'ray.WorldLocation','Direction':'ray.WorldDirection','Limit':get(g,'ReachCm'),'EditStructure':get(g,'StructureEnabled'),'SelectFloors':get(g,'FloorsEnabled'),'SelectWalls':get(g,'WallsEnabled')})
    g.chain('entry','ready','allowed','rayok','pick')
    return g.function('RequestSelection',inputs=[v('Value','double')])


def pump():
    g=Graph();g.node('self','self');branch(g,'open',combine(g,'available',[get(g,'UIOpen'),call(g,'notdragging',KML+':Not_PreBool',{'A':get(g,'DragActive')}),validity(g,'pickervalid',get(g,'Picker'))]))
    branch(g,'busy',get(g,'Busy'));g.set('wasbusy','SelectionWasBusy','true')
    method(g,'cancel',PICKER,'CancelQuery',get(g,'Picker'))
    changed=call(g,'changedgeneration',KML+':NotEqual_IntInt',{'A':get(g,'SelectionGeneration'),'B':get(g,'Generation')});branch(g,'changed',combine(g,'changedcheck',[get(g,'SelectionWasBusy'),changed],True));g.call('clear','self:RevalidateSelection')
    branch(g,'transformonly',get(g,'SelectionTransformOnly'));g.set('resettransform','SelectionTransformOnly','false');method(g,'index',PICKER,'BeginIndex',get(g,'Picker'),{'WorldManager':'self.self'});g.set('reset','SelectionWasBusy','false');set_value(g,'generation','SelectionGeneration',get(g,'Generation'))
    method(g,'pumpindex',PICKER,'PumpIndex',get(g,'Picker'));method(g,'pumpquery',PICKER,'PumpQuery',get(g,'Picker'))
    branch(g,'modal',call(g,'modalcheck',KML+':Greater_IntInt',{'A':get(g,'ConfirmMode')},B=0));method(g,'modalcancel',PICKER,'CancelQuery',get(g,'Picker'))
    branch(g,'ready',prop(g,'readyflag',PICKER,'QueryReady',get(g,'Picker')))
    # Cache the facts before AcceptSelection clears the picker's pending result.
    set_value(g,'cache','local:Result',prop(g,'result',PICKER,'QueryResult',get(g,'Picker')));g.get('cached','local:Result')
    # Acknowledge before dispatch: group selection does not call AcceptSelection,
    # and must not consume the same completed result on every subsequent frame.
    method(g,'consumequery',PICKER,'CancelQuery',get(g,'Picker'))
    g.call('accept','self:ConsumePointerSelection');g.wire(('cached.Result','accept.Facts'))
    g.chain('entry','open','busy','wasbusy','cancel');g.chain('busy.else','changed','clear','transformonly','resettransform','reset','generation','pumpindex','pumpquery','modal','modalcancel');g.chain('changed.else','pumpindex');g.chain('transformonly.else','index','resettransform');g.chain('modal.else','ready','cache','consumequery','accept')
    return g.function('PollSelection',locals=[v('Result','struct:'+FACT)])


def revalidate():
    g=Graph();g.node('self','self');branch(g,'selected',get(g,'HasSelection'))
    unpack(g,'old',FACT,get(g,'Selected'))
    method(g,'classify',PICKER,'Classify',get(g,'Picker'),{'Manager':'self.self','Component':'old.Component','EditStructure':get(g,'StructureEnabled'),'SelectFloors':get(g,'FloorsEnabled'),'SelectWalls':get(g,'WallsEnabled')})
    set_value(g,'copy','local:FreshFacts','classify.Facts');g.get('facts','local:FreshFacts')
    unpack(g,'fresh',FACT,'facts.FreshFacts');branch(g,'allowed','fresh.Allowed')
    g.call('accept','self:AcceptSelection');g.wire(('facts.FreshFacts','accept.Facts'))
    g.call('clear','self:ClearSelection')
    # Undo/Store can legitimately remove the selection. Only an explicit pick
    # should display a rejection; automatic revalidation quietly deselects it.
    g.chain('entry','selected','classify','copy','allowed','accept');g.chain('allowed.else','clear')
    return g.function('RevalidateSelection',locals=[v('FreshFacts','struct:'+FACT)])


def refresh():
    g=Graph();branch(g,'valid',validity(g,'check',get(g,'Inspector')))
    # Settings take the inspector dock's place while open.
    settings=call(g,'settings',STR+'NotEqual_StrStr',{'A':get(g,'ActivePanel')},B='settings')
    branch(g,'selected',combine(g,'shown',[get(g,'HasSelection'),settings]));unpack(g,'facts',FACT,get(g,'Selected'))
    text(g,'name','Inspector','Selection',value='facts.Label');visibility(g,'panelshow',widget(g,'panel','Inspector','Panel'),'SelfHitTestInvisible');visibility(g,'show',get(g,'Inspector'),'SelfHitTestInvisible');visibility(g,'hide',get(g,'Inspector'),'Collapsed')
    g.call('fields','self:RefreshTransformFields');g.call('gizmostyle','self:RefreshGizmoModeUI');g.chain('entry','valid','selected','name','panelshow','show','fields','gizmostyle');g.chain('selected.else','hide')
    return g.function('RefreshSelectionUI')


def variables():return [v('Picker','object:'+PICKER),v('Selected','struct:'+FACT),v('HasSelection','bool'),v('SelectedHadDepth','bool'),v('SelectedStencil','int'),v('SelectionMessage','string'),v('SelectionWasBusy','bool'),v('SelectionGeneration','int','-1'),v('SelectionTransformOnly','bool')]
def functions():return [initialize(),clear_selection(),accept(),request(),pump(),revalidate(),refresh()]
