"""Deferred settings commands and immediate application to the native editor."""
from graph import Graph, variable as v, KML, GS, WBL
from runtime_preferences import DOCUMENT, CHOICES, BINDINGS, NUMBERS, enum
from runtime_preference_service import SERVICE
from runtime_settings_widget import PATH, CHOICE_LABELS, KEY_LABELS
from runtime_store import call, branch, STR, combine
from runtime_world import validity, set_value
from runtime_apply import get
from runtime_session import method


def refresh():
    g=Graph();branch(g,'valid',validity(g,'panel',get(g,'SettingsPanel')))
    method(g,'show',PATH,'RefreshSettings',get(g,'SettingsPanel'),{'Document':get(g,'PreferencesDocument'),'Message':get(g,'SettingsMessage')})
    g.chain('entry','valid','show');return g.function('RefreshSettingsPanel')


def changed():
    g=Graph();branch(g,'active',call(g,'same',STR+'EqualEqual_StrStr',{'A':get(g,'ActivePanel')},B='settings'))
    g.set('clear','SettingsMessage','');g.call('read','self:ReadEditorPreferences')
    branch(g,'healthy',call(g,'writable',KML+':LessEqual_IntInt',{'A':get(g,'PreferencesStatus')},B=2))
    g.set('warning','SettingsMessage','Preferences could not be loaded safely. Existing files will be preserved; changes are unavailable.')
    g.call('refresh','self:RefreshSettingsPanel')
    branch(g,'panel',validity(g,'panelvalid',get(g,'SettingsPanel')))
    branch(g,'focused',call(g,'descendant','/Script/UMG.Widget:HasFocusedDescendants',{'self':get(g,'SettingsPanel')}))
    call(g,'focus',WBL+':SetFocusToGameViewport')
    g.chain('entry','active','clear','read','healthy','refresh');g.chain('healthy.else','warning','refresh');g.chain('active.else','panel','focused','focus')
    return g.function('SettingsPanelChanged')


def change():
    g=Graph();g.call('ensure','self:EnsurePreferenceService');branch(g,'valid',validity(g,'service',get(g,'PreferenceService')))
    branch(g,'reset','entry.Reset');method(g,'resetall',SERVICE,'ResetSettings',get(g,'PreferenceService'))
    method(g,'save',SERVICE,'ChangePreference',get(g,'PreferenceService'),{'Key':'entry.Key','Value':'entry.Value'})
    set_value(g,'resetstatus','SettingsStatus','resetall.Status');set_value(g,'savestatus','SettingsStatus','save.Status')
    branch(g,'success',call(g,'ok',KML+':EqualEqual_IntInt',{'A':get(g,'SettingsStatus')},B=1))
    # A camera/key change must not reset unsaved quickbar choices for this session.
    fields=[('GridStep','double'),('GridIndex','int'),('ReachCm','double'),('ReachIndex','int'),('StructureEnabled','bool'),('FloorsEnabled','bool'),('WallsEnabled','bool'),('GizmoMode','int'),('SnapEnabled','bool')]
    previous='success'
    for field,kind in fields:
        set_value(g,'keep'+field,'local:Old'+field,get(g,field));g.chain(previous,'keep'+field);previous='keep'+field
    g.call('read','self:ReadEditorPreferences');g.call('apply','self:ApplyEditorPreferences');branch(g,'restore','entry.Reset')
    g.call('enddrag','self:EndSelectionDrag',Commit='false')
    g.chain(previous,'enddrag','read','apply','restore');previous='restore.else'
    for field,kind in fields:
        g.get('old'+field,'local:Old'+field);set_value(g,'restore'+field,field,'old'+field+'.Old'+field)
        g.chain(previous,'restore'+field);previous='restore'+field
    needsmapping=combine(g,'mappingneeded',['entry.Reset',enum(g,'keychanged','entry.Key',[key for key,_,_,_ in BINDINGS])],True)
    branch(g,'mapping',needsmapping);g.call('install','self:InstallEditorMappings');branch(g,'installed','install.Accepted')
    g.set('saved','SettingsMessage','Settings saved.');g.set('mappingfailure','SettingsMessage','Settings saved. Controls could not be updated; close and reopen the editor to retry.')
    g.chain(previous,'mapping','install','installed','saved');g.chain('restore','mapping');g.chain('mapping.else','saved');g.chain('installed.else','mappingfailure','refresh')
    g.call('help','self:RefreshEditorHelp');g.call('fields','self:RefreshTransformFields');g.call('refresh','self:RefreshSettingsPanel');g.chain('saved','help','fields','refresh')
    branch(g,'invalid',call(g,'invalidstatus',KML+':EqualEqual_IntInt',{'A':get(g,'SettingsStatus')},B=7))
    g.set('rejected','SettingsMessage','That key is reserved, already assigned, or unsupported. Numeric values must stay within the displayed range.')
    g.set('failure','SettingsMessage','Settings could not be saved. Existing preferences were preserved; check storage and try again.')
    g.chain('success.else','invalid','rejected','refresh');g.chain('invalid.else','failure','refresh')
    g.chain('entry','ensure','valid','reset','resetall','resetstatus','success');g.chain('reset.else','save','savestatus','success')
    return g.function('ChangeEditorSetting',inputs=[v('Key','string'),v('Value','string'),v('Reset','bool')],locals=[v('Old'+f,k) for f,k in fields])


def cycle():
    g=Graph();branch(g,'valid',validity(g,'document',get(g,'PreferencesDocument')))
    method(g,'read',DOCUMENT,'ReadPreference',get(g,'PreferencesDocument'),{'Key':'entry.Key'});previous='read'
    for key in CHOICE_LABELS:
        n='key'+key;branch(g,n,call(g,n+'eq',STR+'EqualEqual_StrStr',{'A':'entry.Key'},B=key));g.chain(previous,n)
        p=n;values=CHOICES[key][1]
        for i,value in enumerate(values):
            ident=n+str(i);branch(g,ident,call(g,ident+'eq',STR+'EqualEqual_StrStr',{'A':'read.Value'},B=value))
            g.call(ident+'set','self:ChangeEditorSetting',Key=key,Value=values[(i+1)%len(values)],Reset='false')
            g.chain(p,ident,ident+'set');p=ident+'.else'
        previous=n+'.else'
    g.chain('entry','valid','read');return g.function('CycleEditorSetting',inputs=[v('Key','string')])


def help_text():
    from runtime_editor_host import widget
    from runtime_key_names import CODEC
    g=Graph();branch(g,'valid',combine(g,'ready',[validity(g,'toolbar',get(g,'Toolbar')),validity(g,'document',get(g,'PreferencesDocument'))]))
    g.node('self','self');call(g,'codec',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=CODEC)
    g.node('cast','cast',**{'class':CODEC});g.wire(('codec.ReturnValue','cast.Object'))
    g.set('start','local:Body','Hold right mouse to look. Left mouse selects and drags.\nMouse wheel rotates; the fast-flight key makes fine turns or lifts while dragging.\n+/− scale. Arrows and Page Up/Down nudge. Esc goes back.\n\n')
    g.chain('entry','valid','codec','cast','start');previous='start'
    for i,(key,_,default,label) in enumerate(BINDINGS):
        n='key'+str(i);g.call(n,'self:BuildEditorHelpLine',Key=key,Default=default,Label=label)
        g.wire(('cast.AsBP Den Key Names',n+'.Codec'));g.get(n+'body','local:Body')
        set_value(g,n+'append','local:Body',call(g,n+'join',STR+'Concat_StrStr',{'A':n+'body.Body','B':n+'.Line'}))
        g.chain(previous,n,n+'append');previous=n+'append'
    g.get('body','local:Body');call(g,'show','/Script/UMG.TextBlock:SetText',{'self':widget(g,'help','Toolbar','HelpText'),'InText':'body.Body'})
    g.chain(previous,'show');return g.function('RefreshEditorHelp',locals=[v('Body','string'),v('CurrentKey','string')])


def help_line():
    from runtime_key_names import CODEC
    g=Graph();method(g,'read',DOCUMENT,'ReadPreference',get(g,'PreferencesDocument'),{'Key':'entry.Key'})
    branch(g,'fallback',get(g,'BindingsDefaulted'));set_value(g,'default','local:HelpKeyValue','entry.Default');set_value(g,'saved','local:HelpKeyValue','read.Value')
    g.get('current','local:HelpKeyValue');method(g,'key',CODEC,'KeyFromName','entry.Codec',{'Name':'current.HelpKeyValue'})
    method(g,'label',CODEC,'NameFromKey','entry.Codec',{'Key':'key.Key'})
    name=call(g,'string','/Script/Engine.KismetTextLibrary:Conv_TextToString',{'InText':'label.Label'})
    prefix=call(g,'prefix',STR+'Concat_StrStr',{'A':'entry.Label'},B=' · ')
    line=call(g,'line',STR+'Concat_StrStr',{'A':prefix,'B':name});line=call(g,'newline',STR+'Concat_StrStr',{'A':line},B='\n')
    g.wire((line,'result.Line'));g.chain('entry','read','fallback','default','key','label','result');g.chain('fallback.else','saved','key')
    return g.function('BuildEditorHelpLine',inputs=[v('Key','string'),v('Default','string'),v('Label','string'),v('Codec','object:'+CODEC)],outputs=[v('Line','string')],locals=[v('HelpKeyValue','string')])


def variables():return [v('SettingsMessage','string'),v('SettingsStatus','int')]
def functions():return [refresh(),changed(),change(),cycle(),help_line(),help_text()]
