"""Community areas retain widget values and a separately reviewed upload snapshot."""
from graph import Graph, variable as v, KML
from runtime import LAYOUT, ENTRY, arr, unpack
from runtime_store import call, branch, combine, STR
from runtime_apply import get
from runtime_world import set_value, validity
from runtime_session import prop, method
from runtime_layout_ui import PRESETS
from runtime_editor_host import text, widget, visibility
from runtime_gizmo_controller import op


def area():
    g=Graph();set_value(g,'remember','CommunityArea','entry.Area');branch(g,'panel',validity(g,'panelalive',get(g,'CommunityPanel')));g.chain('remember','panel');previous='panel'
    for field,value in [('BrowseArea','browse'),('UploadArea','upload'),('DenArea','den'),('AccountArea','account'),('BrowseDenArea','browse_dens')]:
        branch(g,field,call(g,field+'match',STR+'EqualEqual_StrStr',{'A':'entry.Area'},B=value))
        visibility(g,field+'show',widget(g,field+'widget','CommunityPanel',field),'Visible');visibility(g,field+'hide',widget(g,field+'hidden','CommunityPanel',field),'Collapsed')
        g.node(field+'done','sequence',outputs=1);g.chain(previous,field,field+'show',field+'done');g.chain(field+'.else',field+'hide',field+'done');previous=field+'done.then_0'
    branch(g,'cards',call(g,'upload',STR+'EqualEqual_StrStr',{'A':'entry.Area'},B='upload'))
    for field in ['CommunitySources','LibraryTitle']:
        visibility(g,field+'show',widget(g,field+'widget','CommunityPanel',field),'Visible');visibility(g,field+'hide',widget(g,field+'hidden','CommunityPanel',field),'Collapsed')
    branch(g,'denrefresh',call(g,'dencheck',STR+'EqualEqual_StrStr',{'A':'entry.Area'},B='den'));g.call('refreshdens','self:RefreshCommunityDens');g.chain('entry','remember');g.chain('LibraryTitlehide','denrefresh','refreshdens');g.chain(previous,'cards','CommunitySourcesshow','LibraryTitleshow');g.chain('cards.else','CommunitySourceshide','LibraryTitlehide')
    return g.function('SetCommunityArea',inputs=[v('Area','string')])


def read(g,field):
    return call(g,field+'string','/Script/Engine.KismetTextLibrary:Conv_TextToString',{'InText':call(g,field+'read','/Script/UMG.EditableTextBox:GetText',{'self':widget(g,field+'widget','CommunityPanel',field)})})


def report_value(g):
    g.get('reportvalue','local:ReviewReport') if not any(n['id']=='reportvalue' for n in g.nodes) else None
    return 'reportvalue.ReviewReport'


def requirements():
    g=Graph();branch(g,'document',validity(g,'doc','entry.Document'));rows=prop(g,'entries',LAYOUT,'Entries','entry.Document');arr(g,'count','Length',rows)
    g.get('i','local:RequirementCursor');g.get('report','local:RequirementReport');branch(g,'more',op(g,'within','Less_IntInt','i.RequirementCursor','count.ReturnValue'))
    arr(g,'part','Get',rows);g.wire(('i.RequirementCursor','part.Index'));unpack(g,'partdata',ENTRY,'part.Item')
    label=call(g,'meshlabel',KML+':SelectString',{'bPickA':call(g,'reviewed',STR+'EqualEqual_StrStr',{'A':'partdata.Mesh'},B='/Game/Game/Environments/Strategy/HQ/Props/Control/Control_Monitor_A.Control_Monitor_A')},A='\nReviewed base game mesh: ',B='\nUNKNOWN mesh/pack coverage: ')
    value=call(g,'mesh',STR+'Concat_StrStr',{'A':label,'B':'partdata.Mesh'});set_value(g,'append','local:RequirementReport',call(g,'appendtext',STR+'Concat_StrStr',{'A':'report.RequirementReport','B':value}))
    g.set('mireset','local:RequirementMaterialCursor','0');g.get('mi','local:RequirementMaterialCursor');arr(g,'mc','Length','partdata.Materials');branch(g,'mmore',op(g,'mwithin','Less_IntInt','mi.RequirementMaterialCursor','mc.ReturnValue'));arr(g,'mat','Get','partdata.Materials');g.wire(('mi.RequirementMaterialCursor','mat.Index'))
    mat=call(g,'matlabel',STR+'Concat_StrStr',{'B':'mat.Item'},A='\nMaterial (UNKNOWN pack coverage; empty = mesh default): ')
    set_value(g,'mappend','local:RequirementReport',call(g,'mappendtext',STR+'Concat_StrStr',{'A':'report.RequirementReport','B':mat}));set_value(g,'mnext','local:RequirementMaterialCursor',op(g,'madd','Add_IntInt','mi.RequirementMaterialCursor',B=1));set_value(g,'next','local:RequirementCursor',op(g,'add','Add_IntInt','i.RequirementCursor',B=1))
    g.wire(('report.RequirementReport','result.Report'));g.chain('entry','document','more','append','mireset','mmore','mappend','mnext','mmore');g.chain('mmore.else','next','more');g.chain('more.else','result');g.chain('document.else','result')
    return g.function('BuildCommunityRequirements',inputs=[v('Document','object:'+LAYOUT)],outputs=[v('Report','string')],locals=[v('RequirementCursor','int','0'),v('RequirementMaterialCursor','int','0'),v('RequirementReport','string','Requirements detected from saved part values. Service coverage and installed assets are validated independently.')])


def review():
    g=Graph();g.set('reset','CommunityUploadJSON','');g.call('ensure','self:EnsureCompositionService');g.call('fresh','self:CommunitySourceCurrent');branch(g,'freshcheck','fresh.Accepted')
    arr(g,'contains','Contains',get(g,'CommunitySourceNames'));g.wire((get(g,'CommunitySourceName'),'contains.ItemToFind'));branch(g,'selected','contains.ReturnValue')
    method(g,'load',PRESETS,'LoadPreset',get(g,'CompositionService'),{'Name':get(g,'CommunitySourceName')});branch(g,'loaded',validity(g,'doc','load.Document'))
    g.call('build','self:BuildCommunitySubmission');g.wire(('load.Document','build.Document'));branch(g,'built','build.Ready')
    set_value(g,'json','CommunityUploadJSON','build.JSON');set_value(g,'name','CommunityUploadName',get(g,'CommunitySourceName'));set_value(g,'revision','CommunityUploadLibraryID',get(g,'CommunitySourceLibraryID'))
    arr(g,'index','Find',get(g,'CommunitySourceNames'));g.wire((get(g,'CommunitySourceName'),'index.ItemToFind'));arr(g,'row','Get',get(g,'CommunitySourceRows'));g.wire(('index.ReturnValue','row.Index'))
    from runtime_catalog_ui import ITEM
    g.call('filename','self:CommunityThumbnailName');g.wire((prop(g,'path',ITEM,'AssetPath','row.Item'),'filename.Path'));set_value(g,'thumb','CommunityUploadThumbnail','filename.FileName')
    g.call('review','self:BuildCommunityRequirements');g.wire(('load.Document','review.Document'));text(g,'requirements','CommunityPanel','PublishRequirements',value='review.Report')
    arr(g,'count','Length',prop(g,'entries',LAYOUT,'Entries','load.Document'));count=call(g,'countstring',STR+'Conv_IntToString',{'InInt':'count.ReturnValue'});label=call(g,'namecount',STR+'Concat_StrStr',{'A':get(g,'CommunityUploadName'),'B':call(g,'countlabel',STR+'Concat_StrStr',{'A':call(g,'countprefix',STR+'Concat_StrStr',{'B':count},A=' · ')},B=' saved parts')})
    text(g,'selection','CommunityPanel','UploadSelection',value=label)
    g.set('message','CommunityMessage','Saved snapshot reviewed. Enter metadata and Publish. Cached thumbnail is required.');g.set('invalid','CommunityMessage','Saved selection is stale or unavailable. Select a card and review again.');g.call('feedback','self:RefreshCommunityFeedback')
    g.chain('entry','reset','ensure','fresh','freshcheck','selected','load','loaded','build','built','json','name','revision','filename','thumb','review','requirements','selection','message','feedback')
    for pin in ['freshcheck.else','selected.else','loaded.else','built.else']:g.chain(pin,'invalid','feedback')
    return g.function('ReviewCommunityComposition')


def external():
    g=Graph();call(g,'open','/Script/Engine.KismetSystemLibrary:LaunchURL',URL='https://share.zcom.app/account');g.chain('entry','open');return g.function('OpenCommunityAccount')


def copy(url):
    g=Graph();branch(g,'hascode',call(g,'notempty',STR+'NotEqual_StrStr',{'A':get(g,'CommunityPublicCode')},B=''))
    command=call(g,'command',STR+'Concat_StrStr',{'B':get(g,'CommunityPublicCode')},A='COPYURL/' if url else 'COPYCODE/')
    g.call('copy','self:StartCommunityFetch');g.wire((command,'copy.Input'));branch(g,'idle',call(g,'notpending',KML+':Not_PreBool',{'A':get(g,'CommunityPending')}));g.chain('entry','idle','hascode','copy');return g.function('CopyCommunityURL' if url else 'CopyCommunityCode')


def dens():
    from runtime_catalog_ui import LIST
    g=Graph();g.call('refresh','self:RefreshLayoutPresets');call(g,'clear',LIST+':ClearListItems',{'self':widget(g,'list','CommunityPanel','CommunityDenPresets')})
    g.get('i','local:CommunityDenCursor');arr(g,'count','Length',get(g,'PresetRows'));branch(g,'more',op(g,'within','Less_IntInt','i.CommunityDenCursor','count.ReturnValue'));arr(g,'row','Get',get(g,'PresetRows'));g.wire(('i.CommunityDenCursor','row.Index'))
    call(g,'add',LIST+':AddItem',{'self':widget(g,'listadd','CommunityPanel','CommunityDenPresets'),'Item':'row.Item'});set_value(g,'next','local:CommunityDenCursor',op(g,'inc','Add_IntInt','i.CommunityDenCursor',B=1));g.chain('entry','refresh','clear','more','add','next','more');return g.function('RefreshCommunityDens',locals=[v('CommunityDenCursor','int','0')])


def select_den():
    from runtime_layout_ui import read_key
    spec=read_key();spec['name']='ReadCommunityDenCard'
    next(n for n in spec['nodes'] if n['id']=='layoutname')['defaults']['B']='community'
    return spec


def den_selected():
    g=Graph();g.call('read','self:ReadCommunityDenCard');g.wire(('entry.Key','read.Key'));branch(g,'valid','read.Accepted');set_value(g,'keep','CommunityDenName','read.Name');text(g,'label','CommunityPanel','CommunityDenSelected',value=call(g,'caption',STR+'Concat_StrStr',{'A':'read.Name'},B=' · saved preset selected; Full Den publishing unavailable.'));g.chain('entry','read','valid','keep','label');return g.function('SelectCommunityDen',inputs=[v('Key','string')])


def save_den():
    g=Graph();g.call('ready','self:CanEdit');branch(g,'readycheck',combine(g,'readychecks',[get(g,'UIOpen'),'ready.Ready']));g.call('ensure','self:EnsurePresetService');g.call('current','self:PresetLibraryCurrent');branch(g,'fresh','current.Accepted')
    method(g,'normalize',PRESETS,'NormalizeName',get(g,'PresetService'),{'Name':read(g,'DenPresetName')});branch(g,'valid','normalize.Valid');arr(g,'contains','Contains',get(g,'PresetNames'));g.wire(('normalize.CleanName','contains.ItemToFind'));branch(g,'exists','contains.ReturnValue')
    method(g,'save',PRESETS,'SavePreset',get(g,'PresetService'),{'Name':'normalize.CleanName','Document':get(g,'WorkingDocument')});branch(g,'saved',op(g,'success','EqualEqual_IntInt','save.Status',B=1));g.call('refresh','self:RefreshCommunityDens');text(g,'label','CommunityPanel','CommunityDenSelected',constant='Current Den saved as a new preset. Select it above. Publishing remains unavailable.')
    text(g,'error','CommunityPanel','CommunityDenSelected',constant='Preset not saved. Choose a NEW name of 1–40 characters and retry; existing presets are kept.')
    g.chain('entry','ready','readycheck','ensure','current','fresh','normalize','valid','exists');g.chain('exists.else','save','saved','refresh','label')
    for pin in ['fresh.else','valid.else','exists.then','saved.else']:g.chain(pin,'error')
    return g.function('SaveCommunityDenPreset')


def variables():return [v('CommunityArea','string','browse'),v('CommunityMessage','string')]+[v(n,'string') for n in ['CommunityUploadJSON','CommunityUploadName','CommunityUploadLibraryID','CommunityUploadThumbnail','CommunityPublicURL','CommunityPublicCode','CommunityProfile','CommunityDenName']]
def functions():return [area(),requirements(),review(),external(),copy(True),copy(False),dens(),select_den(),den_selected(),save_den()]
