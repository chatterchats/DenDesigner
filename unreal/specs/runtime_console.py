"""World-owned native interaction for the Den office console; no map overrides."""
from graph import Graph,variable as v,GS,KSL,KML
from runtime import ROOT,arr
from runtime_store import call,branch,combine,STR
from runtime_world import ACTOR,SCENE,SMC,validity,set_value
from runtime_apply import get,clock,bump,clear
from runtime_session import prop

CONSOLE=ROOT+'BP_DenOfficeConsole'
INDICATOR=ROOT+'BP_DenConsoleIndicator'
WIDGET_COMPONENT='/Script/BitReactorGame.BitReactorWidgetComponent'
PROMPT='/Game/Game/UI/Tactical/ExploreMode/Widgets/WBP_TacticalExplorePrompts.WBP_TacticalExplorePrompts_C'
INTERACT='/Script/BitReactorGame.InteractableComponent'
MESH='/Game/Game/Environments/Strategy/HQ/Props/Consoles/ConsoleLocks/SM_HUB_ConsoleLocks_3x1.SM_HUB_ConsoleLocks_3x1'
ACTION='/Script/BitReactorGame.InteractableAction'
ACTION_DATA='/Script/BitReactorGame.InputActionAbilities'
IMAGE='/Script/BitReactorCore.BitReactorImageReference'
LABEL='OPEN DEN DESIGNER'
ICON_TAG='ImageBank.Icon.Options.Edit'
INPUT='/Game/Game/Input/Actions/IA_ExploreInteract.IA_ExploreInteract'


def matches():
    g=Graph()
    mesh=call(g,'mesh',STR+'EqualEqual_StrStr',{'A':'entry.MeshPath'},B=MESH)
    level=call(g,'level',STR+'StartsWith',{'SourceString':'entry.LevelPath'},InPrefix='/Game/Game/Maps/Hub/',SearchCase='CaseSensitive')
    g.wire((combine(g,'both',[mesh,level]),'result.Matches'));g.chain('entry','result')
    return g.function('MatchesConsole',inputs=[v('MeshPath','string'),v('LevelPath','string')],outputs=[v('Matches','bool')])


def consider():
    g=Graph();branch(g,'valid',validity(g,'component','entry.Component'))
    mesh=prop(g,'mesh',SMC,'StaticMesh','entry.Component');branch(g,'meshvalid',validity(g,'meshcheck',mesh))
    path=call(g,'path',KSL+':GetPathName',{'Object':mesh})
    owner=call(g,'owner','/Script/Engine.ActorComponent:GetOwner',{'self':'entry.Component'})
    level=call(g,'level',KSL+':GetPathName',{'Object':owner})
    g.call('matches','self:MatchesConsole');g.wire((path,'matches.MeshPath'),(level,'matches.LevelPath'));branch(g,'match','matches.Matches')
    set_value(g,'target','Target','entry.Component')
    g.chain('entry','valid','meshvalid','matches','match','target')
    return g.function('ConsiderConsole',inputs=[v('Component','object:'+SMC)])


def scan_step():
    g=Graph();arr(g,'length','Length',get(g,'Candidates'))
    branch(g,'within',call(g,'withincheck',KML+':Less_IntInt',{'A':get(g,'Cursor'),'B':'length.ReturnValue'}))
    arr(g,'actor','Get',get(g,'Candidates'));g.wire((get(g,'Cursor'),'actor.Index'));branch(g,'valid',validity(g,'actorvalid','actor.Item'))
    components=call(g,'components',ACTOR+':K2_GetComponentsByClass',{'self':'actor.Item'},ComponentClass=SMC)
    arr(g,'clen','Length',components);branch(g,'component',call(g,'cwithin',KML+':Less_IntInt',{'A':get(g,'ComponentCursor'),'B':'clen.ReturnValue'}))
    arr(g,'item','Get',components);g.wire((get(g,'ComponentCursor'),'item.Index'))
    g.node('cast','cast',**{'class':SMC});g.wire(('item.Item','cast.Object'))
    g.call('consider','self:ConsiderConsole');g.wire(('cast.AsStatic Mesh Component','consider.Component'))
    bump(g,'nextcomponent','ComponentCursor');bump(g,'nextactor','Cursor');g.set('reset','ComponentCursor','0')
    g.set('done','Scanning','false');clear(g,'release','Candidates')
    g.chain('entry','within','valid','component','cast','consider','nextcomponent')
    g.chain('valid.else','nextactor','reset');g.chain('component.else','nextactor');g.chain('cast.CastFailed','nextcomponent');g.chain('within.else','done','release')
    return g.function('ScanStep')


def find():
    g=Graph();g.node('self','self');branch(g,'found',validity(g,'targetvalid',get(g,'Target')))
    branch(g,'scanning',get(g,'Scanning'))
    branch(g,'due',call(g,'duecheck',KML+':GreaterEqual_DoubleDouble',{'A':clock(g,'now'),'B':get(g,'NextScan')}))
    actors=call(g,'actors',GS+':GetAllActorsOfClass',{'WorldContextObject':'self.self'},ActorClass='/Script/Engine.StaticMeshActor')
    set_value(g,'cache','Candidates','actors.OutActors');g.set('start','Scanning','true');g.set('cursor','Cursor','0');g.set('componentcursor','ComponentCursor','0')
    set_value(g,'later','NextScan',call(g,'nextscan',KML+':Add_DoubleDouble',{'A':clock(g,'starttime')},B=2))
    g.get('steps','local:Steps');branch(g,'budget',combine(g,'continue',[get(g,'Scanning'),call(g,'underbudget',KML+':Less_IntInt',{'A':'steps.Steps'},B=64),call(g,'missing',KML+':Not_PreBool',{'A':validity(g,'newtarget',get(g,'Target'))})]))
    g.call('step','self:ScanStep');set_value(g,'nextstep','local:Steps',call(g,'increment',KML+':Add_IntInt',{'A':'steps.Steps'},B=1))
    g.set('stop','Scanning','false');clear(g,'clear','Candidates')
    g.chain('entry','found','stop','clear');g.chain('found.else','scanning','budget','step','nextstep','budget')
    g.chain('scanning.else','due','actors','cache','start','cursor','componentcursor','later','budget')
    return g.function('FindConsole',locals=[v('Steps','int','0')])


def present_action():
    # The shipped DetermineValidInputActionAbilities rebuilds non-ability
    # actions with only InputAction. Supply presentation on that live object,
    # before the native view model's later-bound proximity listener reads it.
    g=Graph();branch(g,'valid',validity(g,'actionvalid','entry.Action'))
    data=prop(g,'data',ACTION,'Abilities','entry.Action')
    g.node('fields','break_struct',struct=ACTION_DATA);g.wire((data,'fields.InputActionAbilities'))
    g.node('icon','make_struct',struct=IMAGE,defaults={'ImageReferenceType':'ImageBank','ImageBankTag':f'(TagName="{ICON_TAG}")'})
    g.node('presentation','make_struct',struct=ACTION_DATA,defaults={'InteractionText':f'INVTEXT("{LABEL}")'})
    g.wire(('fields.InputAction','presentation.InputAction'),('fields.AbilityTags','presentation.AbilityTags'),('icon.BitReactorImageReference','presentation.Icon'))
    set_value(g,'apply',ACTION+':Abilities','presentation.InputActionAbilities');g.wire(('entry.Action','apply.self'))
    g.chain('entry','valid','apply')
    return g.function('PresentInteractionAction',inputs=[v('Action','object:'+ACTION)])


def present_current():
    g=Graph();action=prop(g,'current',INTERACT,'CurrentInteraction',get(g,'Interaction'))
    g.call('present','self:PresentInteractionAction');g.wire((action,'present.Action'));g.chain('entry','present')
    return g.function('PresentCurrentInteraction')


def indicator_spec():
    # Same native base/config as the game's BP_SimpleIndicatorComponent. Keep
    # its widget class soft so it resolves to the shipped game asset at runtime.
    return dict(kind='blueprint',path=INDICATOR,parent=WIDGET_COMPONENT,defaults={
        'Lifetime':'Manual','IndicatorConfig':f'(WidgetClass="{PROMPT}",bClampToScreen=True)'})


def fit_prompt_icon():
    g=Graph();branch(g,'valid',validity(g,'iconvalid','entry.Icon'))
    call(g,'pivot','/Script/UMG.Widget:SetRenderTransformPivot',{'self':'entry.Icon'},Pivot='(X=0.5,Y=0.5)')
    call(g,'scale','/Script/UMG.Widget:SetRenderScale',{'self':'entry.Icon'},Scale='(X=0.9,Y=0.9)')
    # Center the complete stock symbol, including its underline.
    call(g,'offset','/Script/UMG.Widget:SetRenderTranslation',{'self':'entry.Icon'},Translation='(X=0,Y=0)')
    parent=call(g,'parent','/Script/UMG.Widget:GetParent',{'self':'entry.Icon'});branch(g,'parentvalid',validity(g,'parentcheck',parent))
    slot=prop(g,'slot','/Script/UMG.Widget','Slot',parent)
    g.node('overlay','cast',**{'class':'/Script/UMG.OverlaySlot'});g.wire((slot,'overlay.Object'))
    call(g,'horizontal','/Script/UMG.OverlaySlot:SetHorizontalAlignment',{'self':'overlay.AsOverlay Slot'},InHorizontalAlignment='HAlign_Center')
    call(g,'vertical','/Script/UMG.OverlaySlot:SetVerticalAlignment',{'self':'overlay.AsOverlay Slot'},InVerticalAlignment='VAlign_Center')
    g.chain('entry','valid','pivot','scale','offset','parentvalid','overlay','horizontal','vertical')
    return g.function('FitPromptIcon',inputs=[v('Icon','object:/Script/UMG.Widget')])


def refresh_prompt_icon():
    g=Graph();g.node('self','self');branch(g,'cached',validity(g,'iconvalid',get(g,'PromptIcon')))
    branch(g,'due',call(g,'time',KML+':GreaterEqual_DoubleDouble',{'A':clock(g,'now'),'B':get(g,'NextPromptCheck')}))
    set_value(g,'next','NextPromptCheck',call(g,'later',KML+':Add_DoubleDouble',{'A':clock(g,'start')},B=.1))
    call(g,'widgets','/Script/UMG.WidgetBlueprintLibrary:GetAllWidgetsOfClass',{'WorldContextObject':'self.self'},WidgetClass=PROMPT,TopLevelOnly='false')
    arr(g,'length','Length','widgets.FoundWidgets');g.get('cursor','local:WidgetCursor')
    branch(g,'within',call(g,'withincheck',KML+':Less_IntInt',{'A':'cursor.WidgetCursor','B':'length.ReturnValue'}))
    arr(g,'item','Get','widgets.FoundWidgets');g.wire(('cursor.WidgetCursor','item.Index'))
    g.node('cast','cast',**{'class':PROMPT});g.wire(('item.Item','cast.Object'))
    owner=call(g,'owner','/Script/BitReactorGame.BRG_IndicatorWidget:GetAttachedActor',{'self':'cast.AsWBP Tactical Explore Prompts'})
    branch(g,'ours',call(g,'same',KML+':EqualEqual_ObjectObject',{'A':owner,'B':'self.self'}))
    icon=prop(g,'icon',PROMPT,'Icon','cast.AsWBP Tactical Explore Prompts')
    set_value(g,'cache','PromptIcon',icon);g.call('fit','self:FitPromptIcon');g.wire((icon,'fit.Icon'))
    set_value(g,'advance','local:WidgetCursor',call(g,'increment',KML+':Add_IntInt',{'A':'cursor.WidgetCursor'},B=1))
    g.chain('entry','cached');g.chain('cached.else','due','next','widgets','within','cast','owner','ours','cache','fit')
    g.chain('ours.else','advance','within');g.chain('cast.CastFailed','advance')
    return g.function('RefreshPromptIcon',locals=[v('WidgetCursor','int','0')])


def update_indicator():
    g=Graph();branch(g,'enabled',get(g,'Enabled'))
    active=call(g,'active',WIDGET_COMPONENT+':HasActiveIndicator',{'self':get(g,'PromptIndicator')});branch(g,'exists',active)
    call(g,'create',WIDGET_COMPONENT+':BP_CreateAndAddIndicator',{'self':get(g,'PromptIndicator')})
    call(g,'remove',WIDGET_COMPONENT+':RemoveIndicatorImmediate',{'self':get(g,'PromptIndicator')})
    g.set('clear','PromptIcon');g.set('reset','NextPromptCheck','0');g.call('fit','self:RefreshPromptIcon')
    g.chain('entry','enabled','exists','fit');g.chain('exists.else','clear','reset','create','fit');g.set('disabledclear','PromptIcon');g.chain('enabled.else','remove','disabledclear')
    return g.function('UpdateIndicator')


def available():
    g=Graph();set_value(g,'enabled','Enabled','entry.Available')
    set_value(g,'allow',INTERACT+':bAllowInteractions','entry.Available');g.wire((get(g,'Interaction'),'allow.self'))
    blocked=call(g,'blocked',KML+':Not_PreBool',{'A':'entry.Available'})
    call(g,'block',INTERACT+':SetInteractionBlocked',{'self':get(g,'Interaction'),'bInInteractionBlocked':blocked})
    branch(g,'disabled',blocked);g.set('clear','Requested','false');g.call('indicator','self:UpdateIndicator')
    g.chain('entry','enabled','allow','block','disabled','clear','indicator');g.chain('disabled.else','indicator')
    return g.function('SetAvailable',inputs=[v('Available','bool')])


def request():
    g=Graph();branch(g,'allowed',combine(g,'ready',[get(g,'Enabled'),validity(g,'target',get(g,'Target'))]));g.set('request','Requested','true')
    g.chain('entry','allowed','request');return g.function('RequestOpen')


def consume():
    g=Graph();set_value(g,'capture','local:Pending',get(g,'Requested'));g.set('clear','Requested','false');g.get('out','local:Pending');g.wire(('out.Pending','result.Requested'))
    g.chain('entry','capture','clear','result');return g.function('ConsumeRequest',outputs=[v('Requested','bool')],locals=[v('Pending','bool')])


def update():
    g=Graph();g.node('self','self');g.call('find','self:FindConsole');branch(g,'target',validity(g,'valid',get(g,'Target')))
    hidden=prop(g,'hidden',SCENE,'bHiddenInGame',get(g,'Target'))
    owner=call(g,'owner','/Script/Engine.ActorComponent:GetOwner',{'self':get(g,'Target')})
    actorhidden=prop(g,'actorhidden',ACTOR,'bHidden',owner)
    enabled=combine(g,'enabled',['entry.Available',call(g,'visible',KML+':Not_PreBool',{'A':hidden}),call(g,'actorvisible',KML+':Not_PreBool',{'A':actorhidden})])
    call(g,'bounds',KSL+':GetComponentBounds',{'Component':get(g,'Target')})
    call(g,'move',ACTOR+':K2_SetActorLocation',{'self':'self.self','NewLocation':'bounds.Origin'},bSweep='false',bTeleport='true')
    g.call('enable','self:SetAvailable');g.wire((enabled,'enable.Available'));g.call('disable','self:SetAvailable',Available='false')
    g.chain('entry','find','target','move','enable');g.chain('target.else','disable')
    return g.function('UpdateConsole',inputs=[v('Available','bool')])


def spec():
    g=Graph();g.node('activate','bound_event',component='Interaction',delegate='OnInteractionActivated');g.call('request','self:RequestOpen');g.chain('activate','request')
    for name,delegate in [('near','OnEnterNearInteraction'),('enter','OnEnterInteraction')]:
        g.node(name,'bound_event',component='Interaction',delegate=delegate);g.call(name+'presentation','self:PresentCurrentInteraction');g.chain(name,name+'presentation')
    g.node('end','event',name='ReceiveEndPlay');call(g,'removeindicator',WIDGET_COMPONENT+':RemoveIndicatorImmediate',{'self':get(g,'PromptIndicator')});g.chain('end','removeindicator')
    return dict(kind='blueprint',path=CONSOLE,parent=ACTOR,
        components=[dict(name='PromptIndicator',**{'class':INDICATOR},props={'Lifetime':'Manual','IndicatorConfig':f'(WidgetClass="{PROMPT}",bClampToScreen=True)'}),dict(name='Root',**{'class':SCENE},props={'Mobility':'Movable'}),dict(name='Interaction',**{'class':INTERACT},attach='Root',props={
            'bUsesAbilities':'false','bRegisterSelectionGroup':'true','bIsSingleUse':'false','bAllowInteractions':'false','bInteractionBlocked':'true',
            'InputActionAbilities':f'((InputAction="{INPUT}",InteractionText="Open Den Designer"))'})],
        variables=[v('PromptIcon','object:/Script/UMG.Widget'),v('NextPromptCheck','double'),v('Target','object:'+SMC),v('Enabled','bool'),v('Requested','bool'),v('Candidates','object:'+ACTOR+'[]'),v('Scanning','bool'),v('Cursor','int'),v('ComponentCursor','int'),v('NextScan','double')],
        graph=g.spec(),functions=[matches(),consider(),scan_step(),find(),present_action(),present_current(),fit_prompt_icon(),refresh_prompt_icon(),update_indicator(),available(),request(),consume(),update()])
