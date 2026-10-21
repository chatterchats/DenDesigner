"""Editor-only authoring of a separate, disposable travel-test Game Feature.

It reads Den Designer state for its diagnostic overlay without changing it.
F7 calls the game's completion
helper only in the sandbox campaign, on SK_Kaller_020_Root, once per world.
"""
import json
import os
import sys
from pathlib import Path
import unreal
import zcom_authoring

REPO = Path(os.environ['DEN_TRAVEL_REPO'])
sys.path.insert(0, str(REPO / 'unreal/specs'))
from graph import Graph, variable as v, GS, KML, KSL, WBL
from runtime_store import call, branch, combine, STR
from runtime_world import validity
from runtime_apply import get
from runtime_coordinator import campaign, campaign_text, COORDINATOR
from runtime_editor_host import HOST
from runtime_shortcut import SHORTCUT
from runtime_session import prop

PLUGIN = 'DenTravelQA'
BRAIN = '/DenTravelQA/BP_TravelProbe'
PANEL = '/DenTravelQA/WBP_TravelProbe'
MISSION = '/Script/BitReactorGame.BRGameMissionActor'
PC = '/Script/Engine.PlayerController'
SANDBOX = 'BA3302BC4165EB931E86A39BFF208F71'


def probe():
    g = Graph(); g.node('self', 'self')
    g.node('tick', 'event', name='ReceiveTick')
    level = call(g, 'world', GS + ':GetCurrentLevelName', {'WorldContextObject': 'self.self'}, bRemovePrefixString='true')
    branch(g, 'map', call(g, 'matches', STR+'EqualEqual_StrStr', {'A': level}, B='SK_Kaller_020_Root'))
    g.call('campaign', 'self:ReadActiveCampaign')
    branch(g, 'sandbox', combine(g, 'allowed', ['campaign.Known', call(g, 'identity', STR+'EqualEqual_StrStr', {'A': 'campaign.CampaignID'}, B=SANDBOX)]))
    pc = call(g, 'player', GS+':GetPlayerController', {'WorldContextObject':'self.self'}, PlayerIndex=0)
    branch(g, 'playerok', validity(g, 'pcvalid', pc))
    branch(g, 'shown', validity(g, 'panelvalid', get(g, 'Panel')))
    created = call(g, 'create', WBL+':Create', {'WorldContextObject':'self.self', 'OwningPlayer':pc}, WidgetType=PANEL)
    g.set('panel', 'Panel');g.wire((created, 'panel.Panel'))
    call(g, 'show', '/Script/UMG.UserWidget:AddToViewport', {'self':created}, ZOrder=500)
    branch(g, 'unused', call(g, 'notused', KML+':Not_PreBool', {'A':get(g, 'Used')}))
    held = [call(g, 'key'+str(i), PC+':IsInputKeyDown', {'self':pc}, Key=key) for i,key in enumerate(['F7'])]
    branch(g, 'pressed', combine(g, 'chord', held))
    actor = call(g, 'mission', GS+':GetActorOfClass', {'WorldContextObject':'self.self'}, ActorClass=MISSION)
    g.node('cast', 'cast', **{'class':MISSION});g.wire((actor,'cast.Object'))
    target = 'cast.AsBRGame Mission Actor'
    branch(g, 'progress', call(g, 'running', MISSION+':IsInProgress', {'self':target}))
    g.set('used', 'Used', 'true')
    call(g, 'remove', '/Script/UMG.Widget:RemoveFromParent', {'self':get(g,'Panel')})
    call(g, 'complete', MISSION+':CompleteMissionCheat', {'self':target})
    g.chain('tick','world','map','campaign','sandbox','playerok','shown','unused','pressed','mission','cast','running','progress','used','remove','complete')
    g.chain('shown.else','create','panel','show','unused')
    g.call('diagnose','self:Diagnose');g.chain('map.else','diagnose')
    return dict(kind='blueprint', path=BRAIN, parent='/Script/Engine.ActorComponent',
                defaults={'PrimaryComponentTick.bCanEverTick':'true','PrimaryComponentTick.bStartWithTickEnabled':'true'},
                variables=[v('Used','bool','false'),v('Panel','object:/Script/UMG.UserWidget')],
                functions=[campaign_text(),campaign(),diagnose(),show_status()],graph=g.spec())


def show_status():
    g=Graph();g.node('self','self')
    pc=call(g,'pc',GS+':GetPlayerController',{'WorldContextObject':'self.self'},PlayerIndex=0)
    branch(g,'shown',validity(g,'valid',get(g,'Panel')))
    widget=call(g,'create',WBL+':Create',{'WorldContextObject':'self.self','OwningPlayer':pc},WidgetType=PANEL)
    g.set('remember','Panel');g.wire((widget,'remember.Panel'))
    call(g,'add','/Script/UMG.UserWidget:AddToViewport',{'self':widget},ZOrder=500)
    g.node('cast','cast',**{'class':PANEL});g.wire((get(g,'Panel'),'cast.Object'))
    message=prop(g,'message',PANEL,'Message','cast.AsWBP Travel Probe')
    call(g,'set','/Script/UMG.TextBlock:SetText',{'self':message,'InText':'entry.Text'})
    g.chain('entry','shown','cast','set');g.chain('shown.else','create','remember','add','cast')
    return g.function('ShowStatus',inputs=[v('Text','string')])


def diagnose():
    g=Graph();g.node('self','self')
    level=call(g,'level',GS+':GetCurrentLevelName',{'WorldContextObject':'self.self'},bRemovePrefixString='true')
    branch(g,'den',call(g,'matches',STR+'EqualEqual_StrStr',{'A':level},B='HUB_Root'))
    owner=call(g,'owner','/Script/Engine.ActorComponent:GetOwner',{'self':'self.self'})
    coord=call(g,'component','/Script/Engine.Actor:GetComponentByClass',{'self':owner},ComponentClass=COORDINATOR)
    g.node('cast','cast',**{'class':COORDINATOR});g.wire((coord,'cast.Object'));c='cast.AsBP Den Runtime Coordinator'
    g.call('absent','self:ShowStatus',Text='QA: no Den Designer coordinator on this GameState')
    host=prop(g,'host',COORDINATOR,'Host',c);shortcut=prop(g,'shortcut',COORDINATOR,'Shortcut',c)
    player=prop(g,'player',COORDINATOR,'Player',c)
    pc=call(g,'pc',GS+':GetPlayerController',{'WorldContextObject':'self.self'},PlayerIndex=0)
    fields=[('Initialized',prop(g,'initialized',COORDINATOR,'Initialized',c),'bool'),
            ('OpenRequested',prop(g,'requested',COORDINATOR,'OpenRequested',c),'bool'),
            ('Host valid',validity(g,'hostvalid',host),'bool'),
            ('Busy',prop(g,'busy',HOST,'Busy',host),'bool'),
            ('UIOpen',prop(g,'open',HOST,'UIOpen',host),'bool'),
            ('Player matches',call(g,'match',KML+':EqualEqual_ObjectObject',{'A':pc,'B':player}),'bool'),
            ('Home',call(g,'home',PC+':IsInputKeyDown',{'self':pc},Key='Home'),'bool'),
            ('Ctrl',call(g,'ctrl',PC+':IsInputKeyDown',{'self':pc},Key='LeftControl'),'bool'),
            ('Shortcut valid',validity(g,'shortcutvalid',shortcut),'bool'),
            ('Key',prop(g,'key',SHORTCUT,'KeyName',shortcut),'string'),
            ('Modifier',prop(g,'modifier',SHORTCUT,'Modifier',shortcut),'string'),
            ('KeyWasDown',prop(g,'wasdown',SHORTCUT,'KeyWasDown',shortcut),'bool')]
    text=None
    for i,(label,value,kind) in enumerate(fields):
        if kind=='bool':value=call(g,'convert'+str(i),STR+'Conv_BoolToString',{'InBool':value})
        piece=call(g,'field'+str(i),STR+'Concat_StrStr',{'B':value},A=label+'=')
        if text is None:text=piece
        else:
            text=call(g,'sep'+str(i),STR+'Concat_StrStr',{'A':text},B='  |  ' if i%3 else '\n')
            text=call(g,'append'+str(i),STR+'Concat_StrStr',{'A':text,'B':piece})
    g.call('show','self:ShowStatus');g.wire((text,'show.Text'))
    g.chain('entry','level','den','cast','show');g.chain('cast.CastFailed','absent')
    return g.function('Diagnose')


def panel():
    return dict(kind='widget',path=PANEL,tree={'class':'/Script/UMG.CanvasPanel','name':'Root','props':{'Visibility':'HitTestInvisible'},'children':[
        {'class':'/Script/UMG.Border','name':'Banner','props':{'BrushColor':'(R=0.08,G=0.02,B=0.02,A=0.95)'},
         'slot':{'LayoutData':'(Offsets=(Left=500,Top=100,Right=1250,Bottom=190))'},
         'children':[{'class':'/Script/UMG.TextBlock','name':'Message','variable':True,'props':{'Text':'QA ONLY | Sandbox mission | F7 completes mission','Font.Size':18,'AutoWrapText':'true','Justification':'Left'}}]}]})

specdir=REPO/'dist/verification/travel-qa/specs';specdir.mkdir(parents=True,exist_ok=True)
paths=[]
for i,spec in enumerate([panel(),probe()]):
    path=specdir/f'{i:02}.json';path.write_text(json.dumps(spec));paths.append(path)
assert zcom_authoring.build(paths),'Travel QA Blueprint build failed'
factory=unreal.DataAssetFactory();factory.set_editor_property('data_asset_class',unreal.GameFeatureData)
lib=unreal.EditorAssetLibrary
data=lib.load_asset('/DenTravelQA/DenTravelQA') if lib.does_asset_exist('/DenTravelQA/DenTravelQA') else unreal.AssetToolsHelpers.get_asset_tools().create_asset(PLUGIN,'/DenTravelQA',unreal.GameFeatureData,factory)
action=unreal.find_object(data,'AddTravelProbe') or unreal.new_object(unreal.load_class(None,'/Script/GameFeatures.GameFeatureAction_AddComponents'),outer=data,name='AddTravelProbe')
assert not unreal.ZComAuthoringLibrary.set_property_from_text(action,'ComponentList',f'((ActorClass="/Script/BitReactorGame.BitReactorGameState",ComponentClass="{BRAIN}.BP_TravelProbe_C",bClientComponent=True,bServerComponent=True))')
assert not unreal.ZComAuthoringLibrary.set_property_from_text(data,'Actions',f'("{action.get_path_name()}")')
lib.save_loaded_asset(data,only_if_is_dirty=False)
unreal.log('DEN_TRAVEL_QA_RESULT ok')
