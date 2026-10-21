"""Native preset listing and transactional layout replacement for the Layouts panel."""
from graph import Graph, variable as v, KML, GS
from runtime import ROOT, ENTRY, MUTATION, LAYOUT, arr, unpack
from runtime_store import call, branch, combine, STR
from runtime_world import set_value, validity, finish_bool
from runtime_apply import get, clear
from runtime_session import prop, method, HISTORY
from runtime_catalog_ui import ITEM, LIST, number, join, prefix
from runtime_editor_host import text, widget, WIDGET, visibility
from runtime_editor_assets import EVENT
from runtime_gizmo_controller import op, neg

PRESETS=ROOT+'BP_DenPresets'
LIBRARY=ROOT+'BP_DenPresetLibrary'


def active(g):return combine(g,'layoutactive',[get(g,'UIOpen'),call(g,'layoutname',STR+'EqualEqual_StrStr',{'A':get(g,'ActivePanel')},B='layouts')])
def names(g):return get(g,'PresetNames')
def entries(g,node,document):return prop(g,node,LAYOUT,'Entries',document)
def ready(g):
    g.call('ready','self:CanEdit');branch(g,'allowed',combine(g,'allowedcheck',['ready.Ready',active(g)]));g.chain('entry','ready','allowed')


def ensure():
    g=Graph();branch(g,'exists',validity(g,'valid',get(g,'PresetService')));g.node('self','self')
    obj=call(g,'create',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=PRESETS);g.node('cast','cast',**{'class':PRESETS});g.wire((obj,'cast.Object'));set_value(g,'remember','PresetService','cast.AsBP Den Presets')
    set_value(g,'key',PRESETS+':LibraryKey',get(g,'PresetStorageKey'));g.wire((get(g,'PresetService'),'key.self'))
    g.chain('entry','exists','key');g.chain('exists.else','create','cast','remember','key');return g.function('EnsurePresetService')


def feedback():
    g=Graph();branch(g,'panel',validity(g,'panelvalid',get(g,'LayoutsPanel')));text(g,'message','LayoutsPanel','Footer',value=get(g,'LayoutMessage'))
    found=call(g,'selected',STR+'NotEqual_StrStr',{'A':get(g,'SelectedPreset')},B='');g.call('ready','self:CanEdit')
    enabled=combine(g,'enabled',['ready.Ready',found,op(g,'healthy','LessEqual_IntInt',get(g,'PresetListStatus'),B=2)])
    previous='message'
    for field in ['LoadPreset','DeletePreset']:
        call(g,field,WIDGET+':SetIsEnabled',{'self':widget(g,field+'widget','LayoutsPanel',field),'bInIsEnabled':enabled});g.chain(previous,field);previous=field
    g.chain('entry','panel','ready','message');return g.function('RefreshLayoutFeedback')


def refresh():
    g=Graph();g.call('ensure','self:EnsurePresetService');clear(g,'rows','PresetRows');clear(g,'names','PresetNames');set_value(g,'revision','PresetListRevision',op(g,'nextrev','Add_IntInt',get(g,'PresetListRevision'),B=1))
    branch(g,'panel',validity(g,'panelvalid',get(g,'LayoutsPanel')));call(g,'clearlist',LIST+':ClearListItems',{'self':widget(g,'list','LayoutsPanel','Presets')})
    method(g,'open',PRESETS,'OpenLibrary',get(g,'PresetService'));set_value(g,'status','PresetListStatus','open.Status');branch(g,'healthy',op(g,'usable','LessEqual_IntInt','open.Status',B=2))
    set_value(g,'id','PresetLibraryID',prop(g,'libraryid',LIBRARY,'ContentID','open.Library'));method(g,'listnames',PRESETS,'ListPresets',get(g,'PresetService'));set_value(g,'copy','PresetNames','listnames.Names')
    arr(g,'length','Length',names(g));g.get('i','local:PresetCursor');branch(g,'more',op(g,'within','Less_IntInt','i.PresetCursor','length.ReturnValue'));arr(g,'name','Get',names(g));g.wire(('i.PresetCursor','name.Index'))
    key=join(g,'key',number(g,'revstr',get(g,'PresetListRevision')),prefix(g,'index',':',number(g,'idxstr','i.PresetCursor')))
    g.call('item','self:NewCatalogItem');g.wire((key,'item.Key'),('name.Item','item.Title'));arr(g,'keep','Add',get(g,'PresetRows'));g.wire(('item.Item','keep.NewItem'))
    branch(g,'addpanel',validity(g,'addvalid',get(g,'LayoutsPanel')));call(g,'add',LIST+':AddItem',{'self':widget(g,'view','LayoutsPanel','Presets'),'Item':'item.Item'})
    set_value(g,'next','local:PresetCursor',op(g,'advance','Add_IntInt','i.PresetCursor',B=1))
    arr(g,'selected','Contains',names(g));g.wire((get(g,'SelectedPreset'),'selected.ItemToFind'));branch(g,'stillselected','selected.ReturnValue');g.set('deselect','SelectedPreset','');g.call('labels','self:RefreshLayoutFeedback')
    g.set('error','LayoutMessage','The preset library could not be read. Existing files have been kept.');g.set('clearid','PresetLibraryID','')
    g.chain('entry','ensure','rows','names','revision','panel','clearlist','open','status','healthy','id','listnames','copy','more','item','keep','addpanel','add','next','more');g.chain('panel.else','open');g.chain('addpanel.else','next');g.chain('more.else','stillselected','labels');g.chain('stillselected.else','deselect','labels');g.chain('healthy.else','clearid','error','deselect')
    return g.function('RefreshLayoutPresets',locals=[v('PresetCursor','int','0')])


def changed():
    g=Graph();branch(g,'active',active(g));g.call('refresh','self:RefreshLayoutPresets');g.call('scope','self:RefreshLayoutScope');g.chain('entry','active','refresh','scope');return g.function('LayoutsPanelChanged')


def read_key():
    g=Graph();branch(g,'active',active(g));call(g,'split',STR+'Split',{'SourceString':'entry.Key'},InStr=':',SearchCase='CaseSensitive',SearchDir='FromStart');branch(g,'parsed','split.ReturnValue')
    revision=call(g,'revision',STR+'Conv_StringToInt',{'InString':'split.LeftS'});index=call(g,'index',STR+'Conv_StringToInt',{'InString':'split.RightS'});arr(g,'length','Length',names(g))
    checks=[op(g,'same','EqualEqual_IntInt',revision,get(g,'PresetListRevision')),op(g,'min','GreaterEqual_IntInt',index,B=0),op(g,'max','Less_IntInt',index,'length.ReturnValue')]
    for name,value,source in [('revexact',revision,'split.LeftS'),('idxexact',index,'split.RightS')]:checks.append(call(g,name,STR+'EqualEqual_StrStr',{'A':source,'B':number(g,name+'str',value)}))
    branch(g,'valid',combine(g,'checks',checks));arr(g,'item','Get',names(g));g.wire((index,'item.Index'));set_value(g,'found','local:PresetNameCopy','item.Item');g.set('yes','local:OK','true');finish_bool(g);g.get('nameout','local:PresetNameCopy');g.wire(('nameout.PresetNameCopy','result.Name'))
    g.chain('entry','active','parsed','valid','found','yes','result')
    for pin in ['active.else','parsed.else','valid.else']:g.chain(pin,'result')
    return g.function('ReadPresetCard',inputs=[v('Key','string')],outputs=[v('Accepted','bool'),v('Name','string')],locals=[v('OK','bool','false'),v('PresetNameCopy','string')])


def select():
    g=Graph();g.call('read','self:ReadPresetCard');g.wire(('entry.Key','read.Key'));branch(g,'valid','read.Accepted');set_value(g,'selected','SelectedPreset','read.Name');set_value(g,'message','LayoutMessage',prefix(g,'label','Selected preset: ','read.Name'));g.call('labels','self:RefreshLayoutFeedback');g.chain('entry','read','valid','selected','message','labels');return g.function('SelectPresetCard',inputs=[v('Key','string')])


def library_current():
    g=Graph();method(g,'open',PRESETS,'OpenLibrary',get(g,'PresetService'));branch(g,'healthy',op(g,'usable','LessEqual_IntInt','open.Status',B=2))
    branch(g,'same',call(g,'match',STR+'EqualEqual_StrStr',{'A':prop(g,'id',LIBRARY,'ContentID','open.Library'),'B':get(g,'PresetLibraryID')}));g.set('yes','local:OK','true');finish_bool(g)
    g.set('changed','LayoutMessage','The preset library changed. Choose the preset again.');g.call('refresh','self:RefreshLayoutPresets');g.chain('entry','open','healthy','same','yes','result');g.chain('healthy.else','changed','refresh','result');g.chain('same.else','changed')
    return g.function('PresetLibraryCurrent',outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def replacement():
    # Remove identities absent from the preset, then add changed/new values. Array
    # Contains uses the struct's native property equality, including material arrays.
    g=Graph();branch(g,'valid',validity(g,'targetvalid','entry.Document'));g.get('batch','local:ReplacementMutations');g.get('i','local:ReplacementCursor')
    current=entries(g,'current',get(g,'WorkingDocument'));target=entries(g,'target','entry.Document');arr(g,'count','Length',current);arr(g,'targetcount','Length',target)
    branch(g,'more',op(g,'within','Less_IntInt','i.ReplacementCursor','count.ReturnValue'));arr(g,'old','Get',current);g.wire(('i.ReplacementCursor','old.Index'));unpack(g,'oldvalue',ENTRY,'old.Item')
    method(g,'find',LAYOUT,'FindEntry','entry.Document',{'Kind':'oldvalue.Kind','Key':'oldvalue.Key'});branch(g,'absent',op(g,'missing','Less_IntInt','find.Index',B=0));g.node('remove','make_struct',struct=MUTATION,defaults={'Present':'false'});g.wire(('old.Item','remove.Value'));arr(g,'removeadd','Add','batch.ReplacementMutations');g.wire(('remove.ST_DenMutation','removeadd.NewItem'))
    set_value(g,'next','local:ReplacementCursor',op(g,'increment','Add_IntInt','i.ReplacementCursor',B=1));g.set('reset','local:ReplacementCursor','0')
    branch(g,'targetmore',op(g,'targetwithin','Less_IntInt','i.ReplacementCursor','targetcount.ReturnValue'));arr(g,'new','Get',target);g.wire(('i.ReplacementCursor','new.Index'));arr(g,'contains','Contains',current);g.wire(('new.Item','contains.ItemToFind'));branch(g,'same','contains.ReturnValue')
    g.node('write','make_struct',struct=MUTATION,defaults={'Present':'true'});g.wire(('new.Item','write.Value'));arr(g,'writeadd','Add','batch.ReplacementMutations');g.wire(('write.ST_DenMutation','writeadd.NewItem'));set_value(g,'targetnext','local:ReplacementCursor',op(g,'targetincrement','Add_IntInt','i.ReplacementCursor',B=1))
    g.wire(('batch.ReplacementMutations','result.Mutations'));g.chain('entry','valid','more','find','absent','removeadd','next','more');g.chain('absent.else','next');g.chain('more.else','reset','targetmore','same','targetnext','targetmore');g.chain('same.else','writeadd','targetnext');g.chain('targetmore.else','result');g.chain('valid.else','result')
    return g.function('BuildPresetReplacement',inputs=[v('Document','object:'+LAYOUT)],outputs=[v('Mutations','struct:'+MUTATION+'[]')],locals=[v('ReplacementMutations','struct:'+MUTATION+'[]'),v('ReplacementCursor','int','0')])


def load():
    g=Graph();ready(g);g.call('current','self:PresetLibraryCurrent');branch(g,'fresh','current.Accepted');method(g,'load',PRESETS,'LoadPreset',get(g,'PresetService'),{'Name':'entry.Name'})
    branch(g,'loaded',combine(g,'loadedcheck',[validity(g,'docvalid','load.Document'),op(g,'statusvalid','LessEqual_IntInt','load.Status',B=2)]));g.call('replacement','self:BuildPresetReplacement');g.wire(('load.Document','replacement.Document'));arr(g,'count','Length','replacement.Mutations');branch(g,'any',op(g,'nonempty','Greater_IntInt','count.ReturnValue',B=0))
    g.call('clear','self:ClearSelection');g.call('commit','self:CommitEdit');g.wire(('replacement.Mutations','commit.Mutations'),(prefix(g,'label','Load preset ','entry.Name'),'commit.Label'));branch(g,'accepted','commit.Accepted');g.set('success','LayoutMessage','Preset applied. Save keeps it; Undo restores your previous layout.');g.set('same','LayoutMessage','This preset already matches your layout.');g.set('failure','LayoutMessage','The preset could not be applied. Your current layout has been kept.');g.call('labels','self:RefreshLayoutFeedback')
    g.chain('allowed','current','fresh','load','loaded','replacement','any','clear','commit','accepted','success','labels');g.chain('any.else','same','labels');g.chain('loaded.else','failure','labels');g.chain('accepted.else','failure')
    return g.function('LoadEditorPreset',inputs=[v('Name','string')])


def save():
    g=Graph();ready(g);g.call('current','self:PresetLibraryCurrent');branch(g,'fresh','current.Accepted');method(g,'save',PRESETS,'SavePreset',get(g,'PresetService'),{'Name':'entry.Name','Document':get(g,'WorkingDocument')});branch(g,'saved',op(g,'success','EqualEqual_IntInt','save.Status',B=1));set_value(g,'selected','SelectedPreset','save.CleanName');set_value(g,'message','LayoutMessage',prefix(g,'caption','Saved preset: ','save.CleanName'));g.call('refresh','self:RefreshLayoutPresets');g.set('failure','LayoutMessage','Preset not saved. Use a name of 1–40 characters and check that mod storage is writable.');g.call('labels','self:RefreshLayoutFeedback')
    g.chain('allowed','current','fresh','save','saved','selected','message','refresh');g.chain('saved.else','failure','labels');return g.function('SaveEditorPreset',inputs=[v('Name','string')])


def delete():
    g=Graph();ready(g);g.call('current','self:PresetLibraryCurrent');branch(g,'fresh','current.Accepted');method(g,'delete',PRESETS,'DeletePreset',get(g,'PresetService'),{'Name':'entry.Name'});branch(g,'deleted',op(g,'success','EqualEqual_IntInt','delete.Status',B=1));g.set('selected','SelectedPreset','');set_value(g,'message','LayoutMessage',prefix(g,'caption','Deleted preset: ','entry.Name'));g.call('refresh','self:RefreshLayoutPresets');g.set('failure','LayoutMessage','The preset could not be deleted. Existing files have been kept.');g.call('labels','self:RefreshLayoutFeedback')
    g.chain('allowed','current','fresh','delete','deleted','selected','message','refresh');g.chain('deleted.else','failure','labels');return g.function('DeleteEditorPreset',inputs=[v('Name','string')])


def request_delete():
    g=Graph();ready(g);g.call('current','self:PresetLibraryCurrent');branch(g,'fresh','current.Accepted');g.call('confirm','self:ShowLayoutConfirmation',Action='delete_preset',Title='Delete this preset?',Button='Delete preset');g.wire(('entry.Name','confirm.Name'),(prefix(g,'message','This removes the preset from the list. A previous library copy remains in backups. Preset: ','entry.Name'),'confirm.Message'));g.chain('allowed','current','fresh','confirm');return g.function('RequestDeletePreset',inputs=[v('Name','string')])


def show_confirm():
    g=Graph();set_value(g,'action','PendingLayoutAction','entry.Action');set_value(g,'name','PendingLayoutName','entry.Name');set_value(g,'version','PendingLayoutVersion',prop(g,'historyversion',HISTORY,'Version',get(g,'History')));set_value(g,'generation','PendingLayoutGeneration',get(g,'Generation'));g.call('mode','self:SetEditorConfirm',Mode=5);branch(g,'panel',validity(g,'toolbarvalid',get(g,'Toolbar')))
    for node,field,value in [('title','ConfirmTitle','entry.Title'),('message','ConfirmText','entry.Message'),('button','ConfirmSaveLabel','entry.Button')]:text(g,node,'Toolbar',field,value=value)
    text(g,'cancel','Toolbar','ConfirmCancelLabel',constant='Keep editing');visibility(g,'hide',widget(g,'discard','Toolbar','ConfirmDiscard'),'Collapsed');g.chain('entry','action','name','version','generation','mode','panel','title','message','button','cancel','hide')
    return g.function('ShowLayoutConfirmation',inputs=[v(n,'string') for n in ['Action','Name','Title','Message','Button']])


def confirmation():
    g=Graph();branch(g,'mode',op(g,'layoutmode','EqualEqual_IntInt',get(g,'ConfirmMode'),B=5));set_value(g,'action','local:ConfirmedAction',get(g,'PendingLayoutAction'));set_value(g,'name','local:ConfirmedName',get(g,'PendingLayoutName'));g.call('clear','self:SetEditorConfirm',Mode=0);g.set('reset','PendingLayoutAction','')
    branch(g,'fresh',combine(g,'unchanged',[op(g,'version','EqualEqual_IntInt',get(g,'PendingLayoutVersion'),prop(g,'historyversion',HISTORY,'Version',get(g,'History'))),op(g,'generation','EqualEqual_IntInt',get(g,'PendingLayoutGeneration'),get(g,'Generation'))]));g.get('actionout','local:ConfirmedAction');g.get('nameout','local:ConfirmedName')
    branch(g,'delete',call(g,'deleteaction',STR+'EqualEqual_StrStr',{'A':'actionout.ConfirmedAction'},B='delete_preset'));g.call('run','self:DeleteEditorPreset');g.wire(('nameout.ConfirmedName','run.Name'));g.set('stale','LayoutMessage','The layout changed while this question was open. Choose the action again.');g.call('labels','self:RefreshLayoutFeedback')
    branch(g,'deletecomposition',call(g,'compositiondelete',STR+'EqualEqual_StrStr',{'A':'actionout.ConfirmedAction'},B='delete_composition'));g.call('runcompositiondelete','self:DeleteEditorComposition');g.wire(('nameout.ConfirmedName','runcompositiondelete.Name'));branch(g,'replacecomposition',call(g,'compositionreplace',STR+'EqualEqual_StrStr',{'A':'actionout.ConfirmedAction'},B='replace_composition'));g.call('runcompositionreplace','self:WriteCapturedComposition');g.chain('entry','mode','action','name','clear','reset','fresh','deletecomposition','runcompositiondelete');g.chain('deletecomposition.else','replacecomposition','runcompositionreplace');g.chain('replacecomposition.else','delete','run');g.chain('fresh.else','stale','labels');branch(g,'home',call(g,'homeaction',STR+'EqualEqual_StrStr',{'A':'actionout.ConfirmedAction'},B='scope_home'));g.call('usehome','self:UseEditorHomeLayout');g.chain('delete.else','home','usehome');return g.function('ConfirmLayoutAction',locals=[v('ConfirmedAction','string'),v('ConfirmedName','string')])


def queue():
    g=Graph();branch(g,'open',active(g));branch(g,'save',call(g,'saveaction',STR+'EqualEqual_StrStr',{'A':'entry.Name'},B='save_preset'));set_value(g,'arg','local:QueuedArgument','entry.Argument');arr(g,'find','Find',names(g));g.wire((get(g,'SelectedPreset'),'find.ItemToFind'));branch(g,'selected',op(g,'found','GreaterEqual_IntInt','find.ReturnValue',B=0));set_value(g,'selectedarg','local:QueuedArgument',join(g,'key',number(g,'revision',get(g,'PresetListRevision')),prefix(g,'index',':',number(g,'idx','find.ReturnValue'))))
    g.node('event','make_struct',struct=EVENT,defaults={'Kind':'2'});g.get('argument','local:QueuedArgument');g.wire(('entry.Name','event.EventName'),('argument.QueuedArgument','event.Argument'));g.call('queue','self:QueueEditorMutation',RequireSelection='false');g.wire(('event.ST_DenEditorEvent','queue.Event'));g.set('missing','LayoutMessage','Select a preset first.');g.call('labels','self:RefreshLayoutFeedback')
    g.chain('entry','open','save','arg','queue');g.chain('save.else','selected','selectedarg','queue');g.chain('selected.else','missing','labels');return g.function('QueuePresetAction',inputs=[v('Name','string'),v('Argument','string')],locals=[v('QueuedArgument','string')])


def run_action():
    g=Graph();branch(g,'save',call(g,'saveaction',STR+'EqualEqual_StrStr',{'A':'entry.Name'},B='save_preset'));g.call('savepreset','self:SaveEditorPreset');g.wire(('entry.Argument','savepreset.Name'));g.call('read','self:ReadPresetCard');g.wire(('entry.Argument','read.Key'));branch(g,'valid','read.Accepted');branch(g,'load',call(g,'loadaction',STR+'EqualEqual_StrStr',{'A':'entry.Name'},B='load_preset'))
    for node,fn in [('loadpreset','LoadEditorPreset'),('deletepreset','RequestDeletePreset')]:g.call(node,'self:'+fn);g.wire(('read.Name',node+'.Name'))
    g.set('stale','LayoutMessage','This preset list changed. Select the preset again.');g.call('labels','self:RefreshLayoutFeedback');g.chain('entry','save','savepreset');g.chain('save.else','read','valid','load','loadpreset');g.chain('load.else','deletepreset');g.chain('valid.else','stale','labels')
    return g.function('RunPresetAction',inputs=[v('Name','string'),v('Argument','string')])


def variables():return [v('PresetService','object:'+PRESETS),v('PresetStorageKey','string','presets'),v('PresetNames','string[]'),v('PresetRows','object:'+ITEM+'[]'),v('PresetListRevision','int'),v('PresetListStatus','int'),v('PresetLibraryID','string'),v('SelectedPreset','string'),v('LayoutMessage','string'),v('PendingLayoutAction','string'),v('PendingLayoutName','string'),v('PendingLayoutVersion','int'),v('PendingLayoutGeneration','int')]
def functions():return [ensure(),feedback(),refresh(),changed(),read_key(),select(),library_current(),replacement(),load(),save(),delete(),request_delete(),show_confirm(),confirmation(),queue(),run_action()]
