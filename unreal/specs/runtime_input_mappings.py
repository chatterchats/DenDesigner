"""Per-editor Enhanced Input mappings, built with native Blueprint operations.

Mappings are copied into a newly spawned context; the cooked template is never
mutated. Triggers/modifiers retain their authored configuration and order.
Enhanced Input deep-copies those objects when building a player's active maps.
"""
from graph import Graph, variable as v, GS, KML
from runtime import ROOT, arr
from runtime_preferences import DOCUMENT, BINDINGS, output
from runtime_key_names import CODEC, KEY, INPUT
from runtime_editor_assets import UIROOT
from runtime_store import call, branch, combine, STR

BUILDER=ROOT+'BP_DenInputMappings'
IMC='/Script/EnhancedInput.InputMappingContext'
MAPPING='/Script/EnhancedInput.EnhancedActionKeyMapping'


def binding_for_mapping():
    g=Graph();g.node('fields','break_struct',struct=MAPPING);g.wire(('entry.Mapping','fields.EnhancedActionKeyMapping'))
    previous='entry'
    for i,(key,action,original,_) in enumerate(BINDINGS):
        ident='b'+str(i)
        actionok=call(g,ident+'action',KML+':EqualEqual_ObjectObject',{'A':'fields.Action'},B=UIROOT+action)
        keyok=call(g,ident+'key',INPUT+'EqualEqual_KeyKey',{'A':'fields.Key'},B=original)
        branch(g,ident,combine(g,ident+'same',[actionok,keyok]));g.set(ident+'value','local:ResultSetting',key)
        g.chain(previous,ident,ident+'value','result');previous=ident+'.else'
    g.chain(previous,'result')
    return g.function('BindingForMapping',inputs=[v('Mapping','struct:'+MAPPING)],outputs=[v('Setting','string')],locals=[output(g,'Setting','string')])


def validate_bindings():
    g=Graph();branch(g,'valid',call(g,'alive','/Script/Engine.KismetSystemLibrary:IsValid',{'Object':'entry.Document'}));previous='valid'
    for i,key in enumerate([*[b[0] for b in BINDINGS],'toggle_key']):
        ident='b'+str(i)
        call(g,ident+'read',DOCUMENT+':ReadPreference',{'self':'entry.Document'},Key=key)
        call(g,ident+'available',DOCUMENT+':BindingAvailable',{'self':'entry.Document','Value':ident+'read.Value'},Key=key)
        branch(g,ident+'free',ident+'available.Available');g.chain(previous,ident+'read',ident+'available',ident+'free');g.chain(ident+'free.else','result');previous=ident+'free'
    g.set('yes','local:ResultValid','true');g.chain('entry','valid');g.chain(previous,'yes','result');g.chain('valid.else','result')
    return g.function('ValidateBindings',inputs=[v('Document','object:'+DOCUMENT)],outputs=[v('Valid','bool')],locals=[output(g,'Valid','bool','false')])


def build():
    g=Graph();g.node('self','self');g.get('template','Template');branch(g,'templatevalid',call(g,'templatealive','/Script/Engine.KismetSystemLibrary:IsValid',{'Object':'template.Template'}))
    g.call('validate','self:ValidateBindings');g.wire(('entry.Document','validate.Document'))
    g.set('defaultflag','local:ResultUsedDefaults');g.wire((call(g,'fallback',KML+':Not_PreBool',{'A':'validate.Valid'}),'defaultflag.ResultUsedDefaults'))
    call(g,'create',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=IMC);g.node('cast','cast',**{'class':IMC});g.wire(('create.ReturnValue','cast.Object'))
    call(g,'codec',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=CODEC);g.node('keycast','cast',**{'class':CODEC});g.wire(('codec.ReturnValue','keycast.Object'))
    g.get('source',IMC+':Mappings');g.wire(('template.Template','source.self'));arr(g,'length','Length','source.Mappings')
    g.get('i','local:Cursor');branch(g,'loop',call(g,'within',KML+':Less_IntInt',{'A':'i.Cursor','B':'length.ReturnValue'}))
    arr(g,'row','Get','source.Mappings');g.wire(('i.Cursor','row.Index'));g.node('fields','break_struct',struct=MAPPING);g.wire(('row.Item','fields.EnhancedActionKeyMapping'))
    g.set('original','local:ChosenKey');g.wire(('fields.Key','original.ChosenKey'))
    g.call('binding','self:BindingForMapping');g.wire(('row.Item','binding.Mapping'))
    branch(g,'override',combine(g,'canoverride',['validate.Valid',call(g,'setting',STR+'NotEqual_StrStr',{'A':'binding.Setting'},B='')]))
    call(g,'read',DOCUMENT+':ReadPreference',{'self':'entry.Document','Key':'binding.Setting'})
    call(g,'resolve',CODEC+':KeyFromName',{'self':'keycast.AsBP Den Key Names','Name':'read.Value'});branch(g,'known','resolve.Known')
    g.set('chosen','local:ChosenKey');g.wire(('resolve.Key','chosen.ChosenKey'));g.get('key','local:ChosenKey')
    g.node('mapping','make_struct',struct=MAPPING)
    for field in ['Action','Modifiers','Triggers']:g.wire(('fields.'+field,'mapping.'+field))
    g.wire(('key.ChosenKey','mapping.Key'))
    g.get('target',IMC+':Mappings');g.wire(('cast.AsInput Mapping Context','target.self'));arr(g,'append','Add','target.Mappings');g.wire(('mapping.EnhancedActionKeyMapping','append.NewItem'))
    g.set('next','local:Cursor');g.wire((call(g,'add',KML+':Add_IntInt',{'A':'i.Cursor'},B=1),'next.Cursor'))
    g.set('context','local:ResultContext');g.wire(('cast.AsInput Mapping Context','context.ResultContext'));g.set('yes','local:ResultAccepted','true')
    g.chain('entry','templatevalid','validate','defaultflag','create','cast','codec','keycast','loop','original','binding','override','read','resolve','known','chosen','append','next','loop')
    g.chain('override.else','append');g.chain('known.else','result');g.chain('loop.else','context','yes','result')
    for pin in ['templatevalid.else','cast.CastFailed','keycast.CastFailed']:g.chain(pin,'result')
    return g.function('BuildEditorContext',inputs=[v('Document','object:'+DOCUMENT)],outputs=[v('Context','object:'+IMC),v('Accepted','bool'),v('UsedDefaults','bool')],
                      locals=[v('Cursor','int','0'),v('ChosenKey',KEY),output(g,'Context','object:'+IMC),output(g,'Accepted','bool','false'),output(g,'UsedDefaults','bool','true')])


def spec():
    return dict(kind='blueprint',path=BUILDER,parent='/Script/CoreUObject.Object',variables=[v('Template','object:'+IMC,UIROOT+'IMC_DenEditor')],
                functions=[binding_for_mapping(),validate_bindings(),build()])
