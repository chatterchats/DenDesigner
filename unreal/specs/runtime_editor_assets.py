"""Connect native UI templates to the event bus, fonts and input guards."""
import copy
import json
import ui_templates as editor
from graph import Graph, variable as v, KML, GS
from runtime import ROOT, arr, unpack, struct
from runtime_store import call, branch, combine, STR
from runtime_world import set_value, validity, finish_bool
from runtime_apply import get

UIROOT='/DenDesignerGF/Editor/'
EVENT=ROOT+'ST_DenEditorEvent'
BUS=ROOT+'BP_DenEditorBus'
FONT='/Script/Engine.Font'
RIG=UIROOT+'BP_DenEditorRig'
TOOLBAR=UIROOT+'WBP_DenToolbar'
WIDGETS=['WBP_DenToolbar','WBP_DenCatalogEntry','WBP_DenCatalogShelf','WBP_DenCatalogChip','WBP_DenCatalog','WBP_DenLayouts','WBP_DenStoreroom','WBP_DenTransform','WBP_DenSettings','WBP_DenCompositions']
WIDGET='/Script/UMG.Widget'

def opening_key():
    from runtime_key_names import CODEC
    g=Graph();g.node('self','self');g.set('fallback','OpeningKey','Home')
    call(g,'codec',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=CODEC)
    g.node('cast','cast',**{'class':CODEC});g.wire(('codec.ReturnValue','cast.Object'))
    call(g,'key',CODEC+':KeyFromName',{'self':'cast.AsBP Den Key Names','Name':'entry.Name'})
    branch(g,'known','key.Known');set_value(g,'remember','OpeningKey','key.Key')
    g.chain('entry','fallback','codec','cast','key','known','remember')
    return g.function('ConfigureOpeningKey',inputs=[v('Name','string')])


def opening_ready():
    # Enhanced Input's held-key suppression does not protect our Axis3D movement.
    # Consume the entire opening chord before any editor action can use its keys.
    g=Graph();g.node('self','self');branch(g,'waiting',get(g,'OpeningInputBlocked'))
    pc=call(g,'player',GS+':GetPlayerController',{'WorldContextObject':'self.self'},PlayerIndex=0)
    branch(g,'valid',validity(g,'playerexists',pc))
    keys=[call(g,'opening', '/Script/Engine.PlayerController:IsInputKeyDown',
               {'self':pc,'Key':get(g,'OpeningKey')})]
    for key in ['LeftControl','RightControl','LeftShift','RightShift','LeftAlt','RightAlt']:
        keys.append(call(g,key,'/Script/Engine.PlayerController:IsInputKeyDown',{'self':pc},Key=key))
    branch(g,'held',combine(g,'anyheld',keys,True));g.set('released','OpeningInputBlocked','false')
    g.set('yes','local:OK','true');finish_bool(g,'Ready')
    g.chain('entry','waiting','valid','held','result');g.chain('held.else','released','yes','result')
    g.chain('waiting.else','yes');g.chain('valid.else','result')
    return g.function('OpeningInputReady',outputs=[v('Ready','bool')],locals=[v('OK','bool','false')])


def text_fields(widget_name):
    from runtime_settings_widget import spec as settings_spec
    from runtime_composition_widget import spec as composition_spec
    from runtime_community_widget import spec as community_spec
    from runtime_community_widget import spec as community_spec
    factories={'WBP_DenCompositions':composition_spec,'WBP_DenCommunity':community_spec,'WBP_DenSettings':settings_spec,'WBP_DenToolbar':editor.toolbar,'WBP_DenCatalog':editor.catalog,
               'WBP_DenLayouts':editor.layouts,'WBP_DenStoreroom':editor.storeroom,
               'WBP_DenTransform':editor.transform}
    def walk(node):
        if node['class'] in ['/Script/UMG.EditableTextBox','/Script/UMG.EditableText','/Script/UMG.InputKeySelector']:
            yield node['name']
        for child in node.get('children',[]):yield from walk(child)
    return list(walk(factories[widget_name]()['tree']))


def register_text_input():
    g=Graph();branch(g,'valid',validity(g,'check','entry.Widget'))
    arr(g,'add','AddUnique',get(g,'TextInputs'));g.wire(('entry.Widget','add.NewItem'))
    g.chain('entry','valid','add')
    return g.function('RegisterTextInput',inputs=[v('Widget','object:'+WIDGET)])


def typing():
    # Query focus at the input event itself, not once per host tick. Otherwise
    # Ctrl+A can move the rig for one frame before the host notices text focus.
    g=Graph();rows=get(g,'TextInputs');g.get('index','local:Cursor')
    arr(g,'len','Length',rows);branch(g,'loop',call(g,'within',KML+':Less_IntInt',{'A':'index.Cursor','B':'len.ReturnValue'}))
    arr(g,'item','Get',rows);g.wire(('index.Cursor','item.Index'))
    branch(g,'valid',validity(g,'check','item.Item'))
    focused=[call(g,'focus'+str(i),WIDGET+':'+fn,{'self':'item.Item'})
             for i,fn in enumerate(['HasKeyboardFocus','HasAnyUserFocus','HasFocusedDescendants'])]
    branch(g,'focused',combine(g,'anyfocus',focused,True));g.set('yes','local:OK','true')
    set_value(g,'next','local:Cursor',call(g,'increment',KML+':Add_IntInt',{'A':'index.Cursor'},B=1));finish_bool(g,'Typing')
    g.chain('entry','loop','valid','focused','yes','result');g.chain('loop.else','result')
    g.chain('valid.else','next','loop');g.chain('focused.else','next')
    return g.function('IsTyping',outputs=[v('Typing','bool')],locals=[v('OK','bool','false'),v('Cursor','int','0')])


def emit():
    g=Graph();branch(g,'enabled',get(g,'Accepting'))
    arr(g,'len','Length',get(g,'Events'))
    branch(g,'full',call(g,'capacity',KML+':GreaterEqual_IntInt',{'A':'len.ReturnValue'},B=256))
    arr(g,'drop','Remove',get(g,'Events'),IndexToRemove=0)
    count=call(g,'count',KML+':Add_IntInt',{'A':get(g,'Dropped')},B=1);set_value(g,'dropped','Dropped',count)
    g.node('event','make_struct',struct=EVENT)
    for field in ['Kind','EventName','Argument','Scalar','Direction']:g.wire(('entry.'+field,'event.'+field))
    arr(g,'append','Add',get(g,'Events'));g.wire(('event.ST_DenEditorEvent','append.NewItem'))
    g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','enabled','full','drop','dropped','append','yes','result');g.chain('full.else','append');g.chain('enabled.else','result')
    return g.function('Emit',inputs=[v('Kind','int'),v('EventName','string'),v('Argument','string'),v('Scalar','float'),v('Direction','vector')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def take():
    g=Graph();arr(g,'len','Length',get(g,'Events'));branch(g,'any',call(g,'has',KML+':Greater_IntInt',{'A':'len.ReturnValue'},B=0))
    arr(g,'item','Get',get(g,'Events'),Index=0);set_value(g,'cache','local:OutputEvent','item.Item')
    arr(g,'remove','Remove',get(g,'Events'),IndexToRemove=0);g.set('yes','local:OK','true');finish_bool(g,'Found')
    g.get('eventout','local:OutputEvent');g.wire(('eventout.OutputEvent','result.Event'))
    g.chain('entry','any','cache','remove','yes','result');g.chain('any.else','result')
    return g.function('Take',outputs=[v('Found','bool'),v('Event','struct:'+EVENT)],locals=[v('OK','bool','false'),v('OutputEvent','struct:'+EVENT)])


def gate(start):
    g=Graph();arr(g,'clear','Clear',get(g,'Events'));g.set('flag','Accepting','true' if start else 'false')
    g.chain('entry','clear','flag')
    if not start:
        arr(g,'release','Clear',get(g,'TextInputs'));g.chain('flag','release')
    return g.function('Start' if start else 'Stop')


def bus_spec():
    return dict(kind='blueprint',path=BUS,parent='/Script/CoreUObject.Object',
        variables=[v('Events','struct:'+EVENT+'[]'),v('Accepting','bool','false'),v('Dropped','int','0'),v('TextInputs','object:'+WIDGET+'[]'),
                   v('TitleFont','object:'+FONT),v('SecondaryFont','object:'+FONT),v('PrimaryFont','object:'+FONT)],
        functions=[emit(),take(),gate(True),gate(False),register_text_input(),typing()])


def bridge(name):
    g=Graph();g.get('bus','EditorBus');branch(g,'valid',validity(g,'check','bus.EditorBus'))
    kind={'Native_Action':0,'Native_Vector':1,'Native_Event':2}[name]
    inputs={'self':'bus.EditorBus','EventName':'entry.Name'}
    params=[v('Name','string')]
    if kind==0:inputs['Scalar']='entry.Value';params.append(v('Value','float'))
    elif kind==1:inputs['Direction']='entry.Value';params.append(v('Value','vector'))
    else:inputs['Argument']='entry.Arg';params.append(v('Arg','string'))
    call(g,'emit',BUS+':Emit',inputs,Kind=kind)
    g.chain('entry','valid')
    if kind<2:
        g.call('opening','self:OpeningInputReady');branch(g,'released','opening.Ready')
        call(g,'typing',BUS+':IsTyping',{'self':'bus.EditorBus'})
        nottyping=call(g,'nottyping',KML+':Not_PreBool',{'A':'typing.Typing'})
        # Capture/release must work while a text field owns keyboard focus.
        looking=call(g,'looking',STR+'EqualEqual_StrStr',{'A':'entry.Name'},B='look_hold')
        branch(g,'allowed',combine(g,'allow',[nottyping,looking],True))
        g.chain('valid','opening','released','typing','allowed','emit')
    else:g.chain('valid','emit')
    return g.function(name,inputs=params)


def font_roles(tree,in_button=False):
    if tree.get('class')=='/Script/UMG.TextBlock':
        props=tree['props'];size=props.get('Font.Size',12);color=props.get('ColorAndOpacity')
        role=tree.get('role') or ('button' if in_button else ('title' if size>=20 else 'heading') if color==editor.GOLD else 'hint' if color==editor.DIM else 'body')
        yield tree['name'],role,size
    for child in tree.get('children',[]):yield from font_roles(child,in_button or tree.get('class')=='/Script/UMG.Button')


def style(tree):
    g=Graph();g.get('bus','EditorBus');branch(g,'valid',validity(g,'check','bus.EditorBus'))
    g.chain('entry','valid')
    previous='valid'
    # (font, typeface, letter spacing in 1/1000 em): capitals in labels and buttons are spaced out.
    roles={'title':('TitleFont','DmBd',0),'heading':('SecondaryFont','Bold',20),'label':('SecondaryFont','Bold',120),
           'button':('SecondaryFont','Medium',70),'body':('PrimaryFont','Medium',0),'hint':('PrimaryFont','Regular',0)}
    for i,(widget,role,size) in enumerate(font_roles(tree)):
        field,face,spacing=roles[role];name='font'+str(i)
        g.get(name,BUS+':'+field);g.wire(('bus.EditorBus',name+'.self'))
        branch(g,name+'valid',validity(g,name+'check',name+'.'+field))
        g.node(name+'info','make_struct',struct='/Script/SlateCore.SlateFontInfo',defaults={'TypefaceFontName':face,'Size':str(size),'LetterSpacing':str(spacing)})
        g.wire((name+'.'+field,name+'info.FontObject'));g.get(name+'widget',widget)
        call(g,name+'set','/Script/UMG.TextBlock:SetFont',{'self':name+'widget.'+widget,'InFontInfo':name+'info.SlateFontInfo'})
        g.chain(previous,name+'valid',name+'set')
        if i:g.chain('font'+str(i-1)+'valid.else',name+'valid')
        previous=name+'set'
    return g.function('ApplyNativeStyle')


def convert(source):
    value=copy.deepcopy(source)
    def expose_panels(node):
        if node.get('name') in ['Panel','Feedback','ScopeHint','LibraryTabs']:node['variable']=True
        for child in node.get('children',[]):expose_panels(child)
    if 'tree' in value:expose_panels(value['tree'])
    name=value['path'].rsplit('/',1)[-1]
    if value['kind'] in ['widget','blueprint']:
        value.setdefault('variables',[]).append(v('EditorBus','object:'+BUS))
        functions=[]
        for fn in value.get('functions',[]):
            if fn['name'] in ['Native_Action','Native_Vector','Native_Event']:functions.append(bridge(fn['name']))
            else:functions.append(fn)
        if value['kind']=='widget':
            functions.append(style(value['tree']))
            def strip_roles(node):
                node.pop('role',None)
                for child in node.get('children',[]):strip_roles(child)
            strip_roles(value['tree'])
        value['functions']=functions
    if name=='BP_DenCatalogItem':
        value['variables'] += [v('AssetPath','string'),v('ThumbnailDocument','object:/DenDesignerGF/Runtime/BP_DenLayoutSave')]
    if name=='WBP_DenCatalogEntry':
        from runtime_thumbnail_ui import refresh_tile
        value['variables'].append(v('NativeItem','object:'+UIROOT+'BP_DenCatalogItem'))
        value['functions'].append(refresh_tile())
    if name=='WBP_DenTransform':
        def constrain(node):
            if node.get('name')=='Selection':node.setdefault('props',{})['WrapTextAt']=editor.INSPECTOR_WIDTH-36
            for child in node.get('children',[]):constrain(child)
        constrain(value['tree'])
        # Queue the focus return: Slate clears focus after the commit callback,
        # so setting viewport focus inside that callback is immediately undone.
        # A focus-loss commit must not steal focus from another field/button.
        graph=value['graph']
        for field in text_fields(name):
            graph['nodes'] += [
                {'id':field+'enter','kind':'call','function':KML+':EqualEqual_ByteByte','defaults':{'B':'1'}},
                {'id':field+'entered','kind':'branch'},
                {'id':field+'viewport','kind':'call','function':'self:Native_Event','defaults':{'Name':'numeric_done'}}]
            graph['links'] += [[field+'.CommitMethod',field+'enter.A'],
                               [field+'enter.ReturnValue',field+'entered.Condition'],
                               [field+'_event.then',field+'entered.execute'],
                               [field+'entered.then',field+'viewport.execute']]
    if name=='BP_DenEditorRig':
        from runtime_key_names import KEY
        value['variables'] += [
            v('ControlsEnabled','bool','true'),v('OpeningInputBlocked','bool','true'),v('OpeningKey',KEY,'Home')]
        value['functions'] += [opening_key(),opening_ready()]
        graph=value['graph']
        graph['nodes'] += [{'id':'opening_tick','kind':'event','name':'ReceiveTick'},
                           {'id':'opening_poll','kind':'call','function':'self:OpeningInputReady'}]
        graph['links'].append(['opening_tick.then','opening_poll.execute'])
        graph['nodes'].append({'id':'controls','kind':'get','var':'ControlsEnabled'})
        graph['nodes'].append({'id':'inputbus','kind':'get','var':'EditorBus'})
        for event,target in [('move','offset'),('look','turn')]:
            graph['nodes'] += [{'id':event+'allowed','kind':'branch'},
                               {'id':event+'opening','kind':'call','function':'self:OpeningInputReady'},
                               {'id':event+'released','kind':'branch'},
                               {'id':event+'typing','kind':'call','function':BUS+':IsTyping'},
                               {'id':event+'textfocus','kind':'branch'}]
            graph['links'].remove([event+'.Triggered',target+'.execute'])
            graph['links'] += [[event+'.Triggered',event+'allowed.execute'],['controls.ControlsEnabled',event+'allowed.Condition'],
                               [event+'allowed.then',event+'opening.execute'],[event+'opening.then',event+'released.execute'],
                               [event+'opening.Ready',event+'released.Condition'],
                               [event+'released.then',event+'typing.execute'],['inputbus.EditorBus',event+'typing.self'],
                               [event+'typing.then',event+'textfocus.execute'],[event+'typing.Typing',event+'textfocus.Condition'],
                               [event+'textfocus.else',target+'.execute']]
    if name in ['WBP_DenCatalogEntry','WBP_DenCatalogShelf','WBP_DenCatalogChip']:
        # Recycled entries obtain the bus (and loaded font references) from the
        # item assigned to them, without retaining external widget/object pointers.
        graph=value['graph'];graph['nodes'] += [
            {'id':'itembus','kind':'get','var':UIROOT+'BP_DenCatalogItem:EditorBus'},
            {'id':'rememberbus','kind':'set','var':'EditorBus'},
            {'id':'style','kind':'call','function':'self:ApplyNativeStyle'}]
        graph['links'].remove(['cast.then','tooltip.execute'])
        graph['links'] += [['cast.AsBP Den Catalog Item','itembus.self'],['itembus.EditorBus','rememberbus.EditorBus'],
                           ['cast.then','rememberbus.execute'],['rememberbus.then','style.execute'],['style.then','tooltip.execute']]
    if name=='WBP_DenCatalogEntry':
        graph=value['graph'];graph['nodes'].append({'id':'rememberitem','kind':'set','var':'NativeItem'})
        graph['links'].remove(['cast.then','rememberbus.execute'])
        graph['links'] += [['cast.AsBP Den Catalog Item','rememberitem.NativeItem'],['cast.then','rememberitem.execute'],['rememberitem.then','rememberbus.execute']]
    return value


def specs():
    yield '19_ST_DenEditorEvent',struct(EVENT,[v('Kind','int'),v('EventName','string'),v('Argument','string'),v('Scalar','float'),v('Direction','vector')])
    yield '20_BP_DenEditorBus',bus_spec()
    from runtime_settings_widget import spec as settings_spec
    from runtime_composition_widget import spec as composition_spec
    from runtime_community_widget import spec as community_spec
    from runtime_community_widget import spec as community_spec
    sources=editor.input_actions()+[editor.mapping_context(),editor.rig(),editor.toolbar(),editor.catalog_item(),editor.catalog_entry(),editor.catalog_shelf(),editor.catalog_chip(),editor.catalog(),editor.layouts(),editor.storeroom(),editor.transform(),settings_spec(),composition_spec(),community_spec()]
    for index,source in enumerate(sources,1):
        spec=convert(source)
        assert spec['path'].startswith('/DenDesignerGF/')
        yield '21_%02d_%s'%(index,spec['path'].rsplit('/',1)[-1]),spec
