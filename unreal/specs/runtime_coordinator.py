"""World-owned standalone lifecycle. Reads campaign identity, never campaign saves."""
from graph import Graph,variable as v,GS,KML,KSL,WBL
from runtime import ROOT,LAYOUT
from runtime_store import call,branch,combine,STR
from runtime_world import validity,set_value,ACTOR,finish_bool
from runtime_apply import get,clock
from runtime_session import method,prop,STORE
from runtime_editor_host import HOST,PC
from runtime_editor_assets import BUS
from runtime_preferences import DOCUMENT
from runtime_shortcut import SHORTCUT
from runtime_console import CONSOLE

COORDINATOR=ROOT+'BP_DenRuntimeCoordinator'
NOTICE=ROOT+'WBP_DenStartupNotice'
GUID='/Script/Engine.KismetGuidLibrary:'


def campaign_text():
    g=Graph();known=call(g,'valid',GUID+'IsValid_Guid',{'InGuid':'entry.ID'});branch(g,'known',known)
    text=call(g,'text',GUID+'Conv_GuidToString',{'InGuid':'entry.ID'});canonical=call(g,'canonical',STR+'Replace',{'SourceString':text},From='-',To='',SearchCase='CaseSensitive')
    set_value(g,'save','local:Value',canonical);g.get('out','local:Value');g.wire(('out.Value','result.CampaignID'),(known,'result.Known'))
    g.chain('entry','known','save','result');g.chain('known.else','result')
    return g.function('CampaignText',inputs=[v('ID','struct:/Script/CoreUObject.Guid')],outputs=[v('CampaignID','string'),v('Known','bool')],locals=[v('Value','string')])


def campaign():
    g=Graph();g.node('self','self');gi=call(g,'instance','/Script/Bruno.BrunoGameInstance:GetBrunoGameInstance',{'WorldContext':'self.self'})
    branch(g,'valid',validity(g,'exists',gi));data=prop(g,'data','/Script/Bruno.BrunoGameInstance','StrategyData',gi)
    g.node('strategy','break_struct',struct='/Script/Bruno.BrunoStrategyData');g.wire((data,'strategy.BrunoStrategyData'))
    g.call('format','self:CampaignText');g.wire(('strategy.CampaignTelemetryID','format.ID'),('format.CampaignID','result.CampaignID'),('format.Known','result.Known'))
    g.chain('entry','valid','format','result');g.chain('valid.else','result')
    return g.function('ReadActiveCampaign',outputs=[v('CampaignID','string'),v('Known','bool')])


def ensure_host():
    g=Graph();g.node('self','self');branch(g,'exists',validity(g,'host',get(g,'Host')))
    owner=call(g,'owner','/Script/Engine.ActorComponent:GetOwner',{'self':'self.self'})
    xf=call(g,'transform',KML+':MakeTransform',{},Scale='1,1,1')
    pending=call(g,'spawn',GS+':BeginDeferredActorSpawnFromClass',{'WorldContextObject':'self.self','Owner':owner,'SpawnTransform':xf},ActorClass=HOST,CollisionHandlingOverride='AlwaysSpawn')
    actor=call(g,'finish',GS+':FinishSpawningActor',{'Actor':pending,'SpawnTransform':xf});g.node('cast','cast',**{'class':HOST});g.wire((actor,'cast.Object'))
    set_value(g,'remember','Host','cast.AsBP Den Editor Host')
    method(g,'services',HOST,'EnsureServices',get(g,'Host'));branch(g,'ready','services.Accepted')
    method(g,'preferences',HOST,'ReadEditorPreferences',get(g,'Host'));method(g,'applypreferences',HOST,'ApplyEditorPreferences',get(g,'Host'))
    g.set('yes','local:OK','true');finish_bool(g);g.chain('entry','exists','services')
    g.chain('yes','result')
    g.chain('exists.else','spawn','finish','cast','remember','services','ready','preferences','applypreferences','yes');g.chain('cast.CastFailed','result');g.chain('ready.else','result')
    return g.function('EnsureHost',outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def prepare_layout():
    g=Graph();g.call('ensure','self:EnsureHost');branch(g,'ready','ensure.Accepted')
    method(g,'flush',HOST,'FlushDraft',get(g,'Host'));method(g,'detach',HOST,'DetachEditor',get(g,'Host'),RestoreView='true')
    method(g,'cancel',HOST,'CancelWork',get(g,'Host'))
    g.set('closed',HOST+':Editing','false');g.wire((get(g,'Host'),'closed.self'))
    set_value(g,'campaign',HOST+':ActiveCampaignID','entry.CampaignID');g.wire((get(g,'Host'),'campaign.self'))
    storage=prop(g,'storage',HOST,'Storage',get(g,'Host'));method(g,'resolve',STORE,'ResolveLayout',storage,{'CampaignID':'entry.CampaignID'})
    set_value(g,'status','LayoutStatus','resolve.Status');set_value(g,'key','ResolvedKey','resolve.Key')
    method(g,'open',HOST,'OpenSession',get(g,'Host'),{'Key':'resolve.Key','Document':'resolve.Document','LoadStatus':'resolve.Status'})
    # Applying a saved layout at arrival is not an editing session. Recovery is
    # offered only after the user opens the editor, never applied automatically.
    g.set('background',HOST+':Editing','false');g.wire((get(g,'Host'),'background.self'))
    branch(g,'applied','open.Accepted');method(g,'clearold',HOST,'BeginBatch',get(g,'Host'),ReplaceAll='true')
    g.wire(('open.Accepted','result.Accepted'));set_value(g,'cached','CampaignID','entry.CampaignID');g.set('initialized','Initialized','true')
    g.chain('entry','ensure','ready','flush','detach','cancel','closed','campaign','resolve','status','key','open','background','applied','cached','initialized','result');g.chain('ready.else','result');g.chain('applied.else','clearold','cached')
    return g.function('PrepareLayout',inputs=[v('CampaignID','string')],outputs=[v('Accepted','bool')])


def update_shortcut():
    g=Graph();g.node('self','self');branch(g,'exists',validity(g,'shortcut',get(g,'Shortcut')))
    call(g,'create',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=SHORTCUT);g.node('cast','cast',**{'class':SHORTCUT});g.wire(('create.ReturnValue','cast.Object'));set_value(g,'save','Shortcut','cast.AsBP Den Shortcut')
    doc=prop(g,'doc',HOST,'PreferencesDocument',get(g,'Host'))
    branch(g,'changed',call(g,'different',KML+':NotEqual_ObjectObject',{'A':doc,'B':get(g,'ShortcutDocument')}))
    method(g,'configure',SHORTCUT,'Configure',get(g,'Shortcut'),{'Document':doc});set_value(g,'cached','ShortcutDocument',doc)
    g.chain('entry','exists','changed','configure','cached');g.chain('exists.else','create','cast','save','configure')
    return g.function('UpdateShortcut')


def clear_notice():
    g=Graph();branch(g,'exists',validity(g,'notice',get(g,'Notice')));call(g,'remove','/Script/UMG.Widget:RemoveFromParent',{'self':get(g,'Notice')});g.set('clear','Notice')
    g.chain('entry','exists','remove','clear');g.chain('exists.else','clear');return g.function('ClearNotice')


def show_notice():
    g=Graph();g.node('self','self');g.call('clear','self:ClearNotice')
    call(g,'create',WBL+':Create',{'WorldContextObject':'self.self','OwningPlayer':get(g,'Player')},WidgetType=NOTICE);g.node('cast','cast',**{'class':NOTICE});g.wire(('create.ReturnValue','cast.Object'));set_value(g,'save','Notice','cast.AsWBP Den Startup Notice')
    field=prop(g,'text',NOTICE,'Message',get(g,'Notice'));call(g,'message','/Script/UMG.TextBlock:SetText',{'self':field,'InText':'entry.Message'})
    call(g,'show','/Script/UMG.UserWidget:AddToViewport',{'self':get(g,'Notice')},ZOrder=100)
    set_value(g,'expires','NoticeUntil',call(g,'due',KML+':Add_DoubleDouble',{'A':clock(g,'now')},B=8))
    g.chain('entry','clear','create','cast','save','message','show','expires');return g.function('ShowNotice',inputs=[v('Message','string')])


def toggle():
    g=Graph();branch(g,'ready',combine(g,'available',[get(g,'Initialized'),validity(g,'host',get(g,'Host')),validity(g,'player',get(g,'Player'))]))
    branch(g,'open',prop(g,'ui',HOST,'UIOpen',get(g,'Host')))
    bus=prop(g,'bus',HOST,'InputBus',get(g,'Host'));method(g,'typing',BUS,'IsTyping',bus);branch(g,'focused','typing.Typing')
    method(g,'close',HOST,'RequestEditorExit',get(g,'Host'));g.call('request','self:RequestEditorOpen')
    g.chain('entry','ready','open','typing','focused');g.chain('focused.else','close');g.chain('open.else','request')
    return g.function('ToggleEditor')


def request_open():
    g=Graph();g.node('self','self')
    branch(g,'ready',combine(g,'available',[get(g,'Initialized'),validity(g,'host',get(g,'Host')),validity(g,'player',get(g,'Player'))]))
    branch(g,'open',prop(g,'ui',HOST,'UIOpen',get(g,'Host')))
    branch(g,'paused',call(g,'pausedvalue',GS+':IsGamePaused',{'WorldContextObject':'self.self'}));g.set('request','OpenRequested','true')
    g.chain('entry','ready','open');g.chain('open.else','paused');g.chain('paused.else','request')
    return g.function('RequestEditorOpen')


def update_console():
    g=Graph();g.node('self','self');branch(g,'exists',validity(g,'console',get(g,'OfficeConsole')))
    owner=call(g,'owner','/Script/Engine.ActorComponent:GetOwner',{'self':'self.self'})
    xf=call(g,'transform',KML+':MakeTransform',{},Scale='1,1,1')
    pending=call(g,'spawn',GS+':BeginDeferredActorSpawnFromClass',{'WorldContextObject':'self.self','Owner':owner,'SpawnTransform':xf},ActorClass=CONSOLE,CollisionHandlingOverride='AlwaysSpawn')
    actor=call(g,'finish',GS+':FinishSpawningActor',{'Actor':pending,'SpawnTransform':xf});g.node('cast','cast',**{'class':CONSOLE});g.wire((actor,'cast.Object'))
    set_value(g,'remember','OfficeConsole','cast.AsBP Den Office Console')
    enabled=call(g,'closed',KML+':Not_PreBool',{'A':prop(g,'ui',HOST,'UIOpen',get(g,'Host'))})
    method(g,'update',CONSOLE,'UpdateConsole',get(g,'OfficeConsole'),{'Available':enabled})
    method(g,'consume',CONSOLE,'ConsumeRequest',get(g,'OfficeConsole'));branch(g,'requested','consume.Requested');g.call('request','self:RequestEditorOpen')
    g.chain('entry','exists','update','consume','requested','request');g.chain('exists.else','spawn','finish','cast','remember','update')
    return g.function('UpdateOfficeConsole')


def open_requested():
    g=Graph();branch(g,'requested',get(g,'OpenRequested'));branch(g,'busy',prop(g,'busyvalue',HOST,'Busy',get(g,'Host')));g.set('clear','OpenRequested','false')
    g.call('prepare','self:PrepareLayout');g.wire((get(g,'CampaignID'),'prepare.CampaignID'));branch(g,'prepared','prepare.Accepted')
    g.set('editing',HOST+':Editing','true');g.wire((get(g,'Host'),'editing.self'))
    method(g,'mount',HOST,'MountEditor',get(g,'Host'),{'Player':get(g,'Player')});branch(g,'mounted','mount.Accepted');g.call('noticeclear','self:ClearNotice')
    g.set('closed',HOST+':Editing','false');g.wire((get(g,'Host'),'closed.self'))
    g.call('layoutfailed','self:ShowNotice',Message='Den Designer could not load this layout. Existing files are preserved. Check your mod layout files, then use the opening shortcut to retry.')
    g.call('mountfailed','self:ShowNotice',Message='Den Designer could not open the editor. Your layout is preserved. Try again once the Den has finished loading.')
    g.chain('entry','requested','busy');g.chain('busy.else','clear','prepare','prepared','editing','mount','mounted','noticeclear');g.chain('prepared.else','layoutfailed');g.chain('mounted.else','closed','mountfailed')
    return g.function('OpenRequestedEditor')


def poll_world():
    g=Graph();g.node('self','self');now=clock(g,'now');branch(g,'due',call(g,'time',KML+':GreaterEqual_DoubleDouble',{'A':now,'B':get(g,'NextWorldCheck')}))
    set_value(g,'next','NextWorldCheck',call(g,'later',KML+':Add_DoubleDouble',{'A':now},B=.5))
    level=call(g,'level',GS+':GetCurrentLevelName',{'WorldContextObject':'self.self'},bRemovePrefixString='true');branch(g,'den',call(g,'inDen',STR+'EqualEqual_StrStr',{'A':level},B='HUB_Root'))
    pc=call(g,'player',GS+':GetPlayerController',{'WorldContextObject':'self.self'},PlayerIndex=0);branch(g,'valid',validity(g,'exists',pc));set_value(g,'save','Player',pc)
    pawn=call(g,'pawn',PC+':K2_GetPawn',{'self':pc});branch(g,'pawnvalid',validity(g,'pawnexists',pawn))
    g.call('campaign','self:ReadActiveCampaign');branch(g,'known','campaign.Known')
    changed=call(g,'changed',STR+'NotEqual_StrStr',{'A':'campaign.CampaignID','B':get(g,'CampaignID')});first=call(g,'first',KML+':Not_PreBool',{'A':get(g,'Initialized')})
    branch(g,'initialize',combine(g,'needsinit',[changed,first,call(g,'hostgone',KML+':Not_PreBool',{'A':validity(g,'hostvalid',get(g,'Host'))})],True));g.call('prepare','self:PrepareLayout');g.wire(('campaign.CampaignID','prepare.CampaignID'))
    g.call('leave','self:Shutdown');g.chain('entry','due','next','level','den','valid','save','pawnvalid','campaign','known','initialize','prepare');g.chain('den.else','leave')
    return g.function('PollWorld')


def poll():
    g=Graph();g.node('self','self');g.call('world','self:PollWorld')
    branch(g,'ready',combine(g,'available',[get(g,'Initialized'),validity(g,'host',get(g,'Host')),validity(g,'player',get(g,'Player'))]))
    paused=call(g,'paused',GS+':IsGamePaused',{'WorldContextObject':'self.self'});branch(g,'pause',paused)
    g.call('shortcut','self:UpdateShortcut');method(g,'pressed',SHORTCUT,'Pressed',get(g,'Shortcut'),{'Player':get(g,'Player')});branch(g,'key','pressed.Pressed');g.call('toggle','self:ToggleEditor')
    g.call('console','self:UpdateOfficeConsole');g.call('open','self:OpenRequestedEditor');branch(g,'notice',validity(g,'noticevalid',get(g,'Notice')));branch(g,'expired',call(g,'time',KML+':GreaterEqual_DoubleDouble',{'A':clock(g,'now'),'B':get(g,'NoticeUntil')}));g.call('clear','self:ClearNotice')
    g.chain('entry','world','ready','pause');g.chain('pause.else','shortcut','pressed','key','toggle','console','open','notice','expired','clear');g.chain('key.else','console')
    return g.function('Poll')


def shutdown():
    g=Graph();g.set('pending','OpenRequested','false');g.set('stop','Initialized','false');g.call('notice','self:ClearNotice')
    branch(g,'console',validity(g,'consolevalid',get(g,'OfficeConsole')));call(g,'destroyconsole',ACTOR+':K2_DestroyActor',{'self':get(g,'OfficeConsole')});g.set('consoleclear','OfficeConsole')
    branch(g,'host',validity(g,'valid',get(g,'Host')))
    call(g,'destroy',ACTOR+':K2_DestroyActor',{'self':get(g,'Host')});g.set('clear','Host');g.set('player','Player');g.set('shortcut','Shortcut');g.set('document','ShortcutDocument')
    g.chain('entry','pending','stop','notice','console','destroyconsole','consoleclear','host','destroy','clear','player','shortcut','document');g.chain('host.else','clear');g.chain('console.else','consoleclear')
    return g.function('Shutdown')


def notice_spec():
    import ui_templates as editor
    return dict(kind='widget',path=NOTICE,tree={'class':'/Script/UMG.CanvasPanel','name':'Root','props':{'Visibility':'HitTestInvisible'},'children':[
        {'class':'/Script/UMG.Border','name':'Panel','props':{'BrushColor':editor.PANEL,'Padding':'(Left=20,Top=14,Right=20,Bottom=14)'},'slot':{'LayoutData':'(Anchors=(Minimum=(X=0.5,Y=1),Maximum=(X=0.5,Y=1)),Offsets=(Left=-320,Top=-150,Right=640,Bottom=110))'},'children':[
            editor.text('Message','',16,editor.WHITE,wrap=True)]}]})


def spec():
    g=Graph();g.node('tick','event',name='ReceiveTick');g.call('poll','self:Poll');g.chain('tick','poll')
    g.node('end','event',name='ReceiveEndPlay');g.call('shutdown','self:Shutdown');g.chain('end','shutdown')
    return dict(kind='blueprint',path=COORDINATOR,parent='/Script/Engine.ActorComponent',defaults={'PrimaryComponentTick.bCanEverTick':'true','PrimaryComponentTick.bStartWithTickEnabled':'true'},
        variables=[v('Host','object:'+HOST),v('OfficeConsole','object:'+CONSOLE),v('Player','object:'+PC),v('Shortcut','object:'+SHORTCUT),v('ShortcutDocument','object:'+DOCUMENT),v('CampaignID','string'),v('ResolvedKey','string'),v('LayoutStatus','int'),v('Initialized','bool'),v('OpenRequested','bool'),v('NextWorldCheck','double'),v('Notice','object:'+NOTICE),v('NoticeUntil','double')],
        graph=g.spec(),functions=[campaign_text(),campaign(),ensure_host(),prepare_layout(),update_shortcut(),clear_notice(),show_notice(),toggle(),request_open(),update_console(),open_requested(),poll_world(),poll(),shutdown()])
