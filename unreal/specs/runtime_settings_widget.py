"""In-game preferences panel."""
import ui_templates as editor
from graph import Graph, variable as v, GS, KML
from runtime_preferences import DOCUMENT, BINDINGS, NUMBERS, CHOICES
from runtime_key_names import CODEC
from runtime_store import call, branch
from runtime_world import set_value, validity
from runtime_session import method
from runtime_apply import get

PATH='/DenDesignerGF/Editor/WBP_DenSettings'
CHORD='/Script/Slate.InputChord'
SELECTOR='/Script/UMG.InputKeySelector'
NUMERIC_LABELS={'fly_speed':'Flight speed · 200–3000 cm/s','fast_multiplier':'Fast flight multiplier · 1–8','look_speed':'Look sensitivity · 0.5–10'}
CHOICE_LABELS={'autosave':'Draft autosave','thumbnails':'Generate thumbnails','toggle_modifier':'Open editor modifier'}
KEY_LABELS={'toggle_key':'Open editor key',**{key:label for key,_,_,label in BINDINGS}}


def refresh():
    g=Graph();branch(g,'valid',validity(g,'document','entry.Document'));g.set('guard','Refreshing','true');g.node('self','self')
    call(g,'codec',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=CODEC);g.node('cast','cast',**{'class':CODEC});g.wire(('codec.ReturnValue','cast.Object'))
    g.chain('entry','valid','guard','codec','cast');previous='cast'
    for key in [*NUMBERS,*CHOICE_LABELS,*KEY_LABELS]:
        method(g,key+'read',DOCUMENT,'ReadPreference','entry.Document',Key=key)
        g.chain(previous,key+'read');previous=key+'read'
        if key in KEY_LABELS:
            method(g,key+'key',CODEC,'KeyFromName','cast.AsBP Den Key Names',{'Name':key+'read.Value'})
            g.node(key+'chord','make_struct',struct=CHORD);g.wire((key+'key.Key',key+'chord.Key'))
            call(g,key+'show',SELECTOR+':SetSelectedKey',{'self':get(g,'Field_'+key),'InSelectedKey':key+'chord.InputChord'})
            g.chain(previous,key+'key',key+'show')
        elif key in NUMBERS:
            call(g,key+'show','/Script/UMG.EditableTextBox:SetText',{'self':get(g,'Field_'+key),'InText':key+'read.Value'})
            g.chain(previous,key+'show')
        else:
            # Stable human-readable choices; the saved booleans never appear in the UI.
            values=CHOICES[key][1];g.node(key+'done','sequence',outputs=1)
            from runtime_store import STR
            for i,value in enumerate(values):
                n=key+str(i);branch(g,n,call(g,n+'eq',STR+'EqualEqual_StrStr',{'A':key+'read.Value'},B=value))
                label={'true':'On','false':'Off','ctrl':'Ctrl','shift':'Shift','alt':'Alt','none':'None'}.get(value,value)
                call(g,n+'show','/Script/UMG.TextBlock:SetText',{'self':get(g,'Field_'+key+'Label')},InText=label)
                g.chain(previous,n,n+'show',key+'done');previous=n+'.else'
            g.chain(previous,key+'done');previous=key+'done.then_0';continue
        previous=key+'show'
    call(g,'message','/Script/UMG.TextBlock:SetText',{'self':get(g,'Message'),'InText':'entry.Message'})
    g.set('unguard','Refreshing','false');g.chain(previous,'message','unguard');g.chain('cast.CastFailed','unguard')
    return g.function('RefreshSettings',inputs=[v('Document','object:'+DOCUMENT),v('Message','string')])


def selected():
    g=Graph();branch(g,'refreshing',get(g,'Refreshing'));g.node('self','self')
    call(g,'codec',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=CODEC);g.node('cast','cast',**{'class':CODEC});g.wire(('codec.ReturnValue','cast.Object'))
    g.node('chord','break_struct',struct=CHORD);g.wire(('entry.Chord','chord.InputChord'))
    method(g,'name',CODEC,'NameFromKey','cast.AsBP Den Key Names',{'Key':'chord.Key'})
    g.call('emit','self:Native_Event');g.wire(('entry.Event','emit.Name'),('name.Name','emit.Arg'))
    g.chain('entry','refreshing');g.chain('refreshing.else','codec','cast','name','emit')
    return g.function('CaptureSettingKey',inputs=[v('Event','string'),v('Chord','struct:'+CHORD)])


def spec():
    g=editor.Graph();rows=[]
    def heading(name,label):rows.append(editor.label(name,label,slot={'Padding':'(Left=0,Top=18,Right=0,Bottom=6)'}))
    def row(key,label,field):
        title=editor.text('Label_'+key,label,13,wrap=True,slot={'Size':'(SizeRule=Fill,Value=1)','VerticalAlignment':'VAlign_Center','Padding':'(Left=0,Top=0,Right=12,Bottom=0)'})
        box={'class':'/Script/UMG.SizeBox','name':'Width_'+key,'props':{'WidthOverride':124,'bOverride_WidthOverride':'true'},'children':[field]}
        rows.append(editor.row('Row_'+key,[title,box]))
    heading('Camera','Camera')
    for key,label in NUMERIC_LABELS.items():
        row(key,label,editor.box('Field_'+key,'',select_all=True));g.commit('Field_'+key,'setting:'+key)
    heading('Background','Background tasks')
    for key in ['autosave','thumbnails']:
        row(key,CHOICE_LABELS[key],editor.button('Field_'+key,''));g.click('Field_'+key,'setting_cycle');g.nodes[-1]['defaults']['Arg']=key
    heading('Opening','Open editor')
    row('toggle_modifier',CHOICE_LABELS['toggle_modifier'],editor.button('Field_toggle_modifier',''))
    g.click('Field_toggle_modifier','setting_cycle');g.nodes[-1]['defaults']['Arg']='toggle_modifier'
    for key,label in KEY_LABELS.items():
        if key=='key_forward':
            heading('Bindings','Editor keys')
            rows.append(editor.text('CaptureHint','Click a key, then press its replacement. Esc cancels. Each action needs its own key.',12,editor.DIM,wrap=True))
        field={'class':SELECTOR,'name':'Field_'+key,'variable':True,'props':dict(editor.BUTTON_STYLE, bAllowModifierKeys='false',bAllowGamepadKeys='false',KeySelectionText='Press a key…',NoKeySpecifiedText='Choose key',**{'TextStyle.Font.Size':14,'TextStyle.ColorAndOpacity':editor.WHITE})}
        row(key,label,field)
        g.nodes += [{'id':key,'kind':'bound_event','widget':'Field_'+key,'delegate':'OnKeySelected'},
                    {'id':key+'capture','kind':'call','function':'self:CaptureSettingKey','defaults':{'Event':'setting:'+key}}]
        g.links += [[key+'.then',key+'capture.execute'],[key+'.SelectedKey',key+'capture.Chord']]
    rows.append(editor.text('FixedHint','Mouse controls, Esc, Delete, arrow keys, Page Up/Down and +/− remain fixed. F9 is reserved. Grid, Range, Floors, Walls and Structure are on the menu bar.',12,editor.DIM,wrap=True,slot={'Padding':'(Left=0,Top=14,Right=0,Bottom=8)'}))
    # Settings take the inspector dock's place while open.
    panel=editor.inspector_panel('Panel',[
        editor.text('Title','Settings',20,editor.GOLD,role='title'),
        editor.text('Intro','Changes save automatically and apply immediately.',12,editor.DIM,wrap=True,slot={'Padding':'(Left=0,Top=6,Right=0,Bottom=0)'}),
        {'class':'/Script/UMG.ScrollBox','name':'SettingsScroll','slot':{'Size':'(SizeRule=Fill,Value=1)'},'children':[
            {'class':'/Script/UMG.VerticalBox','name':'SettingsRows','children':rows}]},
        editor.text('Message','',12,editor.DIM,wrap=True,slot={'Padding':'(Left=0,Top=12,Right=0,Bottom=8)'}),
        editor.row('Footer',[editor.button('ResetSettings','Reset settings'),editor.button('CloseSettings','Close')])])
    tree={'class':'/Script/UMG.CanvasPanel','name':'Root','children':[panel]}
    g.click('ResetSettings','settings_reset');g.click('CloseSettings','settings_close')
    return dict(kind='widget',path=PATH,variables=[v('Refreshing','bool','false')],tree=tree,functions=[*editor.NATIVE_EVENT,refresh(),selected()],graph=g.spec())
