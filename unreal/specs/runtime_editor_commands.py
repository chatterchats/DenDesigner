"""Native toolbar/navigation/session commands. Selection commands are added next."""
from graph import Graph, variable as v, KML
from runtime import arr, unpack
from runtime_store import call, branch, combine, STR
from runtime_world import set_value, validity
from runtime_apply import get, bump
from runtime_session import HISTORY, LAYOUT, prop, method
from runtime_editor_assets import EVENT, BUS, RIG
from runtime_editor_host import PANELS, WIDGET, WBL, text, widget, visibility, style_toggle
import ui_templates as editor


def set_panel():
    g=Graph();branch(g,'panelopen',call(g,'nonempty',STR+'NotEqual_StrStr',{'A':'entry.Name'},B=''));g.call('cancelplacement','self:CancelPlacement');set_value(g,'remember','ActivePanel','entry.Name');previous='remember'
    for var,name in [('CatalogPanel','catalog'),('LayoutsPanel','layouts'),('StoreroomPanel','storeroom'),('SettingsPanel','settings'),('CompositionsPanel','compositions')]:
        branch(g,var+'valid',validity(g,var+'check',get(g,var)))
        branch(g,var+'selected',call(g,var+'same',STR+'EqualEqual_StrStr',{'A':'entry.Name'},B=name))
        visibility(g,var+'show',get(g,var),'SelfHitTestInvisible');visibility(g,var+'hide',get(g,var),'Collapsed')
        g.node(var+'next','sequence',outputs=1)
        g.chain(previous,var+'valid',var+'selected',var+'show',var+'next');g.chain(var+'selected.else',var+'hide',var+'next');g.chain(var+'valid.else',var+'next');previous=var+'next.then_0'
    g.call('catalog','self:CatalogPanelChanged');g.call('storeroom','self:StoreroomPanelChanged');g.call('layouts','self:LayoutsPanelChanged');g.call('settings','self:SettingsPanelChanged');g.call('compositions','self:CompositionsPanelChanged');g.chain(previous,'catalog','storeroom','layouts','settings','compositions');branch(g,'keepcomposition',call(g,'compositionpanel',STR+'EqualEqual_StrStr',{'A':'entry.Name'},B='compositions'));g.call('clearcomposition','self:ClearCompositionSelection');g.chain('compositions','keepcomposition');g.chain('keepcomposition.else','clearcomposition')
    g.call('compositioncancel','self:CancelCompositionPreview');g.chain('entry','panelopen','cancelplacement','compositioncancel','remember');g.chain('panelopen.else','remember')
    # Settings take the inspector dock's place while open.
    g.call('inspector','self:RefreshSelectionUI');g.chain('keepcomposition','inspector');g.chain('clearcomposition','inspector')
    return g.function('SetEditorPanel',inputs=[v('Name','string')])


def toggle_panel():
    g=Graph();branch(g,'same',call(g,'equal',STR+'EqualEqual_StrStr',{'A':get(g,'ActivePanel'),'B':'entry.Name'}))
    g.call('clear','self:SetEditorPanel',Name='');g.call('select','self:SetEditorPanel');g.wire(('entry.Name','select.Name'))
    g.chain('entry','same','clear');g.chain('same.else','select')
    return g.function('ToggleEditorPanel',inputs=[v('Name','string')])


def confirm():
    g=Graph();set_value(g,'mode','ConfirmMode','entry.Mode');g.call('release','self:SetLooking',Held='false')
    branch(g,'rigvalid',validity(g,'rigcheck',get(g,'EditorRig')))
    none=call(g,'none',KML+':EqualEqual_IntInt',{'A':'entry.Mode'},B=0)
    set_value(g,'controls',RIG+':ControlsEnabled',none);g.wire((get(g,'EditorRig'),'controls.self'))
    branch(g,'toolbar',validity(g,'tcheck',get(g,'Toolbar')));visibility(g,'discardvisible',widget(g,'discardbutton','Toolbar','ConfirmDiscard'),'Visible')
    confirmwidget=widget(g,'confirm','Toolbar','Confirm');branch(g,'hidden',none)
    visibility(g,'hide',confirmwidget,'Collapsed');visibility(g,'show',confirmwidget,'Visible')
    branch(g,'exit',call(g,'exitmode',KML+':EqualEqual_IntInt',{'A':'entry.Mode'},B=1))
    previous='exit'
    for name,field,value in [('exitTitle','ConfirmTitle','Save your Den changes?'),('exitText','ConfirmText','Save to keep this layout, or discard to restore your last save.'),('exitSave','ConfirmSaveLabel','Save'),('exitDiscard','ConfirmDiscardLabel','Discard'),('exitCancel','ConfirmCancelLabel','Keep editing')]:
        text(g,name,'Toolbar',field,constant=value);g.chain(previous,name);previous=name
    g.node('finish','sequence',outputs=1);g.chain(previous,'finish')
    previous='exit.else'
    for name,field,value in [('recoveryTitle','ConfirmTitle','Recover your previous edits?'),('recoverySave','ConfirmSaveLabel','Recover'),('recoveryDiscard','ConfirmDiscardLabel','Discard draft'),('recoveryCancel','ConfirmCancelLabel','Not now')]:
        text(g,name,'Toolbar',field,constant=value);g.chain(previous,name);previous=name
    branch(g,'matching',call(g,'matchmode',KML+':EqualEqual_IntInt',{'A':'entry.Mode'},B=2));g.chain(previous,'matching')
    text(g,'matchingText','Toolbar','ConfirmText',constant='A draft from your last editing session is available.');g.chain('matching','matchingText','finish')
    branch(g,'corrupt',call(g,'corruptmode',KML+':EqualEqual_IntInt',{'A':'entry.Mode'},B=4))
    text(g,'mismatchText','Toolbar','ConfirmText',constant='This draft has a different or unknown saved baseline. Recover it only if you want to use its contents.')
    text(g,'corruptText','Toolbar','ConfirmText',constant='The draft could not be read. Keep it for recovery, or explicitly discard it before editing.')
    g.chain('matching.else','corrupt','corruptText','finish');g.chain('corrupt.else','mismatchText','finish')
    recoverable=call(g,'recoverable',KML+':NotEqual_IntInt',{'A':'entry.Mode'},B=4)
    savebutton=widget(g,'savebutton','Toolbar','ConfirmSave');call(g,'enable',WIDGET+':SetIsEnabled',{'self':savebutton,'bInIsEnabled':recoverable});g.chain('finish.then_0','enable')
    g.chain('entry','mode','release','rigvalid','controls','toolbar','discardvisible','hidden','hide');g.chain('rigvalid.else','toolbar');g.chain('hidden.else','show','exit')
    return g.function('SetEditorConfirm',inputs=[v('Mode','int')])


def offer_recovery():
    g=Graph();branch(g,'pending',get(g,'RecoveryPending'));branch(g,'valid',validity(g,'validdoc',get(g,'RecoveryDocument')))
    branch(g,'matches',get(g,'RecoveryMatchesBase'))
    for name,mode in [('matched',2),('unknown',3),('broken',4)]:g.call(name,'self:SetEditorConfirm',Mode=mode)
    g.chain('entry','pending','valid','matches','matched');g.chain('matches.else','unknown');g.chain('valid.else','broken')
    return g.function('OfferRecovery')


def exit_editor():
    g=Graph();branch(g,'recovery',get(g,'RecoveryPending'));g.call('offer','self:OfferRecovery')
    method(g,'dirty',HISTORY,'IsDirty',get(g,'History'));branch(g,'changed','dirty.Dirty')
    g.call('confirm','self:SetEditorConfirm',Mode=1);g.set('close','Editing','false');g.call('detach','self:DetachEditor',RestoreView='true')
    g.chain('entry','recovery','offer');g.chain('recovery.else','dirty','changed','confirm');g.chain('changed.else','close','detach')
    return g.function('RequestEditorExit')


def back():
    g=Graph();branch(g,'modal',call(g,'hasmodal',KML+':Greater_IntInt',{'A':get(g,'ConfirmMode')},B=0))
    branch(g,'drag',get(g,'DragActive'));g.call('dragcancel','self:EndSelectionDrag',Commit='false')
    g.call('cancel','self:EditorConfirmCancel')
    branch(g,'help',get(g,'HelpOpen'));g.call('hidehelp','self:ToggleEditorHelp')
    branch(g,'panel',call(g,'haspanel',STR+'NotEqual_StrStr',{'A':get(g,'ActivePanel')},B=''))
    g.call('hidepanel','self:SetEditorPanel',Name='');g.call('exit','self:RequestEditorExit')
    branch(g,'placement',get(g,'PlacementActive'));g.call('cancelplacement','self:CancelPlacement');branch(g,'composition',get(g,'CompositionPlacing'));g.call('compositioncancel','self:CancelCompositionPreview');arr(g,'partcount','Length',get(g,'CompositionParts'));branch(g,'parts',combine(g,'collecting',[get(g,'CompositionSelecting'),call(g,'anyparts',KML+':Greater_IntInt',{'A':'partcount.ReturnValue'},B=0)],True));g.call('partsclear','self:ClearCompositionSelection');branch(g,'compositionmodal',call(g,'compositionmodalcheck',KML+':Greater_IntInt',{'A':get(g,'ConfirmMode')},B=0));g.chain('entry','compositionmodal','modal');g.chain('compositionmodal.else','composition','compositioncancel');g.chain('composition.else','parts','partsclear');g.chain('parts.else','placement','cancelplacement');g.chain('placement.else','drag','dragcancel');g.chain('drag.else','modal','cancel');g.chain('modal.else','help','hidehelp');branch(g,'selected',get(g,'HasSelection'));g.call('deselect','self:ClearSelection');g.chain('help.else','selected','deselect');g.chain('selected.else','panel','hidepanel');g.chain('panel.else','exit')
    return g.function('EditorBack')


def confirm_choice(which):
    g=Graph();branch(g,'modal',call(g,'hasmodal',KML+':Greater_IntInt',{'A':get(g,'ConfirmMode')},B=0));branch(g,'recovery',get(g,'RecoveryPending'))
    branch(g,'layoutmode',call(g,'islayout',KML+':EqualEqual_IntInt',{'A':get(g,'ConfirmMode')},B=5));g.chain('entry','modal','layoutmode');g.chain('layoutmode.else','recovery')
    if which=='save':
        g.call('layoutconfirm','self:ConfirmLayoutAction');g.chain('layoutmode','layoutconfirm')
    else:
        g.set('layoutcancel','PendingLayoutAction','');g.call('layoutclear','self:SetEditorConfirm',Mode=0);g.chain('layoutmode','layoutcancel','layoutclear')
    if which=='cancel':
        g.set('close','Editing','false');g.call('detach','self:DetachEditor',RestoreView='true');g.call('clear','self:SetEditorConfirm',Mode=0)
        g.chain('recovery','close','detach');g.chain('recovery.else','clear')
    else:
        g.call('recoverychoice','self:'+('RecoverDraft' if which=='save' else 'DiscardRecovery'),**({'AcceptMismatchedBase':'true'} if which=='save' else {}))
        branch(g,'accepted','recoverychoice.Accepted');g.call('clear','self:SetEditorConfirm',Mode=0)
        g.call('close','self:CloseSession',SaveChanges='true' if which=='save' else 'false');branch(g,'closed','close.Accepted');g.call('detach','self:DetachEditor',RestoreView='true')
        g.chain('recovery','recoverychoice','accepted','clear');g.chain('recovery.else','close','closed','detach')
    return g.function('EditorConfirm'+which.title())


def help_toggle():
    g=Graph();value=call(g,'not',KML+':Not_PreBool',{'A':get(g,'HelpOpen')});set_value(g,'toggle','HelpOpen',value)
    branch(g,'valid',validity(g,'check',get(g,'Toolbar')));branch(g,'show',get(g,'HelpOpen'))
    obj=widget(g,'help','Toolbar','HelpPanel');visibility(g,'visible',obj,'Visible');visibility(g,'hidden',obj,'Collapsed')
    g.chain('entry','toggle','valid','show','visible');g.chain('show.else','hidden')
    return g.function('ToggleEditorHelp')


def focus_viewport():
    g=Graph();branch(g,'open',combine(g,'available',[get(g,'UIOpen'),validity(g,'player',get(g,'EditorController'))]))
    method(g,'typing',BUS,'IsTyping',get(g,'InputBus'));branch(g,'focused','typing.Typing')
    call(g,'viewport',WBL+':SetFocusToGameViewport')
    g.chain('entry','open','typing','focused');g.chain('focused.else','viewport')
    return g.function('FocusEditorViewport')


def cycle(grid):
    g=Graph();index='GridIndex' if grid else 'ReachIndex';field='GridStep' if grid else 'ReachCm';values=[0,5,10,25,50] if grid else [1000,2000,4000,10000]
    step=call(g,'next',KML+':Add_IntInt',{'A':get(g,index)},B=1);wrapped=call(g,'wrapped',KML+':Percent_IntInt',{'A':step},B=len(values));set_value(g,'index',index,wrapped)
    previous='index'
    for i,value in enumerate(values):
        branch(g,'choice'+str(i),call(g,'is'+str(i),KML+':EqualEqual_IntInt',{'A':get(g,index)},B=i));g.set('set'+str(i),field,str(value))
        g.chain(previous,'choice'+str(i),'set'+str(i));previous='choice'+str(i)+'.else'
    g.chain('entry','index')
    return g.function('CycleEditorGrid' if grid else 'CycleEditorReach')


def toggle_style():
    # The active backing, icon and caption colours match ui_templates (ACTIVE_BACK, ACCENT, SOFT).
    g=Graph();previous='entry'
    back=call(g,'backcolor',KML+':SelectColor',{'bPickA':'entry.On'},A=editor.ACTIVE_BACK,B=editor.CLEAR)
    tint=call(g,'tint',KML+':SelectColor',{'bPickA':'entry.On'},A=editor.rgba(*editor.ACCENT),B=editor.rgba(*editor.SOFT_RGB))
    for part,fn,pin,value in [('Back','/Script/UMG.Border:SetBrushColor','InBrushColor',back),('Icon','/Script/UMG.Image:SetColorAndOpacity','InColorAndOpacity',tint)]:
        branch(g,part+'valid',validity(g,part+'check','entry.'+part));call(g,part+'set',fn,{'self':'entry.'+part,pin:value})
        g.node(part+'next','sequence',outputs=1);g.chain(previous,part+'valid',part+'set',part+'next');g.chain(part+'valid.else',part+'next');previous=part+'next.then_0'
    g.node('slate','make_struct',struct='/Script/SlateCore.SlateColor');g.wire((tint,'slate.SpecifiedColor'))
    branch(g,'labelvalid',validity(g,'labelcheck','entry.Label'))
    call(g,'labelset','/Script/UMG.TextBlock:SetColorAndOpacity',{'self':'entry.Label','InColorAndOpacity':'slate.SlateColor'})
    g.chain(previous,'labelvalid','labelset')
    return g.function('StyleEditorToggle',inputs=[v('Back','object:/Script/UMG.Border'),v('Icon','object:/Script/UMG.Image'),v('Label','object:/Script/UMG.TextBlock'),v('On','bool')])


def handle():
    g=Graph();unpack(g,'event',EVENT,'entry.Event')
    branch(g,'look',call(g,'lookname',STR+'EqualEqual_StrStr',{'A':'event.EventName'},B='look_hold'))
    held=call(g,'held',KML+':Greater_DoubleDouble',{'A':'event.Scalar'},B=.5);g.call('looking','self:SetLooking');g.wire((held,'looking.Held'))
    previous='look.else'
    commands=[('confirm_save','EditorConfirmSave',{}),('confirm_discard','EditorConfirmDiscard',{}),('confirm_cancel','EditorConfirmCancel',{}),('back','EditorBack',{})]
    normal=[('rotation_pivot','CycleEditorSetting',{'Key':'rotation_pivot'}),('compositions','ToggleEditorPanel',{'Name':'compositions'}),('composition_select','ToggleCompositionSelection',{}),('composition_clear','ClearCompositionSelection',{}),('settings','ToggleEditorPanel',{'Name':'settings'}),('settings_close','SetEditorPanel',{'Name':''}),('settings_reset','ChangeEditorSetting',{'Reset':'true'}),('catalog','ToggleEditorPanel',{'Name':'catalog'}),('layouts','ToggleEditorPanel',{'Name':'layouts'}),('storeroom','ToggleEditorPanel',{'Name':'storeroom'}),('help','ToggleEditorHelp',{}),('snap','CycleEditorGrid',{}),('reach','CycleEditorReach',{}),('numeric_done','FocusEditorViewport',{}),('mode_select','SetGizmoMode',{'Mode':0}),('mode_move','SetGizmoMode',{'Mode':1}),('mode_rotate','SetGizmoMode',{'Mode':2}),('mode_scale','SetGizmoMode',{'Mode':3}),('gimbal','CycleGizmoMode',{})]
    for i,(name,fn,defaults) in enumerate(commands+normal):
        if i==len(commands):
            branch(g,'modal',call(g,'ismodal',KML+':Greater_IntInt',{'A':get(g,'ConfirmMode')},B=0));g.chain(previous,'modal');branch(g,'select',call(g,'selectname',STR+'EqualEqual_StrStr',{'A':'event.EventName'},B='select'));g.call('pick','self:GizmoPointerButton');g.wire(('event.Scalar','pick.Value'));branch(g,'placing',get(g,'PlacementActive'));g.call('place','self:PlacementPointerButton');g.wire(('event.Scalar','place.Value'));branch(g,'composing',get(g,'CompositionPlacing'));g.call('composeclick','self:CompositionPointerButton');g.wire(('event.Scalar','composeclick.Value'));g.chain('modal.else','select','composing','composeclick');g.chain('composing.else','placing','place');g.chain('placing.else','pick');previous='select.else'
        branch(g,'name'+str(i),call(g,'eq'+str(i),STR+'EqualEqual_StrStr',{'A':'event.EventName'},B=name));g.call('call'+str(i),'self:'+fn,**defaults)
        g.chain(previous,'name'+str(i),'call'+str(i));previous='name'+str(i)+'.else'
    from runtime_settings_widget import NUMERIC_LABELS,KEY_LABELS
    for i,key in enumerate([*NUMERIC_LABELS,*KEY_LABELS]):
        node='setting'+str(i);branch(g,node,call(g,node+'eq',STR+'EqualEqual_StrStr',{'A':'event.EventName'},B='setting:'+key))
        g.call(node+'apply','self:ChangeEditorSetting',Key=key,Reset='false');g.wire(('event.Argument',node+'apply.Value'))
        g.chain(previous,node,node+'apply');previous=node+'.else'
    branch(g,'cycle_setting',call(g,'cycle_setting_eq',STR+'EqualEqual_StrStr',{'A':'event.EventName'},B='setting_cycle'))
    g.call('cycle_setting_run','self:CycleEditorSetting');g.wire(('event.Argument','cycle_setting_run.Key'));g.chain(previous,'cycle_setting','cycle_setting_run');previous='cycle_setting.else'
    for name,fn,pin in [('search','SearchCatalog','Text'),('shelf','ChooseCatalogShelf','Key'),('item','ChooseCatalogItem','Key'),('stored_search','SearchStoreroom','Text'),('preset','SelectPresetCard','Key'),('composition_card','SelectCompositionCard','Key')]:
        node='catalog'+name;branch(g,node,call(g,node+'name',STR+'EqualEqual_StrStr',{'A':'event.EventName'},B=name))
        g.call(node+'run','self:'+fn);g.wire(('event.Argument',node+'run.'+pin));g.chain(previous,node,node+'run');previous=node+'.else'
    for name in ['save_composition','load_composition','delete_composition']:
        node='composition'+name;branch(g,node,call(g,node+'name',STR+'EqualEqual_StrStr',{'A':'event.EventName'},B=name));g.call(node+'queue','self:QueueCompositionAction',Name=name);g.wire(('event.Argument',node+'queue.Argument'));g.chain(previous,node,node+'queue');previous=node+'.else'
    for name in ['restore','restore_all','forget']:
        node='storeroom'+name;branch(g,node,call(g,node+'name',STR+'EqualEqual_StrStr',{'A':'event.EventName'},B=name))
        g.call(node+'queue','self:QueueStoreroomAction',Name=name);g.wire(('event.Argument',node+'queue.Key'));g.chain(previous,node,node+'queue');previous=node+'.else'
    for name in ['save_preset','load_preset','delete_preset','scope']:
        node='preset'+name;branch(g,node,call(g,node+'name',STR+'EqualEqual_StrStr',{'A':'event.EventName'},B=name));
        if name=='scope':
            g.call(node+'queue','self:QueueEditorMutation',RequireSelection='false');g.wire(('entry.Event',node+'queue.Event'))
        else:
            g.call(node+'queue','self:QueuePresetAction',Name=name);g.wire(('event.Argument',node+'queue.Argument'))
        g.chain(previous,node,node+'queue');previous=node+'.else'
    adjust_names=[call(g,'adjustname'+str(i),STR+'EqualEqual_StrStr',{'A':'event.EventName'},B=n) for i,n in enumerate(['rotate','rotate_fine','scale'])]
    branch(g,'compositionadjust',combine(g,'compositionadjustcheck',[get(g,'CompositionPlacing'),combine(g,'compositionadjustname',adjust_names,True)]));g.call('adjustcomposition','self:AdjustComposition');g.wire(('event.EventName','adjustcomposition.Name'),('event.Scalar','adjustcomposition.Steps'));g.chain(previous,'compositionadjust','adjustcomposition');previous='compositionadjust.else'
    branch(g,'previewadjust',combine(g,'previewadjustcheck',[get(g,'PlacementActive'),combine(g,'previewadjustname',adjust_names,True)]));g.call('adjustpreview','self:AdjustPlacement');g.wire(('event.EventName','adjustpreview.Name'),('event.Scalar','adjustpreview.Steps'));g.chain(previous,'previewadjust','adjustpreview');previous='previewadjust.else'
    from runtime_edit_queue import GLOBAL,TRANSFORMS
    for i,name in enumerate(GLOBAL+TRANSFORMS):
        node='mutation'+str(i);branch(g,node,call(g,node+'name',STR+'EqualEqual_StrStr',{'A':'event.EventName'},B=name))
        g.call(node+'queue','self:QueueEditorMutation',RequireSelection='false' if name in GLOBAL else 'true');g.wire(('entry.Event',node+'queue.Event'))
        g.chain(previous,node,node+'queue');previous=node+'.else'
    for i,(name,field) in enumerate([('lock','StructureEnabled'),('floors','FloorsEnabled'),('walls','WallsEnabled')]):
        node='toggle'+str(i);branch(g,node,call(g,node+'name',STR+'EqualEqual_StrStr',{'A':'event.EventName'},B=name))
        value=call(g,node+'not',KML+':Not_PreBool',{'A':get(g,field)});set_value(g,node+'set',field,value)
        branch(g,node+'picker',validity(g,node+'valid',get(g,'Picker')))
        from runtime_pick import PICKER
        method(g,node+'cancel',PICKER,'CancelQuery',get(g,'Picker'))
        g.call(node+'validate','self:RevalidateSelection')
        g.chain(previous,node,node+'set',node+'picker',node+'cancel',node+'validate');previous=node+'.else'
    # Session toggle; Settings hold the default.
    branch(g,'magnet',call(g,'magnetname',STR+'EqualEqual_StrStr',{'A':'event.EventName'},B='neighbour_snap'))
    set_value(g,'magnettoggle','SnapEnabled',call(g,'magnetnot',KML+':Not_PreBool',{'A':get(g,'SnapEnabled')}));g.chain(previous,'magnet','magnettoggle');previous='magnet.else'
    set_value(g,'unhandled','LastUnhandled','event.EventName');bump(g,'count','UnhandledCommands');g.chain(previous,'unhandled','count')
    g.chain('entry','look','looking')
    return g.function('HandleEditorEvent',inputs=[v('Event','struct:'+EVENT)])


def process():
    g=Graph();g.get('i','local:EventIndex')
    bounded=call(g,'limit',KML+':Less_IntInt',{'A':'i.EventIndex'},B=64)
    branch(g,'loop',combine(g,'ready',[get(g,'UIOpen'),validity(g,'busvalid',get(g,'InputBus')),bounded]))
    method(g,'take',BUS,'Take',get(g,'InputBus'));branch(g,'found','take.Found')
    g.call('handle','self:HandleEditorEvent');g.wire(('take.Event','handle.Event'))
    set_value(g,'advance','local:EventIndex',call(g,'next',KML+':Add_IntInt',{'A':'i.EventIndex'},B=1))
    g.call('refresh','self:RefreshEditorUI')
    g.chain('entry','loop','take','found','handle','refresh','advance','loop')
    return g.function('ProcessEditorEvents',locals=[v('EventIndex','int','0')])


def refresh():
    g=Graph();branch(g,'valid',combine(g,'ready',[get(g,'UIOpen'),validity(g,'toolbarvalid',get(g,'Toolbar')),validity(g,'historyvalid',get(g,'History'))]))
    g.call('canedit','self:CanEdit');method(g,'dirty',HISTORY,'IsDirty',get(g,'History'))
    branch(g,'busy',get(g,'Busy'))
    text(g,'applying','Toolbar','Status',constant='Applying layout…');branch(g,'unsaved','dirty.Dirty')
    text(g,'dirtytext','Toolbar','Status',constant='Unsaved changes');text(g,'savedtext','Toolbar','Status',constant='No unsaved changes')
    g.node('buttons','sequence',outputs=1)
    g.chain('entry','valid','canedit','dirty','busy','applying','buttons');g.chain('busy.else','unsaved','dirtytext','buttons');g.chain('unsaved.else','savedtext','buttons')
    previous='buttons.then_0'
    for name,field in [('Undo','UndoSteps'),('Redo','RedoSteps'),('Save',None)]:
        ready='canedit.Ready'
        if field:
            rows=prop(g,name+'steps',HISTORY,field,get(g,'History'));arr(g,name+'len','Length',rows)
            any_=call(g,name+'any',KML+':Greater_IntInt',{'A':name+'len.ReturnValue'},B=0);ready=combine(g,name+'ready',[ready,any_])
        obj=widget(g,name+'button','Toolbar',name);call(g,name+'enable',WIDGET+':SetIsEnabled',{'self':obj,'bInIsEnabled':ready});g.chain(previous,name+'enable');previous=name+'enable'
    # The selection/filter port reads the same native values displayed here.
    for field,widgetname,divisor,suffix in [('GridStep','SnapLabel',1,' cm'),('ReachCm','ReachLabel',100,' m')]:
        amount=call(g,field+'value',KML+':Divide_DoubleDouble',{'A':get(g,field)},B=divisor)
        whole=call(g,field+'whole',KML+':FTrunc',{'A':amount})
        number=call(g,field+'number',STR+'Conv_IntToString',{'InInt':whole})
        full=call(g,field+'full',STR+'Concat_StrStr',{'A':number},B=suffix)
        text(g,field+'text','Toolbar',widgetname,value=full);g.chain(previous,field+'text');previous=field+'text'
    branch(g,'gridoff',call(g,'zero',KML+':EqualEqual_DoubleDouble',{'A':get(g,'GridStep')},B=0))
    text(g,'offlabel','Toolbar','SnapLabel',constant='Off');g.node('aftergrid','sequence',outputs=1);g.chain(previous,'gridoff','offlabel','aftergrid');g.chain('gridoff.else','aftergrid');previous='aftergrid.then_0'
    # Grid and the selection filters are toggles; the library tabs show the open panel.
    toggles=[('Magnet',get(g,'SnapEnabled')),('Snap',call(g,'gridon',KML+':NotEqual_DoubleDouble',{'A':get(g,'GridStep')},B=0)),
             ('Floors',get(g,'FloorsEnabled')),('Walls',get(g,'WallsEnabled')),('Lock',get(g,'StructureEnabled'))]
    toggles+=[(button,call(g,'tab'+button,STR+'EqualEqual_StrStr',{'A':get(g,'ActivePanel')},B=name)) for button,_,name,_ in editor.LIBRARY]
    for button,on in toggles:
        g.chain(previous,style_toggle(g,'style'+button,'Toolbar',button,on));previous='style'+button
    g.call('modes','self:RefreshGizmoModeUI');g.chain(previous,'modes');previous='modes'
    g.call('feedback','self:EditorFeedback');text(g,'hints','Toolbar','Hints',value='feedback.Message')
    set_value(g,'busycache','LastUIBusy',get(g,'Busy'));set_value(g,'draftcache','LastUIDraftStatus',get(g,'LastDraftStatus'));set_value(g,'prefcache','LastUIPreferencesStatus',get(g,'PreferencesStatus'));g.call('layoutfeedback','self:RefreshLayoutFeedback');g.call('scopelabels','self:RefreshLayoutScope');g.chain(previous,'feedback','hints','busycache','draftcache','prefcache','layoutfeedback','scopelabels')
    return g.function('RefreshEditorUI')


def feedback():
    g=Graph();previous='entry'
    for code,message in [(6,'The layout could not be saved. Your edits are still here.'),(8,'The saved layout changed outside this session. Your edits have been kept; discard and reopen to load that version.'),(7,'That change could not be applied.'),(9,'That action is not available right now.'),(10,'Review the different draft baseline before recovering it.')]:
        name='code'+str(code);branch(g,name,call(g,name+'match',KML+':EqualEqual_IntInt',{'A':get(g,'LastStatus')},B=code))
        g.set(name+'text','local:FeedbackMessage',message);g.chain(previous,name,name+'text','result');previous=name+'.else'
    branch(g,'draft',call(g,'draftfailed',KML+':GreaterEqual_IntInt',{'A':get(g,'LastDraftStatus')},B=3))
    g.set('warning','local:FeedbackMessage','Draft autosave is unavailable. Save your changes before leaving.')
    g.chain(previous,'draft','warning','result')
    branch(g,'selection',call(g,'selectionmessage',STR+'NotEqual_StrStr',{'A':get(g,'SelectionMessage')},B=''));set_value(g,'selectiontext','local:FeedbackMessage',get(g,'SelectionMessage'));g.chain('draft.else','selection','selectiontext','result');g.chain('selection.else','preferences')
    branch(g,'preferences',call(g,'preffailed',KML+':GreaterEqual_IntInt',{'A':get(g,'PreferencesStatus')},B=3))
    g.set('prefwarning','local:FeedbackMessage','Preferences are unavailable or could not be saved. Your layout edits are still here; existing preference files have been kept.')
    g.chain('preferences','prefwarning','result');g.chain('preferences.else','bindings')
    branch(g,'bindings',get(g,'BindingsDefaulted'));g.set('bindingwarning','local:FeedbackMessage','Saved key bindings conflict. Default controls are active; reset or correct the bindings in Settings.')
    g.chain('bindings','bindingwarning','result');g.chain('bindings.else','result')
    g.get('out','local:FeedbackMessage');g.wire(('out.FeedbackMessage','result.Message'))
    return g.function('EditorFeedback',outputs=[v('Message','string')],locals=[v('FeedbackMessage','string','Select a prop to edit it, or open the Catalog to add something.')])


def poll():
    g=Graph();busy=call(g,'busy',KML+':NotEqual_BoolBool',{'A':get(g,'Busy'),'B':get(g,'LastUIBusy')});draft=call(g,'draft',KML+':NotEqual_IntInt',{'A':get(g,'LastDraftStatus'),'B':get(g,'LastUIDraftStatus')})
    pref=call(g,'prefs',KML+':NotEqual_IntInt',{'A':get(g,'PreferencesStatus'),'B':get(g,'LastUIPreferencesStatus')})
    branch(g,'changed',combine(g,'changedstate',[busy,draft,pref],True));g.call('refresh','self:RefreshEditorUI');g.chain('entry','changed','refresh')
    return g.function('PollEditorUI')


def functions():return [toggle_style(),set_panel(),toggle_panel(),confirm(),offer_recovery(),exit_editor(),back(),confirm_choice('save'),confirm_choice('discard'),confirm_choice('cancel'),help_toggle(),focus_viewport(),cycle(True),cycle(False),handle(),process(),feedback(),refresh(),poll()]
