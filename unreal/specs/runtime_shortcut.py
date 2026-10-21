"""Pak-only opening shortcut, independent of the editor's temporary input map."""
from graph import Graph,variable as v,GS,KML
from runtime import ROOT
from runtime_store import call,branch,combine,STR
from runtime_world import validity,set_value
from runtime_apply import get
from runtime_session import method
from runtime_preferences import DOCUMENT
from runtime_key_names import CODEC,KEY
from runtime_input_mappings import BUILDER

SHORTCUT=ROOT+'BP_DenShortcut'
PC='/Script/Engine.PlayerController'


def configure():
    g=Graph();g.node('self','self');g.set('defaultkey','Key','Home');g.set('defaultname','KeyName','Home');g.set('defaultmodifier','Modifier','ctrl')
    branch(g,'valid',validity(g,'document','entry.Document'))
    call(g,'builder',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=BUILDER);g.node('castbuilder','cast',**{'class':BUILDER});g.wire(('builder.ReturnValue','castbuilder.Object'))
    method(g,'validate',BUILDER,'ValidateBindings','castbuilder.AsBP Den Input Mappings',{'Document':'entry.Document'});branch(g,'bindings','validate.Valid')
    call(g,'codec',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=CODEC);g.node('cast','cast',**{'class':CODEC});g.wire(('codec.ReturnValue','cast.Object'))
    method(g,'readkey',DOCUMENT,'ReadPreference','entry.Document',Key='toggle_key');method(g,'readmodifier',DOCUMENT,'ReadPreference','entry.Document',Key='toggle_modifier')
    method(g,'key',CODEC,'KeyFromName','cast.AsBP Den Key Names',{'Name':'readkey.Value'});branch(g,'known','key.Known')
    set_value(g,'savekey','Key','key.Key');set_value(g,'savename','KeyName','readkey.Value');set_value(g,'savemodifier','Modifier','readmodifier.Value')
    g.chain('entry','defaultkey','defaultname','defaultmodifier','valid','builder','castbuilder','validate','bindings','codec','cast','readkey','readmodifier','key','known','savekey','savename','savemodifier')
    return g.function('Configure',inputs=[v('Document','object:'+DOCUMENT)])


def pressed():
    g=Graph();branch(g,'valid',validity(g,'player','entry.Player'))
    # The GameState component can tick before PlayerController input processing.
    # Retain our own edge across frames instead of sampling its one-frame event.
    down=call(g,'down',PC+':IsInputKeyDown',{'self':'entry.Player','Key':get(g,'Key')})
    g.call('edge','self:ObserveKey');g.wire((down,'edge.Down'));branch(g,'key','edge.Pressed')
    mods={}
    for group,keys in [('ctrl',['LeftControl','RightControl']),('shift',['LeftShift','RightShift']),('alt',['LeftAlt','RightAlt'])]:
        mods[group]=combine(g,group+'held',[call(g,key,PC+':IsInputKeyDown',{'self':'entry.Player'},Key=key) for key in keys],True)
    choices=[]
    for group in ['ctrl','shift','alt','none']:
        matches=[call(g,group+'selected',STR+'EqualEqual_StrStr',{'A':get(g,'Modifier')},B=group)]
        for other,state in mods.items():matches.append(state if other==group else call(g,group+'not'+other,KML+':Not_PreBool',{'A':state}))
        choices.append(combine(g,group+'matches',matches))
    set_value(g,'save','local:ResultPressed',combine(g,'matched',choices,True));g.get('out','local:ResultPressed');g.wire(('out.ResultPressed','result.Pressed'))
    g.chain('entry','valid','edge','key','save','result');g.chain('valid.else','result');g.chain('key.else','result')
    return g.function('Pressed',inputs=[v('Player','object:'+PC)],outputs=[v('Pressed','bool')],locals=[v('ResultPressed','bool','false')])


def observe_key():
    g=Graph()
    rising=combine(g,'rising',['entry.Down',call(g,'released',KML+':Not_PreBool',{'A':get(g,'KeyWasDown')})])
    set_value(g,'capture','local:Rising',rising);set_value(g,'remember','KeyWasDown','entry.Down')
    g.get('output','local:Rising');g.wire(('output.Rising','result.Pressed'))
    g.chain('entry','capture','remember','result')
    return g.function('ObserveKey',inputs=[v('Down','bool')],outputs=[v('Pressed','bool')],locals=[v('Rising','bool','false')])


def spec():return dict(kind='blueprint',path=SHORTCUT,parent='/Script/CoreUObject.Object',variables=[v('Key',KEY,'Home'),v('KeyName','string','Home'),v('Modifier','string','ctrl'),v('KeyWasDown','bool','false')],functions=[configure(),observe_key(),pressed()])
