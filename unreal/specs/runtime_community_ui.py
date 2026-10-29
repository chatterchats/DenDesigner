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
from runtime_community_mailbox import HOLONET, split, item, eq, length
from runtime_catalog_ui import ITEM, LIST, number, join, prefix


def connected(g,name='connected'):
    """The last account message says whether a key is connected."""
    return call(g,name,STR+'StartsWith',{'SourceString':get(g,'CommunityProfile')},InPrefix='Connected',SearchCase='CaseSensitive')


def area():
    from runtime_holonet_widget import AREAS, RAIL_BROWSE, RAIL_YOURS
    from runtime_editor_host import style_toggle
    g=Graph();set_value(g,'remember','CommunityArea','entry.Area');branch(g,'panel',validity(g,'panelalive',get(g,'CommunityPanel')));g.chain('entry','remember','panel');previous='panel'
    for field,value in AREAS:
        branch(g,field,call(g,field+'match',STR+'EqualEqual_StrStr',{'A':'entry.Area'},B=value))
        visibility(g,field+'show',widget(g,field+'widget','CommunityPanel',field),'Visible');visibility(g,field+'hide',widget(g,field+'hidden','CommunityPanel',field),'Collapsed')
        g.node(field+'done','sequence',outputs=1);g.chain(previous,field,field+'show',field+'done');g.chain(field+'.else',field+'hide',field+'done');previous=field+'done.then_0'
    for name,_,event,_ in RAIL_BROWSE+RAIL_YOURS:
        value={'community_browse':'browse','community_browse_dens':'browse_dens','community_upload':'upload','holonet_shares':'shares','community_account':'account'}[event]
        style_toggle(g,'rail'+name,'CommunityPanel',name,call(g,'on'+name,STR+'EqualEqual_StrStr',{'A':'entry.Area'},B=value));g.chain(previous,'rail'+name);previous='rail'+name
    subtitle=call(g,'subtitledefault',STR+'Concat_StrStr',A='Builds shared by other captains',B='')
    for value,label in [('browse_dens','Dens'),('upload','Share a build'),('shares','My Shares'),('account','Account')]:
        subtitle=call(g,'subtitle'+value,KML+':SelectString',{'B':subtitle,'bPickA':call(g,'is'+value,STR+'EqualEqual_StrStr',{'A':'entry.Area'},B=value)},A=label)
    text(g,'subtitle','CommunityPanel','HolonetSubtitle',value=subtitle);g.chain(previous,'subtitle');previous='subtitle'
    branch(g,'upload',call(g,'uploadarea',STR+'EqualEqual_StrStr',{'A':'entry.Area'},B='upload'));g.call('share','self:RefreshHolonetShare')
    branch(g,'shares',call(g,'sharesarea',STR+'EqualEqual_StrStr',{'A':'entry.Area'},B='shares'));g.call('loadshares','self:EnsureHolonetShares')
    g.call('style','self:StyleHolonetBrowse')
    g.chain(previous,'style','upload','share');g.chain('upload.else','shares','loadshares')
    return g.function('SetCommunityArea',inputs=[v('Area','string')])


def read(g,field):
    if any(n['id']==field+'string' for n in g.nodes):return field+'string.ReturnValue'
    return call(g,field+'string','/Script/Engine.KismetTextLibrary:Conv_TextToString',{'InText':call(g,field+'read','/Script/UMG.EditableTextBox:GetText',{'self':widget(g,field+'widget','CommunityPanel',field)})})


def report_value(g):
    g.get('reportvalue','local:ReviewReport') if not any(n['id']=='reportvalue' for n in g.nodes) else None
    return 'reportvalue.ReviewReport'


def requirements():
    """What someone needs to use this build: the base game, prop packs (by
    title) or assets from other mods."""
    from runtime_catalog import CATALOG
    g=Graph();branch(g,'document',validity(g,'doc','entry.Document'));rows=prop(g,'entries',LAYOUT,'Entries','entry.Document');arr(g,'count','Length',rows)
    g.get('i','local:RequirementCursor');g.get('paths','local:Paths');branch(g,'more',op(g,'within','Less_IntInt','i.RequirementCursor','count.ReturnValue'))
    arr(g,'part','Get',rows);g.wire(('i.RequirementCursor','part.Index'));unpack(g,'partdata',ENTRY,'part.Item')
    arr(g,'addmesh','Add','paths.Paths');g.wire(('partdata.Mesh','addmesh.NewItem'))
    g.set('mireset','local:RequirementMaterialCursor','0');g.get('mi','local:RequirementMaterialCursor');arr(g,'mc','Length','partdata.Materials');branch(g,'mmore',op(g,'mwithin','Less_IntInt','mi.RequirementMaterialCursor','mc.ReturnValue'));arr(g,'mat','Get','partdata.Materials');g.wire(('mi.RequirementMaterialCursor','mat.Index'))
    branch(g,'nonempty',call(g,'hasmaterial',STR+'NotEqual_StrStr',{'A':'mat.Item'},B=''));arr(g,'addmaterial','Add','paths.Paths');g.wire(('mat.Item','addmaterial.NewItem'))
    set_value(g,'mnext','local:RequirementMaterialCursor',op(g,'madd','Add_IntInt','mi.RequirementMaterialCursor',B=1));set_value(g,'next','local:RequirementCursor',op(g,'add','Add_IntInt','i.RequirementCursor',B=1))
    branch(g,'catalog',validity(g,'catalogvalid',get(g,'CatalogProvider')))
    method(g,'describe',CATALOG,'DescribeSources',get(g,'CatalogProvider'),{'Paths':'paths.Paths'});g.wire(('describe.Summary','result.Report'))
    g.chain('entry','document','more','addmesh','mireset','mmore','nonempty','addmaterial','mnext','mmore');g.chain('nonempty.else','mnext');g.chain('mmore.else','next','more');g.chain('more.else','catalog','describe','result');g.chain('document.else','result');g.chain('catalog.else','result')
    return g.function('BuildCommunityRequirements',inputs=[v('Document','object:'+LAYOUT)],outputs=[v('Report','string')],locals=[v('RequirementCursor','int','0'),v('RequirementMaterialCursor','int','0'),v('Paths','string[]')])


def review():
    g=Graph();g.set('reset','CommunityUploadJSON','');g.call('ensure','self:EnsureCompositionService');g.call('fresh','self:CommunitySourceCurrent');branch(g,'freshcheck','fresh.Accepted')
    arr(g,'contains','Contains',get(g,'CommunitySourceNames'));g.wire((get(g,'CommunitySourceName'),'contains.ItemToFind'));branch(g,'selected','contains.ReturnValue')
    method(g,'load',PRESETS,'LoadPreset',get(g,'CompositionService'),{'Name':get(g,'CommunitySourceName')});branch(g,'loaded',validity(g,'doc','load.Document'))
    g.call('build','self:BuildCommunitySubmission');g.wire(('load.Document','build.Document'),('filename.FileName','build.Thumbnail'));branch(g,'built','build.Ready')
    set_value(g,'json','CommunityUploadJSON','build.JSON');set_value(g,'name','CommunityUploadName',get(g,'CommunitySourceName'));set_value(g,'revision','CommunityUploadLibraryID',get(g,'CommunitySourceLibraryID'))
    arr(g,'index','Find',get(g,'CommunitySourceNames'));g.wire((get(g,'CommunitySourceName'),'index.ItemToFind'));arr(g,'row','Get',get(g,'CommunitySourceRows'));g.wire(('index.ReturnValue','row.Index'))
    from runtime_catalog_ui import ITEM
    g.call('filename','self:CommunityThumbnailName');g.wire((prop(g,'path',ITEM,'AssetPath','row.Item'),'filename.Path'));set_value(g,'thumb','CommunityUploadThumbnail','filename.FileName')
    g.call('review','self:BuildCommunityRequirements');g.wire(('load.Document','review.Document'));text(g,'requirements','CommunityPanel','PublishRequirements',value='review.Report')
    arr(g,'count','Length',prop(g,'entries',LAYOUT,'Entries','load.Document'));count=call(g,'countstring',STR+'Conv_IntToString',{'InInt':'count.ReturnValue'});label=call(g,'namecount',STR+'Concat_StrStr',{'A':get(g,'CommunityUploadName'),'B':call(g,'countlabel',STR+'Concat_StrStr',{'A':call(g,'countprefix',STR+'Concat_StrStr',{'B':count},A=' · ')},B=' parts')})
    text(g,'selection','CommunityPanel','ShareSummary',value=label)
    g.set('message','CommunityMessage','Ready to share. Check the title, then Share.');g.set('invalid','CommunityMessage','That saved composition changed or is gone. Pick its card again.');g.call('feedback','self:RefreshCommunityFeedback')
    g.chain('entry','reset','ensure','fresh','freshcheck','selected','load','loaded','filename','build','built','json','name','revision','thumb','review','requirements','selection','message','feedback')
    for pin in ['freshcheck.else','selected.else','loaded.else','built.else']:g.chain(pin,'invalid','feedback')
    return g.function('ReviewCommunityComposition')


def external():
    g=Graph();call(g,'open','/Script/Engine.KismetSystemLibrary:LaunchURL',URL='https://'+HOLONET+'/account');g.chain('entry','open');return g.function('OpenCommunityAccount')


def copy(url):
    g=Graph();branch(g,'hascode',call(g,'notempty',STR+'NotEqual_StrStr',{'A':get(g,'CommunityPublicCode')},B=''))
    command=call(g,'command',STR+'Concat_StrStr',{'B':get(g,'CommunityPublicCode')},A='COPYURL/' if url else 'COPYCODE/')
    g.call('copy','self:StartCommunityFetch');g.wire((command,'copy.Input'));branch(g,'idle',call(g,'notpending',KML+':Not_PreBool',{'A':get(g,'CommunityPending')}));g.chain('entry','idle','hascode','copy');return g.function('CopyCommunityURL' if url else 'CopyCommunityCode')


def variables():return [v('CommunityArea','string','browse'),v('CommunityMessage','string'),v('HolonetShareTarget','int','-1'),v('HolonetShareUpdate','bool','false'),v('HolonetShowResult','bool','false'),
                         v('HolonetSharesPage','int'),v('HolonetSharesPages','int'),v('HolonetSharesTotal','int','-1'),v('HolonetSharesStale','bool','true'),v('HolonetShareRevisions','int[]'),
                         v('HolonetShareCodes','string[]'),v('HolonetShareTitles','string[]'),v('HolonetShareRows','object:'+ITEM+'[]')]+[v(n,'string') for n in ['CommunityUploadJSON','CommunityUploadName','CommunityUploadLibraryID','CommunityUploadThumbnail','CommunityPublicURL','CommunityPublicCode','CommunityProfile','CommunityDenName']]
def functions():return [area(),requirements(),review(),external(),copy(True),copy(False)]+share_functions()


def text_value(g,field):
    """A share text box, with backslashes doubled for the PUBLISH lines."""
    return call(g,field+'escaped',STR+'Replace',{'SourceString':read(g,field)},From='\\',To='\\\\',SearchCase='CaseSensitive')


def target(g,array,name):
    """HolonetShareTarget's entry in one of the My Shares arrays."""
    arr(g,name,'Get',get(g,array));g.wire((get(g,'HolonetShareTarget'),name+'.Index'));return name+'.Item'


def has_target(g,name='hastarget'):
    arr(g,name+'count','Length',get(g,'HolonetShareCodes'))
    return combine(g,name,[op(g,name+'min','GreaterEqual_IntInt',get(g,'HolonetShareTarget'),B=0),op(g,name+'max','Less_IntInt',get(g,'HolonetShareTarget'),name+'count.ReturnValue')])


def refresh_share():
    """Share a build: not connected, the form, or the result of the last share."""
    from runtime_editor_host import style_toggle
    g=Graph();branch(g,'panel',validity(g,'alive',get(g,'CommunityPanel')));g.chain('entry','panel')
    online=connected(g);updating=combine(g,'updating',[get(g,'HolonetShareUpdate'),has_target(g)])
    showresult=combine(g,'showresult',[get(g,'HolonetShowResult'),call(g,'hascode',STR+'NotEqual_StrStr',{'A':get(g,'CommunityPublicCode')},B='')])
    previous='panel'
    for node,field,show in [('offline','ShareOffline',call(g,'notonline',KML+':Not_PreBool',{'A':online})),('resultpanel','ShareResult',showresult),
                            ('form','ShareFormFields',combine(g,'formshown',[online,call(g,'noresult',KML+':Not_PreBool',{'A':showresult})])),
                            ('footer','ShareFooter',combine(g,'footershown',[online,call(g,'noresult2',KML+':Not_PreBool',{'A':showresult})])),
                            ('changelog','ChangelogBox',updating)]:
        branch(g,node,show);visibility(g,node+'show',widget(g,node+'widget','CommunityPanel',field),'Visible');visibility(g,node+'hide',widget(g,node+'hidden','CommunityPanel',field),'Collapsed')
        g.node(node+'done','sequence',outputs=1);g.chain(previous,node,node+'show',node+'done');g.chain(node+'.else',node+'hide',node+'done');previous=node+'done.then_0'
    style_toggle(g,'styleupdate','CommunityPanel','ShareUpdate',updating);style_toggle(g,'stylenew','CommunityPanel','ShareNew',call(g,'notupdating',KML+':Not_PreBool',{'A':updating}))
    g.chain(previous,'styleupdate','stylenew');previous='stylenew'
    title=target(g,'HolonetShareTitles','targettitle');code=target(g,'HolonetShareCodes','targetcode');revision=target(g,'HolonetShareRevisions','targetrevision')
    update=join(g,'updatelabel',prefix(g,'updateprefix','Update ',title),join(g,'updatecode',prefix(g,'codeprefix',' · ',code),call(g,'updaterev',STR+'Concat_StrStr',{'A':prefix(g,'revprefix',' (becomes revision ',number(g,'nextrev',op(g,'plusone','Add_IntInt',revision,B=1)))},B=')')))
    branch(g,'targeted',has_target(g,'hastarget2'))
    text(g,'updatelabel2','CommunityPanel','ShareUpdateLabel',value=update);text(g,'pickfirst','CommunityPanel','ShareUpdateLabel',constant='Update an existing share (pick it in My Shares)')
    note=call(g,'note',STR+'Concat_StrStr',{'A':call(g,'notehead',STR+'Concat_StrStr',A='Shares the saved copy of this composition, not your unsaved edits. Sharing as ',B=''),'B':call(g,'who',STR+'Replace',{'SourceString':call(g,'firstpart',STR+'Replace',{'SourceString':get(g,'CommunityProfile')},From=' - Remembered connection.',To='',SearchCase='CaseSensitive')},From='Connected as ',To='',SearchCase='CaseSensitive')})
    text(g,'notetext','CommunityPanel','ShareNote',value=call(g,'notedot',STR+'Concat_StrStr',{'A':note},B='.'))
    text(g,'submitlabel','CommunityPanel','SubmitCommunityLabel',value=call(g,'submit',KML+':SelectString',{'bPickA':updating},A='Share update',B='Share'))
    g.chain(previous,'targeted','updatelabel2','notetext','submitlabel');g.chain('targeted.else','pickfirst','notetext')
    return g.function('RefreshHolonetShare')


def pick_source():
    g=Graph();g.call('select','self:SelectCommunitySourceCard');g.wire(('entry.Key','select.Key'));g.call('share','self:ShareChosenSource');g.chain('entry','select','share')
    return g.function('PickHolonetSource',inputs=[v('Key','string')])


def chosen_source():
    """Review the chosen saved composition at once and suggest the share to
    update: the one with the same title, if any. A typed title is kept."""
    g=Graph();g.set('fresh','HolonetShowResult','false');g.call('review','self:ReviewCommunityComposition')
    branch(g,'empty',call(g,'notitle',STR+'EqualEqual_StrStr',{'A':read(g,'PublishTitle')},B=''))
    call(g,'title','/Script/UMG.EditableTextBox:SetText',{'self':widget(g,'titlewidget','CommunityPanel','PublishTitle'),'InText':get(g,'CommunityUploadName')})
    g.get('i','local:Cursor');arr(g,'count','Length',get(g,'HolonetShareTitles'));branch(g,'more',op(g,'within','Less_IntInt','i.Cursor','count.ReturnValue'))
    arr(g,'name','Get',get(g,'HolonetShareTitles'));g.wire(('i.Cursor','name.Index'))
    branch(g,'same',call(g,'match',STR+'EqualEqual_StriStri',{'A':'name.Item','B':get(g,'CommunityUploadName')}))
    set_value(g,'pick','HolonetShareTarget','i.Cursor');g.set('update','HolonetShareUpdate','true')
    set_value(g,'next','local:Cursor',op(g,'inc','Add_IntInt','i.Cursor',B=1));g.set('none','HolonetShareUpdate','false');g.set('notarget','HolonetShareTarget','-1')
    g.call('refresh','self:RefreshHolonetShare');g.call('stale','self:EnsureHolonetShares')
    g.chain('entry','fresh','stale','review','empty','title','more','same','pick','update','refresh');g.chain('empty.else','more');g.chain('same.else','next','more');g.chain('more.else','none','notarget','refresh')
    return g.function('ShareChosenSource',locals=[v('Cursor','int','0')])


def share_selected():
    """Share on the Compositions panel: open HoloNet's Share a build with the
    selected saved composition picked."""
    g=Graph();branch(g,'selected',call(g,'hasselection',STR+'NotEqual_StrStr',{'A':get(g,'SelectedComposition')},B=''))
    g.call('open','self:SetEditorPanel',Name='community');g.call('area','self:SetCommunityArea',Area='upload');g.call('sources','self:RefreshCommunitySources')
    set_value(g,'pick','CommunitySourceName',get(g,'SelectedComposition'));g.call('share','self:ShareChosenSource')
    g.set('none','CompositionMessage','Select a saved composition card first.');g.call('labels','self:RefreshCompositionFeedback')
    g.chain('entry','selected','open','area','sources','pick','share');g.chain('selected.else','none','labels')
    return g.function('ShareSelectedComposition')


def share_mode(update):
    g=Graph()
    if update:
        branch(g,'targeted',has_target(g));g.set('on','HolonetShareUpdate','true');g.call('refresh','self:RefreshHolonetShare')
        g.set('message','CommunityMessage','Pick the share to update in My Shares.');g.call('feedback','self:RefreshCommunityFeedback');g.call('shares','self:SetCommunityArea',Area='shares')
        g.chain('entry','targeted','on','refresh');g.chain('targeted.else','message','feedback','shares')
    else:
        g.set('off','HolonetShareUpdate','false');g.call('refresh','self:RefreshHolonetShare');g.chain('entry','off','refresh')
    return g.function('ShareHolonetUpdate' if update else 'ShareHolonetNew')


def submit():
    """PUBLISH: the card render (the 512 px share render when it exists), then
    title, description, update and What changed lines, then the payload."""
    g=Graph();g.call('ready','self:CanEdit');branch(g,'available',combine(g,'availablecheck',[get(g,'UIOpen'),'ready.Ready']))
    g.call('ensure','self:EnsureCompositionService');g.call('current','self:CommunitySourceCurrent');branch(g,'fresh','current.Accepted')
    branch(g,'reviewed',combine(g,'reviewchecks',[call(g,'hasreview',STR+'NotEqual_StrStr',{'A':get(g,'CommunityUploadJSON')},B=''),call(g,'samerevision',STR+'EqualEqual_StrStr',{'A':get(g,'CommunityUploadLibraryID'),'B':get(g,'CommunitySourceLibraryID')})]))
    branch(g,'titled',call(g,'hastitle',STR+'NotEqual_StrStr',{'A':call(g,'trimmed',STR+'Trim',{'SourceString':read(g,'PublishTitle')})},B=''))
    large=call(g,'large',STR+'Replace',{'SourceString':get(g,'CommunityUploadThumbnail')},From='.png',To='_512.png',SearchCase='CaseSensitive')
    path=call(g,'largepath',STR+'Concat_StrStr',{'A':call(g,'thumbs',STR+'Concat_StrStr',{'A':call(g,'saved','/Script/Engine.KismetSystemLibrary:GetProjectSavedDirectory')},B='ZComDen/thumbs/'),'B':large})
    thumb=call(g,'thumb',KML+':SelectString',{'A':large,'B':get(g,'CommunityUploadThumbnail'),'bPickA':call(g,'haslarge','/Script/Engine.BlueprintPathsLibrary:FileExists',{'InPath':path})})
    updating=combine(g,'updating',[get(g,'HolonetShareUpdate'),has_target(g)])
    update=join(g,'updateline',prefix(g,'updatehead','\nupdate\t',target(g,'HolonetShareCodes','targetcode')),join(g,'updaterev',prefix(g,'revhead','\t',number(g,'revtext',target(g,'HolonetShareRevisions','targetrevision'))),prefix(g,'changehead','\nchangelog\t',text_value(g,'PublishChangelog'))))
    wire=join(g,'w1',thumb,prefix(g,'titlehead','\ntitle\t',text_value(g,'PublishTitle')))
    wire=join(g,'w2',wire,prefix(g,'deschead','\ndescription\t',text_value(g,'PublishDescription')))
    branch(g,'isupdate',updating);set_value(g,'keepupdate','local:UpdateLines',update);g.get('updatelines','local:UpdateLines')
    wire=join(g,'w3',wire,'updatelines.UpdateLines')
    wire=join(g,'w4',wire,prefix(g,'payloadhead','\npayload\n',get(g,'CommunityUploadJSON')))
    g.set('noresult','HolonetShowResult','false')
    g.call('start','self:StartCommunityTransfer',Input='PUBLISH');g.wire((wire,'start.Payload'))
    g.set('message','CommunityMessage','Sharing on HoloNet… Cancel stops it.');g.call('refresh','self:RefreshCommunityFeedback');g.call('form','self:RefreshHolonetShare')
    g.set('unsupported','CommunityMessage','The saved composition changed, or none is picked. Pick its card again. Your text is kept.')
    g.set('untitled','CommunityMessage','Give the build a title first.')
    g.chain('entry','ready','available','ensure','current','fresh','reviewed','titled','isupdate','keepupdate','noresult','start','message','refresh','form');g.chain('isupdate.else','noresult')
    g.chain('fresh.else','unsupported','refresh');g.chain('reviewed.else','unsupported');g.chain('titled.else','untitled','refresh')
    return g.function('SubmitCommunityComposition',locals=[v('UpdateLines','string','')])


def ensure_shares():
    g=Graph();branch(g,'stale',combine(g,'needed',[get(g,'HolonetSharesStale'),connected(g)]));g.call('load','self:LoadHolonetShares');g.chain('entry','stale','load')
    return g.function('EnsureHolonetShares')


def load_shares():
    g=Graph();branch(g,'online',connected(g));g.call('available','self:CanStartCommunityBrowse');branch(g,'allowed','available.Allowed')
    g.call('start','self:StartCommunityTransfer',Payload='request');g.wire((prefix(g,'command','MYSHARES/',number(g,'page',get(g,'HolonetSharesPage'))),'start.Input'))
    text(g,'loading','CommunityPanel','SharesStatus',constant='Loading your shares…');text(g,'offline','CommunityPanel','SharesStatus',constant='Connect in Account to see your shares.')
    g.chain('entry','online','available','allowed','start','loading');g.chain('online.else','offline')
    return g.function('LoadHolonetShares')


def read_shares():
    """shares\t<page>\t<pages>\t<total>, then share\t<code>\t<title>\t<revision>\t<imports>\t<public|hidden>\t<updated>."""
    g=Graph();lines=get(g,'CommunityWireLines');header=split(g,'header',item(g,'line',lines,1),'\t');branch(g,'headerok',length(g,'headercount',header,4))
    set_value(g,'pages','HolonetSharesPages',call(g,'pagesvalue',STR+'Conv_StringToInt',{'InString':item(g,'pagestext',header,2)}))
    set_value(g,'total','HolonetSharesTotal',call(g,'totalvalue',STR+'Conv_StringToInt',{'InString':item(g,'totaltext',header,3)}))
    previous='total'
    for name in ['HolonetShareCodes','HolonetShareTitles','HolonetShareRevisions','HolonetShareRows']:
        arr(g,'clear'+name,'Clear',get(g,name));g.chain(previous,'clear'+name);previous='clear'+name
    call(g,'clearlist',LIST+':ClearListItems',{'self':widget(g,'list','CommunityPanel','ShareListings')});g.chain(previous,'clearlist')
    g.get('i','local:Cursor');arr(g,'count','Length',lines);branch(g,'more',op(g,'within','Less_IntInt','i.Cursor','count.ReturnValue'))
    arr(g,'shareline','Get',lines);g.wire(('i.Cursor','shareline.Index'));fields=split(g,'fields','shareline.Item','\t')
    branch(g,'row',combine(g,'rowcheck',[eq(g,'shareword',item(g,'tag',fields,0),'share'),length(g,'fieldcount',fields,7)]))
    code=item(g,'code',fields,1);title=item(g,'title',fields,2);revision=item(g,'revision',fields,3)
    hidden=eq(g,'hidden',item(g,'visibility',fields,5),'hidden')
    caption=join(g,'c1',title,join(g,'c2',prefix(g,'codesep','  ·  ',code),join(g,'c3',prefix(g,'revsep','  ·  revision ',revision),join(g,'c4',prefix(g,'impsep','  ·  imports: ',item(g,'imports',fields,4)),call(g,'vis',KML+':SelectString',{'bPickA':hidden},A='  ·  Hidden',B='  ·  Public')))))
    arr(g,'index','Length',get(g,'HolonetShareCodes'))
    g.call('new','self:NewCatalogItem');g.wire((prefix(g,'key','share:',number(g,'keyindex','index.ReturnValue')),'new.Key'),(caption,'new.Title'))
    previous='new'
    for name,value in [('HolonetShareCodes',code),('HolonetShareTitles',title),('HolonetShareRevisions',call(g,'revint',STR+'Conv_StringToInt',{'InString':revision})),('HolonetShareRows','new.Item')]:
        arr(g,'add'+name,'Add',get(g,name));g.wire((value,'add'+name+'.NewItem'));g.chain(previous,'add'+name);previous='add'+name
    call(g,'show',LIST+':AddItem',{'self':widget(g,'listadd','CommunityPanel','ShareListings'),'Item':'new.Item'});g.chain(previous,'show')
    set_value(g,'next','local:Cursor',op(g,'inc','Add_IntInt','i.Cursor',B=1))
    g.set('fresh','HolonetSharesStale','false');g.set('pending','CommunityPending','false');g.call('release','self:ReleaseCommunityMailbox')
    status=join(g,'status',prefix(g,'pageprefix','Page ',number(g,'pagenum',op(g,'onebased','Add_IntInt',get(g,'HolonetSharesPage'),B=1))),join(g,'statustotal',prefix(g,'of',' of ',number(g,'pagesnum',get(g,'HolonetSharesPages'))),prefix(g,'totalprefix',' · shares: ',number(g,'totalnum',get(g,'HolonetSharesTotal')))))
    status=call(g,'statustext',KML+':SelectString',{'A':status,'bPickA':op(g,'any','Greater_IntInt',get(g,'HolonetSharesTotal'),B=0)},B='You haven’t shared anything yet. Pick Share a build.')
    text(g,'statusset','CommunityPanel','SharesStatus',value=status)
    text(g,'countset','CommunityPanel','SharesCount',value=call(g,'counttext',KML+':SelectString',{'A':prefix(g,'countprefix','Shares: ',number(g,'countnum',get(g,'HolonetSharesTotal'))),'bPickA':op(g,'known','GreaterEqual_IntInt',get(g,'HolonetSharesTotal'),B=0)},B=''))
    g.call('share','self:RefreshHolonetShare')
    g.chain('entry','headerok','pages','total');g.chain('clearlist','more','row','new');g.chain('show','next','more');g.chain('row.else','next')
    g.chain('more.else','fresh','pending','release','statusset','countset','share')
    return g.function('ReadHolonetShares',locals=[v('Cursor','int','2')])


def shares_page(next):
    g=Graph();target_page=op(g,'target','Add_IntInt' if next else 'Subtract_IntInt',get(g,'HolonetSharesPage'),B=1)
    branch(g,'bounded',combine(g,'bounds',[op(g,'min','GreaterEqual_IntInt',target_page,B=0),op(g,'max','Less_IntInt',target_page,get(g,'HolonetSharesPages'))]))
    set_value(g,'page','HolonetSharesPage',target_page);g.call('load','self:LoadHolonetShares');g.chain('entry','bounded','page','load')
    return g.function('NextHolonetShares' if next else 'PreviousHolonetShares')


def reload_shares():
    g=Graph();g.set('stale','HolonetSharesStale','true');g.call('load','self:LoadHolonetShares');g.chain('entry','stale','load');return g.function('ReloadHolonetShares')


def pick_share():
    """Picking one of My Shares opens Share a build as an update of it."""
    g=Graph();call(g,'split',STR+'Split',{'SourceString':'entry.Key'},InStr=':',SearchCase='CaseSensitive',SearchDir='FromStart');branch(g,'splitok','split.ReturnValue')
    index=call(g,'index',STR+'Conv_StringToInt',{'InString':'split.RightS'});arr(g,'count','Length',get(g,'HolonetShareCodes'))
    branch(g,'bounds',combine(g,'boundscheck',[op(g,'min','GreaterEqual_IntInt',index,B=0),op(g,'max','Less_IntInt',index,'count.ReturnValue')]))
    set_value(g,'target','HolonetShareTarget',index);g.set('update','HolonetShareUpdate','true');g.set('fresh','HolonetShowResult','false')
    g.set('message','CommunityMessage','Now pick the saved composition to share as the update, then Share update.');g.call('feedback','self:RefreshCommunityFeedback')
    g.call('area','self:SetCommunityArea',Area='upload')
    g.chain('entry','splitok','bounds','target','update','fresh','message','feedback','area')
    return g.function('PickHolonetShare',inputs=[v('Key','string')])


def share_functions():return [refresh_share(),pick_source(),chosen_source(),share_selected(),share_mode(True),share_mode(False),submit(),ensure_shares(),load_shares(),read_shares(),shares_page(True),shares_page(False),reload_shares(),pick_share()]
