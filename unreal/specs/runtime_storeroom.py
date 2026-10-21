"""Native stored/dormant listings and transactional restore/forget commands."""
from graph import Graph, variable as v, KML
from runtime import ENTRY, MUTATION, LAYOUT, arr, unpack
from runtime_store import call, branch, combine, STR
from runtime_world import set_value, validity, finish_bool
from runtime_apply import get, clear, clock
from runtime_session import prop, method, HISTORY
from runtime_transform import copy_entry
from runtime_catalog import CATALOG
from runtime_catalog_ui import ITEM
from runtime_editor_assets import EVENT
from runtime_editor_host import text, widget, WIDGET
from runtime_gizmo_controller import op, neg

LIST='/Script/UMG.ListView'


def active(g):return combine(g,'storeroomactive',[get(g,'UIOpen'),call(g,'storeroomname',STR+'EqualEqual_StrStr',{'A':get(g,'ActivePanel')},B='storeroom')])
def version(g):return prop(g,'historyversion',HISTORY,'Version',get(g,'History'))
def entries(g):
    if any(n['id']=='storeentries' for n in g.nodes):return 'storeentries.Entries'
    return prop(g,'storeentries',LAYOUT,'Entries',get(g,'WorkingDocument'))
def string(g,name,value):return call(g,name,STR+'Conv_IntToString',{'InInt':value})
def concat(g,name,a,b):return call(g,name,STR+'Concat_StrStr',{'A':a,'B':b})


def classify():
    g=Graph();unpack(g,'entryvalue',ENTRY,'entry.Value');g.get('status','local:EntryStatus');g.wire(('status.EntryStatus','result.Status'))
    branch(g,'stored',op(g,'kindstored','EqualEqual_IntInt','entryvalue.Kind',B=1));g.set('yes','local:EntryStatus','1')
    branch(g,'native',op(g,'kindnative','EqualEqual_IntInt','entryvalue.Kind',B=2));g.call('record','self:FindRecord');g.wire(('entryvalue.Key','record.Key'));branch(g,'bound',op(g,'recordfound','GreaterEqual_IntInt','record.Index',B=0));branch(g,'hidden','entryvalue.Hidden');g.set('missing','local:EntryStatus','2')
    branch(g,'placed',op(g,'kindplaced','EqualEqual_IntInt','entryvalue.Kind',B=0));g.call('find','self:FindPlaced');g.wire(('entryvalue.Key','find.Key'));branch(g,'absent',op(g,'missingplaced','Less_IntInt','find.Index',B=0))
    g.chain('entry','stored','yes','result');g.chain('stored.else','native','record','bound','hidden','yes');g.chain('bound.else','missing','result');g.chain('hidden.else','result');g.chain('native.else','placed','find','absent','missing');g.chain('placed.else','result');g.chain('absent.else','result')
    return g.function('ClassifyStoreroomEntry',inputs=[v('Value','struct:'+ENTRY)],outputs=[v('Status','int')],locals=[v('EntryStatus','int','0')])


def clear_listing():
    g=Graph();g.set('stop','StoreBuilding','false');previous='stop'
    for field in ['StoredRows','DormantRows','StoredIndexes','DormantIndexes']:
        clear(g,field,field);g.chain(previous,field);previous=field
    branch(g,'panel',validity(g,'panelvalid',get(g,'StoreroomPanel')))
    for field in ['Stored','Dormant']:call(g,field+'clear',LIST+':ClearListItems',{'self':widget(g,field+'list','StoreroomPanel',field)})
    g.chain('entry','stop');g.chain(previous,'panel','Storedclear','Dormantclear');return g.function('ClearStoreroomListing')


def begin():
    g=Graph();g.call('clear','self:ClearStoreroomListing');g.call('thumbs','self:CancelThumbnailRequests');g.call('catalog','self:EnsureCatalog')
    set_value(g,'revision','StoreRevision',op(g,'nextrev','Add_IntInt',get(g,'StoreRevision'),B=1));set_value(g,'version','StoreSeenVersion',version(g));set_value(g,'generation','StoreSeenGeneration',get(g,'Generation'))
    g.set('cursor','StoreCursor','0');g.set('count','StoreTotal','0');g.set('start','StoreBuilding','true');g.chain('entry','clear','thumbs','catalog','revision','version','generation','cursor','count','start');return g.function('BeginStoreroomListing')


def label():
    g=Graph();unpack(g,'value',ENTRY,'entry.Value');mesh=call(g,'mesh',KML+':SelectString',{'A':'value.Mesh','B':'value.FingerprintMesh','bPickA':call(g,'hasmesh',STR+'NotEqual_StrStr',{'A':'value.Mesh'},B='')});g.wire((mesh,'result.Mesh'))
    method(g,'find',CATALOG,'FindPath',get(g,'CatalogProvider'),{'Path':mesh});branch(g,'catalog',op(g,'exists','GreaterEqual_IntInt','find.Index',B=0));method(g,'read',CATALOG,'ReadItem',get(g,'CatalogProvider'),{'Index':'find.Index'});set_value(g,'title','local:ResolvedTitle','read.Label')
    source=call(g,'source',KML+':SelectString',{'A':mesh,'B':'value.Key','bPickA':call(g,'nonempty',STR+'NotEqual_StrStr',{'A':mesh},B='')});call(g,'split',STR+'Split',{'SourceString':source},InStr='.',SearchCase='CaseSensitive',SearchDir='FromEnd')
    candidate=call(g,'fallback',KML+':SelectString',{'A':'split.RightS','B':source,'bPickA':'split.ReturnValue'});prefix=call(g,'prefix',STR+'StartsWith',{'SourceString':candidate},InPrefix='SM_');trimmed=call(g,'trimmed',STR+'RightChop',{'SourceString':candidate},Count=3);name=call(g,'name',KML+':SelectString',{'A':trimmed,'B':candidate,'bPickA':prefix});name=call(g,'spaces',STR+'Replace',{'SourceString':name},From='_',To=' ');set_value(g,'fallbacktitle','local:ResolvedTitle',name)
    g.get('out','local:ResolvedTitle');g.wire(('out.ResolvedTitle','result.Title'));g.chain('entry','find','catalog','read','title','result');g.chain('catalog.else','fallbacktitle','result')
    return g.function('StoreroomLabel',inputs=[v('Value','struct:'+ENTRY)],outputs=[v('Title','string'),v('Mesh','string')],locals=[v('ResolvedTitle','string')])


def step():
    g=Graph();arr(g,'count','Length',entries(g));branch(g,'more',op(g,'within','Less_IntInt',get(g,'StoreCursor'),'count.ReturnValue'));arr(g,'value','Get',entries(g));g.wire((get(g,'StoreCursor'),'value.Index'))
    g.call('classify','self:ClassifyStoreroomEntry');g.wire(('value.Item','classify.Value'));branch(g,'relevant',op(g,'positive','Greater_IntInt','classify.Status',B=0));g.call('label','self:StoreroomLabel');g.wire(('value.Item','label.Value'))
    branch(g,'stored',op(g,'isstored','EqualEqual_IntInt','classify.Status',B=1));set_value(g,'total','StoreTotal',op(g,'incrementcount','Add_IntInt',get(g,'StoreTotal'),B=1))
    hay=call(g,'lower',STR+'ToLower',{'SourceString':concat(g,'hay','label.Title','label.Mesh')});query=call(g,'query',STR+'ToLower',{'SourceString':get(g,'StoreQuery')});branch(g,'matches',call(g,'contains',STR+'Contains',{'SearchIn':hay,'Substring':query},bUseCase='true'))
    key=concat(g,'key',string(g,'revision',get(g,'StoreRevision')),concat(g,'suffix',call(g,'colon',STR+'Concat_StrStr',{},A=':',B=''),string(g,'index',get(g,'StoreCursor'))))
    unpack(g,'entrydata',ENTRY,'value.Item');detail=call(g,'detail',KML+':SelectString',{'bPickA':op(g,'added','EqualEqual_IntInt','entrydata.Kind',B=1)},A='Added prop · click to restore',B='Den prop · click to restore')
    g.call('storeditem','self:NewCatalogItem',Preview='Preview unavailable');g.wire((key,'storeditem.Key'),('label.Title','storeditem.Title'),('label.Mesh','storeditem.AssetPath'),(detail,'storeditem.Detail'))
    g.call('dormantitem','self:NewCatalogItem',Detail='Not applied in this Den · click to forget');g.wire((key,'dormantitem.Key'),('label.Title','dormantitem.Title'),('label.Mesh','dormantitem.AssetPath'))
    for name,rows,indexes,field in [('stored','StoredRows','StoredIndexes','Stored'),('dormant','DormantRows','DormantIndexes','Dormant')]:
        arr(g,name+'keep','Add',get(g,rows));g.wire((name+'item.Item',name+'keep.NewItem'));arr(g,name+'index','Add',get(g,indexes));g.wire((get(g,'StoreCursor'),name+'index.NewItem'));branch(g,name+'panel',validity(g,name+'valid',get(g,'StoreroomPanel')));call(g,name+'add',LIST+':AddItem',{'self':widget(g,name+'list','StoreroomPanel',field),'Item':name+'item.Item'});g.chain(name+'item',name+'keep',name+'index',name+'panel',name+'add','next');g.chain(name+'panel.else','next')
    set_value(g,'next','StoreCursor',op(g,'advance','Add_IntInt',get(g,'StoreCursor'),B=1));g.set('stop','StoreBuilding','false')
    g.chain('entry','more','classify','relevant','label','stored','total','matches','storeditem');g.chain('stored.else','dormantitem');g.chain('matches.else','next');g.chain('relevant.else','next');g.chain('more.else','stop')
    return g.function('StoreroomListingStep')


def refresh_labels():
    g=Graph();branch(g,'panel',validity(g,'valid',get(g,'StoreroomPanel')));arr(g,'shown','Length',get(g,'StoredRows'));arr(g,'dormant','Length',get(g,'DormantRows'))
    caption=concat(g,'caption',string(g,'shownstr','shown.ReturnValue'),concat(g,'of',call(g,'ofprefix',STR+'Concat_StrStr',{'B':string(g,'total',get(g,'StoreTotal'))},A=' of '),call(g,'suffix',STR+'Concat_StrStr',{},A=' stored props · Click one to restore it.',B='')))
    label=call(g,'empty',KML+':SelectString',{'B':caption,'bPickA':op(g,'none','EqualEqual_IntInt',get(g,'StoreTotal'),B=0)},A='Your Storeroom is empty. Select a prop and choose Store to keep it here.')
    text(g,'stored','StoreroomPanel','StoredText',value=label)
    dormant=call(g,'dormantcaption',STR+'Concat_StrStr',{'A':string(g,'dormantstr','dormant.ReturnValue')},B=' edits could not be applied in this Den. They remain in your layout. Click one to forget it; Undo can bring it back.')
    dormant=call(g,'resolved',KML+':SelectString',{'B':dormant,'bPickA':op(g,'allfound','EqualEqual_IntInt','dormant.ReturnValue',B=0)},A='Every edit in this layout found its object.')
    text(g,'missing','StoreroomPanel','DormantText',value=dormant);text(g,'footer','StoreroomPanel','Footer',value=get(g,'StoreMessage'))
    call(g,'button',WIDGET+':SetIsEnabled',{'self':widget(g,'restoreall','StoreroomPanel','RestoreAll'),'bInIsEnabled':op(g,'any','Greater_IntInt',get(g,'StoreTotal'),B=0)})
    g.chain('entry','panel','stored','missing','footer','button');return g.function('RefreshStoreroomLabels')


def poll():
    g=Graph();branch(g,'open',active(g));g.call('ready','self:CanEdit');branch(g,'readycheck','ready.Ready')
    changed=combine(g,'changed',[op(g,'versionchanged','NotEqual_IntInt',version(g),get(g,'StoreSeenVersion')),op(g,'worldchanged','NotEqual_IntInt',get(g,'Generation'),get(g,'StoreSeenGeneration'))],True);branch(g,'changed',changed);g.call('begin','self:BeginStoreroomListing')
    branch(g,'building',get(g,'StoreBuilding'));set_value(g,'start','local:BatchStarted',clock(g,'now'));g.get('started','local:BatchStarted');g.get('steps','local:BatchSteps')
    branch(g,'loop',combine(g,'budget',[get(g,'StoreBuilding'),op(g,'time','Less_DoubleDouble',op(g,'elapsed','Subtract_DoubleDouble',clock(g,'timenow'),'started.BatchStarted'),B=.003),op(g,'stepsleft','Less_IntInt','steps.BatchSteps',B=16)]));g.call('step','self:StoreroomListingStep');set_value(g,'next','local:BatchSteps',op(g,'increment','Add_IntInt','steps.BatchSteps',B=1));branch(g,'done',neg(g,'complete',get(g,'StoreBuilding')));g.call('labels','self:RefreshStoreroomLabels')
    g.chain('entry','open','ready','readycheck','changed','begin','building','start','loop','step','next','loop');g.chain('changed.else','building');g.chain('loop.else','done','labels')
    return g.function('PollStoreroomUI',locals=[v('BatchStarted','double'),v('BatchSteps','int','0')])


def panel_changed():
    g=Graph();g.call('clear','self:ClearStoreroomListing');g.set('version','StoreSeenVersion','-1');g.chain('entry','clear','version');return g.function('StoreroomPanelChanged')


def search():
    g=Graph();branch(g,'active',active(g));set_value(g,'query','StoreQuery','entry.Text');g.set('version','StoreSeenVersion','-1');g.chain('entry','active','query','version');return g.function('SearchStoreroom',inputs=[v('Text','string')])


def validate():
    g=Graph();g.call('ready','self:CanEdit');branch(g,'readycheck',combine(g,'readyguard',['ready.Ready',active(g),neg(g,'complete',get(g,'StoreBuilding')),op(g,'currentversion','EqualEqual_IntInt',version(g),get(g,'StoreSeenVersion')),op(g,'currentgeneration','EqualEqual_IntInt',get(g,'Generation'),get(g,'StoreSeenGeneration'))]))
    call(g,'split',STR+'Split',{'SourceString':'entry.Key'},InStr=':',SearchCase='CaseSensitive',SearchDir='FromStart');branch(g,'splitok','split.ReturnValue')
    revision=call(g,'rev',STR+'Conv_StringToInt',{'InString':'split.LeftS'});index=call(g,'idx',STR+'Conv_StringToInt',{'InString':'split.RightS'})
    checks=[op(g,'same','EqualEqual_IntInt',revision,get(g,'StoreRevision')),call(g,'revexact',STR+'EqualEqual_StrStr',{'A':'split.LeftS','B':string(g,'revstr',revision)})]
    branch(g,'revision',combine(g,'revisioncheck',checks));branch(g,'all','entry.All')
    branch(g,'allkey',call(g,'alltext',STR+'EqualEqual_StrStr',{'A':'split.RightS'},B='all'))
    branch(g,'indexexact',call(g,'idxexact',STR+'EqualEqual_StrStr',{'A':'split.RightS','B':string(g,'idxstr',index)}))
    branch(g,'forget','entry.Forget');arr(g,'dormant','Contains',get(g,'DormantIndexes'));g.wire((index,'dormant.ItemToFind'));branch(g,'isdormant','dormant.ReturnValue')
    arr(g,'stored','Contains',get(g,'StoredIndexes'));g.wire((index,'stored.ItemToFind'));branch(g,'isstored','stored.ReturnValue')
    set_value(g,'indexout','local:ResultIndex',index);g.set('yes','local:OK','true');finish_bool(g);g.get('indexresult','local:ResultIndex');g.wire(('indexresult.ResultIndex','result.Index'))
    g.chain('entry','ready','readycheck','splitok','revision','all','allkey','yes','result');g.chain('all.else','indexexact','forget','isdormant','indexout','yes');g.chain('forget.else','isstored','indexout')
    for pin in ['readycheck.else','splitok.else','revision.else','allkey.else','indexexact.else','isdormant.else','isstored.else']:g.chain(pin,'result')
    return g.function('ValidateStoreroomAction',inputs=[v('Key','string'),v('Forget','bool'),v('All','bool')],outputs=[v('Accepted','bool'),v('Index','int')],locals=[v('OK','bool','false'),v('ResultIndex','int','-1')])


def restore_changes():
    g=Graph();unpack(g,'value',ENTRY,'entry.Value');g.get('batch','local:Restoration');g.call('classify','self:ClassifyStoreroomEntry');g.wire(('entry.Value','classify.Value'));branch(g,'stored',op(g,'isstored','EqualEqual_IntInt','classify.Status',B=1));branch(g,'added',op(g,'placedkind','EqualEqual_IntInt','value.Kind',B=1))
    method(g,'find',LAYOUT,'FindEntry',get(g,'WorkingDocument'),{'Key':'value.Key'},Kind=0);branch(g,'free',op(g,'absent','Less_IntInt','find.Index',B=0))
    g.node('remove','make_struct',struct=MUTATION,defaults={'Present':'false'});g.wire(('entry.Value','remove.Value'));arr(g,'removeadd','Add','batch.Restoration');g.wire(('remove.ST_DenMutation','removeadd.NewItem'))
    value=copy_entry(g,'placed','entry.Value',defaults={'Kind':'0'});g.node('place','make_struct',struct=MUTATION,defaults={'Present':'true'});g.wire((value,'place.Value'));arr(g,'placeadd','Add','batch.Restoration');g.wire(('place.ST_DenMutation','placeadd.NewItem'))
    native=copy_entry(g,'native','entry.Value',defaults={'Hidden':'false'});g.node('unhide','make_struct',struct=MUTATION);g.wire((native,'unhide.Value'),(combine(g,'transformed',['value.HasPosition','value.HasRotation','value.HasScale'],True),'unhide.Present'));arr(g,'nativeadd','Add','batch.Restoration');g.wire(('unhide.ST_DenMutation','nativeadd.NewItem'))
    g.set('yes','local:OK','true');finish_bool(g);g.wire(('batch.Restoration','result.Mutations'));g.chain('entry','classify','stored','added','find','free','removeadd','placeadd','yes','result');g.chain('added.else','nativeadd','yes');g.chain('stored.else','result');g.chain('free.else','result')
    return g.function('MakeRestoreChanges',inputs=[v('Value','struct:'+ENTRY)],outputs=[v('Accepted','bool'),v('Mutations','struct:'+MUTATION+'[]')],locals=[v('OK','bool','false'),v('Restoration','struct:'+MUTATION+'[]')])


def action():
    g=Graph();g.call('validate','self:ValidateStoreroomAction');g.wire(('entry.Key','validate.Key'),('entry.Forget','validate.Forget'),('entry.All','validate.All'));branch(g,'valid','validate.Accepted')
    g.get('batch','local:StoreMutations');branch(g,'all','entry.All');arr(g,'count','Length',entries(g));g.get('i','local:EntryCursor');branch(g,'more',op(g,'within','Less_IntInt','i.EntryCursor','count.ReturnValue'));arr(g,'allentry','Get',entries(g));g.wire(('i.EntryCursor','allentry.Index'));g.call('classify','self:ClassifyStoreroomEntry');g.wire(('allentry.Item','classify.Value'));branch(g,'eligible',op(g,'stored','EqualEqual_IntInt','classify.Status',B=1))
    g.call('restoreall','self:MakeRestoreChanges');g.wire(('allentry.Item','restoreall.Value'));branch(g,'allok','restoreall.Accepted');arr(g,'appendall','Append','batch.StoreMutations');g.wire(('restoreall.Mutations','appendall.SourceArray'));set_value(g,'next','local:EntryCursor',op(g,'increment','Add_IntInt','i.EntryCursor',B=1))
    arr(g,'oneentry','Get',entries(g));g.wire(('validate.Index','oneentry.Index'));branch(g,'forget','entry.Forget');g.node('remove','make_struct',struct=MUTATION,defaults={'Present':'false'});g.wire(('oneentry.Item','remove.Value'));arr(g,'appendremove','Add','batch.StoreMutations');g.wire(('remove.ST_DenMutation','appendremove.NewItem'))
    g.call('restore','self:MakeRestoreChanges');g.wire(('oneentry.Item','restore.Value'));branch(g,'oneok','restore.Accepted');arr(g,'appendone','Append','batch.StoreMutations');g.wire(('restore.Mutations','appendone.SourceArray'))
    arr(g,'length','Length','batch.StoreMutations');branch(g,'any',op(g,'nonempty','Greater_IntInt','length.ReturnValue',B=0));g.call('commit','self:CommitEdit');g.wire(('batch.StoreMutations','commit.Mutations'));label=call(g,'label',KML+':SelectString',{'bPickA':'entry.Forget'},A='Forget unavailable edit',B='Restore stored props');g.wire((label,'commit.Label'));branch(g,'accepted','commit.Accepted')
    g.set('message','StoreMessage','Done. Undo reverses this change.');g.set('invalid','StoreMessage','This list changed. Choose the prop again.');g.set('conflict','StoreMessage','A placed prop already uses that identity. Nothing was restored.');g.call('labels','self:RefreshStoreroomLabels')
    g.chain('entry','validate','valid','all','more','classify','eligible','restoreall','allok','appendall','next','more');g.chain('eligible.else','next');g.chain('more.else','any','commit','accepted','message','labels');g.chain('all.else','forget','appendremove','any');g.chain('forget.else','restore','oneok','appendone','any')
    g.chain('valid.else','invalid','labels');g.chain('allok.else','conflict','labels');g.chain('oneok.else','conflict');g.chain('accepted.else','invalid')
    return g.function('RunStoreroomAction',inputs=[v('Key','string'),v('Forget','bool'),v('All','bool')],locals=[v('StoreMutations','struct:'+MUTATION+'[]'),v('EntryCursor','int','0')])


def queue_action():
    g=Graph();branch(g,'open',active(g));g.node('event','make_struct',struct=EVENT,defaults={'Kind':'2'});g.wire(('entry.Name','event.EventName'));all=call(g,'all',STR+'EqualEqual_StrStr',{'A':'entry.Name'},B='restore_all')
    allkey=call(g,'allkey',STR+'Concat_StrStr',{'A':string(g,'revision',get(g,'StoreRevision'))},B=':all');arg=call(g,'argument',KML+':SelectString',{'A':allkey,'B':'entry.Key','bPickA':all});g.wire((arg,'event.Argument'));g.call('queue','self:QueueEditorMutation',RequireSelection='false');g.wire(('event.ST_DenEditorEvent','queue.Event'));g.chain('entry','open','queue');return g.function('QueueStoreroomAction',inputs=[v('Name','string'),v('Key','string')])


def variables():return [v('StoredRows','object:'+ITEM+'[]'),v('DormantRows','object:'+ITEM+'[]'),v('StoredIndexes','int[]'),v('DormantIndexes','int[]'),v('StoreQuery','string'),v('StoreMessage','string'),v('StoreBuilding','bool'),v('StoreCursor','int'),v('StoreRevision','int'),v('StoreTotal','int'),v('StoreSeenVersion','int','-1'),v('StoreSeenGeneration','int','-1')]
def functions():return [classify(),clear_listing(),begin(),label(),step(),refresh_labels(),poll(),panel_changed(),search(),validate(),restore_changes(),action(),queue_action()]
