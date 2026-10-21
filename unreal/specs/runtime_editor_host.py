"""Native viewport/UI owner layered over BP_DenSession.

This class is not yet the Game Feature entry point. Development callers open a
session then MountEditor; the runtime owns its UI and camera lifecycle.
"""
from graph import Graph, variable as v, KML, KSL, GS, WBL
from runtime import ROOT, arr
from runtime_store import call, branch, combine
from runtime_world import ACTOR, set_value, validity, finish_bool
from runtime_apply import get
from runtime_session import SESSION, prop, method
from runtime_editor_assets import UIROOT, BUS, RIG, TOOLBAR
from runtime_assets import JOB

HOST=ROOT+'BP_DenEditorHost'
PC='/Script/Engine.PlayerController'
CAM='/Script/Engine.PlayerCameraManager'
SUB='/Script/EnhancedInput.EnhancedInputLocalPlayerSubsystem'
SUBINTERFACE='/Script/EnhancedInput.EnhancedInputSubsystemInterface'
WIDGET='/Script/UMG.Widget'
USERWIDGET='/Script/UMG.UserWidget'
PANELS=[('Toolbar','WBP_DenToolbar',50),('Inspector','WBP_DenTransform',45),('CatalogPanel','WBP_DenCatalog',40),('LayoutsPanel','WBP_DenLayouts',40),('StoreroomPanel','WBP_DenStoreroom',40),('SettingsPanel','WBP_DenSettings',40),('CompositionsPanel','WBP_DenCompositions',40)]


def widget_class(variable):return UIROOT+next(cls for var,cls,_ in PANELS if var==variable)


def widget(g,node,panel,field):return prop(g,node,widget_class(panel),field,get(g,panel))


def text(g,node,panel,field,value=None,constant=None):
    obj=widget(g,node+'widget',panel,field)
    return call(g,node,'/Script/UMG.TextBlock:SetText',{'self':obj,**({'InText':value} if value else {})},**({'InText':constant} if constant is not None else {}))


def visibility(g,node,obj,mode):return call(g,node,WIDGET+':SetVisibility',{'self':obj},InVisibility=mode)


def create_panels():
    from runtime_editor_assets import text_fields
    g=Graph();g.node('self','self');previous='entry'
    for var,cls,order in PANELS:
        obj=call(g,'create'+var,WBL+':Create',{'WorldContextObject':'self.self','OwningPlayer':get(g,'EditorController')},WidgetType=UIROOT+cls)
        g.node('cast'+var,'cast',**{'class':UIROOT+cls});g.wire((obj,'cast'+var+'.Object'))
        castpin='cast'+var+'.As'+{'WBP_DenToolbar':'WBP Den Toolbar','WBP_DenTransform':'WBP Den Transform','WBP_DenCatalog':'WBP Den Catalog','WBP_DenLayouts':'WBP Den Layouts','WBP_DenStoreroom':'WBP Den Storeroom','WBP_DenSettings':'WBP Den Settings','WBP_DenCompositions':'WBP Den Compositions'}[cls]
        set_value(g,'save'+var,var,castpin)
        set_value(g,'bus'+var,UIROOT+cls+':EditorBus',get(g,'InputBus'));g.wire((get(g,var),'bus'+var+'.self'))
        call(g,'show'+var,USERWIDGET+':AddToViewport',{'self':get(g,var)},ZOrder=order)
        visibility(g,'visible'+var,get(g,var),'SelfHitTestInvisible' if var in ['Toolbar','Inspector'] else 'Collapsed')
        g.chain(previous,'create'+var,'cast'+var,'save'+var,'bus'+var,'show'+var,'visible'+var)
        g.chain('cast'+var+'.CastFailed','result');previous='visible'+var
        for field in text_fields(cls):
            name='register'+var+field
            method(g,name,BUS,'RegisterTextInput',get(g,'InputBus'),{'Widget':widget(g,name+'widget',var,field)})
            g.chain(previous,name);previous=name
    g.call('help','self:RefreshEditorHelp')
    g.set('yes','local:OK','true');finish_bool(g)
    g.chain(previous,'help','yes','result')
    return g.function('CreateEditorPanels',outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def mount():
    g=Graph();g.node('self','self')
    closed=call(g,'closed',KML+':Not_PreBool',{'A':get(g,'UIOpen')})
    branch(g,'available',combine(g,'allowed',[get(g,'Editing'),closed,validity(g,'pcvalid','entry.Player')]))
    level=call(g,'level',GS+':GetCurrentLevelName',{'WorldContextObject':'self.self'},bRemovePrefixString='true')
    from runtime_store import STR
    branch(g,'den',call(g,'dencheck',STR+'EqualEqual_StrStr',{'A':level},B='HUB_Root'))
    manager=prop(g,'manager',PC,'PlayerCameraManager','entry.Player');branch(g,'camera',validity(g,'cameravalid',manager))
    sub=call(g,'sub','/Script/Engine.SubsystemBlueprintLibrary:GetLocalPlayerSubSystemFromPlayerController',{'PlayerController':'entry.Player'},Class=SUB)
    g.node('subcast','cast',**{'class':SUB});g.wire((sub,'subcast.Object'))
    set_value(g,'subsave','InputSubsystem','subcast.AsEnhanced Input Local Player Subsystem')
    set_value(g,'player','EditorController','entry.Player')
    view=call(g,'view',PC+':GetViewTarget',{'self':'entry.Player'});set_value(g,'viewcopy','PreviousView',view)
    capture=[]
    for var,field in [('PreviousCursor','bShowMouseCursor'),('PreviousClicks','bEnableClickEvents'),('PreviousHover','bEnableMouseOverEvents')]:
        value=prop(g,'read'+var,PC,field,'entry.Player');set_value(g,'copy'+var,var,value);capture.append('copy'+var)
    g.set('captured','ControllerCaptured','true')
    bus=call(g,'buscreate',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=BUS)
    g.node('buscast','cast',**{'class':BUS});g.wire((bus,'buscast.Object'));set_value(g,'bussave','InputBus','buscast.AsBP Den Editor Bus')
    at=call(g,'at',CAM+':GetCameraLocation',{'self':manager});rot=call(g,'rot',CAM+':GetCameraRotation',{'self':manager})
    xf=call(g,'transform',KML+':MakeTransform',{'Location':at,'Rotation':rot},Scale='1,1,1')
    pending=call(g,'spawn',GS+':BeginDeferredActorSpawnFromClass',{'WorldContextObject':'self.self','Owner':'self.self','SpawnTransform':xf},ActorClass=RIG,CollisionHandlingOverride='AlwaysSpawn')
    rig=call(g,'finish',GS+':FinishSpawningActor',{'Actor':pending,'SpawnTransform':xf})
    g.node('rigcast','cast',**{'class':RIG});g.wire((rig,'rigcast.Object'));set_value(g,'rigsave','EditorRig','rigcast.AsBP Den Editor Rig')
    set_value(g,'rigbus',RIG+':EditorBus',get(g,'InputBus'));g.wire((get(g,'EditorRig'),'rigbus.self'))
    g.call('panels','self:CreateEditorPanels');branch(g,'created','panels.Accepted')
    method(g,'startbus',BUS,'Start',get(g,'InputBus'))
    call(g,'enable',ACTOR+':EnableInput',{'self':get(g,'EditorRig'),'PlayerController':'entry.Player'})
    g.call('preferences','self:ReadEditorPreferences');g.call('applypreferences','self:ApplyEditorPreferences')
    g.call('mapping','self:InstallEditorMappings');branch(g,'mapped','mapping.Accepted')
    setters=[]
    for field,val in [('bEnableClickEvents','false'),('bEnableMouseOverEvents','false'),('bShowMouseCursor','true')]:
        g.set('set'+field,PC+':'+field,val);g.wire(('entry.Player','set'+field+'.self'));setters.append('set'+field)
    call(g,'target',PC+':SetViewTargetWithBlend',{'self':'entry.Player','NewViewTarget':get(g,'EditorRig')},BlendTime=0,BlendFunc='VTBlend_Linear')
    current=call(g,'current',PC+':GetViewTarget',{'self':'entry.Player'})
    branch(g,'accepted',call(g,'match',KML+':EqualEqual_ObjectObject',{'A':current,'B':get(g,'EditorRig')}))
    call(g,'mode',WBL+':SetInputMode_GameAndUIEx',{'PlayerController':'entry.Player'},InMouseLockMode='DoNotLock',bHideCursorDuringCapture='false',bFlushInput='false')
    g.set('open','UIOpen','true');g.set('fontindex','FontIndex','0');g.set('confirmreset','ConfirmMode','0');g.set('panelreset','ActivePanel','');g.set('helpreset','HelpOpen','false')
    g.call('selection','self:InitializeSelection');g.call('gizmo','self:InitializeEditorGizmo');g.call('refresh','self:RefreshEditorUI');g.call('recovery','self:OfferRecovery');g.set('yes','local:OK','true');finish_bool(g)
    g.call('cleanup','self:DetachEditor',RestoreView='true')
    g.chain('entry','available','level','den','camera','subcast','subsave','player','viewcopy',*capture,'captured','buscreate','buscast','bussave','spawn','finish','rigcast','rigsave','rigbus','preferences','applypreferences','panels','created','startbus','enable','mapping','mapped',*setters,'target','accepted','mode','open','fontindex','confirmreset','panelreset','helpreset','selection','gizmo','refresh','recovery','yes','result')
    for pin in ['available.else','den.else','camera.else','subcast.CastFailed']:g.chain(pin,'result')
    for pin in ['buscast.CastFailed','rigcast.CastFailed','created.else','mapped.else','accepted.else']:g.chain(pin,'cleanup','result')
    return g.function('MountEditor',inputs=[v('Player','object:'+PC)],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def detach():
    g=Graph();g.call('compositionparts','self:ClearCompositionSelection');g.call('compositionpreview','self:CancelCompositionPreview');g.call('stored','self:ClearStoreroomListing');g.call('thumbs','self:ReleaseThumbnails');g.call('placement','self:CancelPlacement');g.call('queue','self:ClearEditorMutations');g.call('catalog','self:ReleaseCatalog');g.call('gizmo','self:DestroyEditorGizmo');g.call('selection','self:ClearSelection');g.call('mappings','self:ReleaseEditorMappings');g.chain('entry','compositionparts','compositionpreview','stored','thumbs','placement','queue','catalog','gizmo','selection','mappings');previous='mappings'
    operations=[('bus','InputBus',BUS+':Stop',{}),('riginput','EditorRig',ACTOR+':DisableInput',{})]
    for name,var,fn,defaults in operations:
        branch(g,name+'valid',validity(g,name+'check',get(g,var)));call(g,name,fn,dict({'self':get(g,var)},**({'PlayerController':get(g,'EditorController')} if name=='riginput' else {})),**defaults)
        g.node(name+'next','sequence',outputs=1);g.chain(previous,name+'valid',name,name+'next');g.chain(name+'valid.else',name+'next');previous=name+'next.then_0'
    for var,_,_ in PANELS:
        branch(g,var+'valid',validity(g,var+'check',get(g,var)));call(g,'remove'+var,WIDGET+':RemoveFromParent',{'self':get(g,var)})
        g.set('clear'+var,var);g.chain(previous,var+'valid','remove'+var,'clear'+var);g.chain(var+'valid.else','clear'+var);previous='clear'+var
    branch(g,'player',combine(g,'hasplayer',[get(g,'ControllerCaptured'),validity(g,'pcvalid',get(g,'EditorController'))]))
    fields=[]
    for var,field in [('PreviousCursor','bShowMouseCursor'),('PreviousClicks','bEnableClickEvents'),('PreviousHover','bEnableMouseOverEvents')]:
        set_value(g,'restore'+var,PC+':'+field,get(g,var));g.wire((get(g,'EditorController'),'restore'+var+'.self'));fields.append('restore'+var)
    branch(g,'view',combine(g,'restoreview',['entry.RestoreView',validity(g,'viewvalid',get(g,'PreviousView'))]))
    call(g,'target',PC+':SetViewTargetWithBlend',{'self':get(g,'EditorController'),'NewViewTarget':get(g,'PreviousView')},BlendTime=0.3,BlendFunc='VTBlend_Linear')
    branch(g,'inputmode','entry.RestoreView');branch(g,'cursor',get(g,'PreviousCursor'))
    call(g,'ui',WBL+':SetInputMode_GameAndUIEx',{'PlayerController':get(g,'EditorController')},InMouseLockMode='DoNotLock',bHideCursorDuringCapture='false',bFlushInput='false')
    call(g,'game',WBL+':SetInputMode_GameOnly',{'PlayerController':get(g,'EditorController')},bFlushInput='false')
    g.node('release','sequence',outputs=1)
    g.chain(previous,'player',*fields,'view','target','inputmode','cursor','ui','release');g.chain('view.else','inputmode');g.chain('cursor.else','game','release');g.chain('inputmode.else','release');g.chain('player.else','release')
    previous='release.then_0'
    for var in ['EditorRig','FontJob']:
        branch(g,var+'valid',validity(g,var+'check',get(g,var)));call(g,'destroy'+var,ACTOR+':K2_DestroyActor',{'self':get(g,var)})
        g.set('clear'+var,var);g.chain(previous,var+'valid','destroy'+var,'clear'+var);g.chain(var+'valid.else','clear'+var);previous='clear'+var
    tail=[]
    for var in ['EditorController','PreviousView','InputSubsystem','InputBus']:
        g.set('clear'+var,var);tail.append('clear'+var)
    for var in ['UIOpen','ControllerCaptured','Looking']:
        g.set('stop'+var,var,'false');tail.append('stop'+var)
    g.chain(previous,*tail)
    return g.function('DetachEditor',inputs=[v('RestoreView','bool')])


def look():
    g=Graph();branch(g,'available',combine(g,'valid',[get(g,'UIOpen'),validity(g,'player',get(g,'EditorController'))]))
    nomodal=call(g,'nomodal',KML+':EqualEqual_IntInt',{'A':get(g,'ConfirmMode')},B=0)
    value=combine(g,'capture',['entry.Held',nomodal]);set_value(g,'remember','Looking',value)
    branch(g,'held',get(g,'Looking'))
    for name,val in [('hide','false'),('show','true')]:
        g.set(name,PC+':bShowMouseCursor',val);g.wire((get(g,'EditorController'),name+'.self'))
    call(g,'game',WBL+':SetInputMode_GameOnly',{'PlayerController':get(g,'EditorController')},bFlushInput='false')
    call(g,'ui',WBL+':SetInputMode_GameAndUIEx',{'PlayerController':get(g,'EditorController')},InMouseLockMode='DoNotLock',bHideCursorDuringCapture='false',bFlushInput='false')
    g.chain('entry','available','remember','held','hide','game');g.chain('held.else','show','ui')
    return g.function('SetLooking',inputs=[v('Held','bool')])


def keep_camera():
    g=Graph();branch(g,'open',combine(g,'valid',[get(g,'UIOpen'),validity(g,'player',get(g,'EditorController')),validity(g,'rig',get(g,'EditorRig'))]))
    current=call(g,'current',PC+':GetViewTarget',{'self':get(g,'EditorController')})
    branch(g,'different',call(g,'changed',KML+':NotEqual_ObjectObject',{'A':current,'B':get(g,'EditorRig')}))
    call(g,'target',PC+':SetViewTargetWithBlend',{'self':get(g,'EditorController'),'NewViewTarget':get(g,'EditorRig')},BlendTime=0,BlendFunc='VTBlend_Linear')
    g.chain('entry','open','different','target')
    return g.function('KeepEditorCamera')


def spec():
    from runtime_compositions import functions as composition_functions, variables as composition_variables
    from runtime_composition_library import functions as composition_library_functions, variables as composition_library_variables
    from runtime_composition_preview import functions as composition_preview_functions, variables as composition_preview_variables
    from runtime_editor_commands import functions as command_functions
    from runtime_editor_fonts import functions as font_functions
    from runtime_selection import functions as selection_functions, variables as selection_variables
    from runtime_transform import functions as transform_functions
    from runtime_edit_queue import functions as queue_functions, variables as queue_variables
    from runtime_drag import functions as drag_functions, variables as drag_variables
    from runtime_gizmo_controller import functions as gizmo_functions, variables as gizmo_variables
    from runtime_surface import functions as surface_functions, variables as surface_variables
    from runtime_copy import functions as copy_functions, variables as copy_variables
    from runtime_catalog_ui import functions as catalog_functions, variables as catalog_variables
    from runtime_placement import functions as placement_functions, variables as placement_variables
    from runtime_thumbnail_ui import functions as thumbnail_functions, variables as thumbnail_variables
    from runtime_storeroom import functions as storeroom_functions, variables as storeroom_variables
    from runtime_layout_ui import functions as layout_ui_functions, variables as layout_ui_variables
    from runtime_scope_ui import functions as scope_ui_functions, variables as scope_ui_variables
    from runtime_preference_ui import functions as preference_functions, variables as preference_variables
    from runtime_settings_ui import functions as settings_functions, variables as settings_variables
    from runtime_input_ui import functions as input_functions, variables as input_variables
    g=Graph();g.node('tick','event',name='ReceiveTick')
    for name,fn in [('pump','Pump'),('draft','PollDraft'),('events','ProcessEditorEvents'),('catalog','PollCatalogUI'),('storeroom','PollStoreroomUI'),('thumbnails','PollThumbnailUI'),('placement','PollPlacement'),('compositionpreview','PollCompositionPreview'),('drag','PollSelectionDrag'),('selection','PollSelection'),('copy','PollCopiedSelection'),('surface','PollSurfaceDrag'),('gizmo','PollEditorGizmo'),('edits','PumpEditorMutations'),('camera','KeepEditorCamera'),('fonts','PollEditorFonts'),('refresh','PollEditorUI')]:g.call(name,'self:'+fn)
    g.chain('tick','pump','draft','events','catalog','storeroom','thumbnails','placement','compositionpreview','drag','selection','copy','surface','gizmo','edits','camera','fonts','refresh')
    g.node('end','event',name='ReceiveEndPlay');g.call('flush','self:FlushDraft');g.set('close','Editing','false')
    g.call('detach','self:DetachEditor',RestoreView='false');g.call('cancel','self:CancelWork');g.call('forget','self:Forget');g.chain('end','flush','close','detach','cancel','forget')
    variables=[v('EditorController','object:'+PC),v('PreviousView','object:'+ACTOR),v('EditorRig','object:'+RIG),v('InputSubsystem','object:'+SUB),v('InputBus','object:'+BUS),
        v('FontJob','object:'+JOB),v('FontRequestAt','double'),v('FontIndex','int'),v('UIOpen','bool'),v('ControllerCaptured','bool'),v('PreviousCursor','bool'),v('PreviousClicks','bool'),v('PreviousHover','bool'),
        v('Looking','bool'),v('ActivePanel','string'),v('HelpOpen','bool'),v('ConfirmMode','int'),v('GridIndex','int'),v('ReachIndex','int','1'),v('GridStep','double','0'),v('ReachCm','double','2000'),
        v('StructureEnabled','bool','false'),v('FloorsEnabled','bool','true'),v('WallsEnabled','bool','false'),v('LastUIBusy','bool'),v('LastUIDraftStatus','int','-1'),v('UnhandledCommands','int'),v('LastUnhandled','string')]
    variables += composition_variables()+composition_library_variables()+composition_preview_variables()+selection_variables()+queue_variables()+drag_variables()+gizmo_variables()+surface_variables()+copy_variables()+catalog_variables()+placement_variables()+thumbnail_variables()+storeroom_variables()+layout_ui_variables()+scope_ui_variables()+preference_variables()+input_variables()+settings_variables()
    variables += [v(var,'object:'+UIROOT+cls) for var,cls,_ in PANELS]
    return dict(kind='blueprint',path=HOST,parent=SESSION,variables=variables,graph=g.spec(),functions=[create_panels(),mount(),detach(),look(),keep_camera(),*composition_functions(),*composition_library_functions(),*composition_preview_functions(),*command_functions(),*font_functions(),*selection_functions(),*transform_functions(),*queue_functions(),*drag_functions(),*gizmo_functions(),*surface_functions(),*copy_functions(),*catalog_functions(),*placement_functions(),*thumbnail_functions(),*storeroom_functions(),*layout_ui_functions(),*scope_ui_functions(),*preference_functions(),*input_functions(),*settings_functions()])
