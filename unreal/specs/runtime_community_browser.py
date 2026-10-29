"""Public browsing, immutable preview snapshots and explicit local downloads."""
from graph import Graph,variable as v,KML
from runtime import LAYOUT,arr
from runtime_store import call,branch,combine,STR
from runtime_apply import get
from runtime_world import validity,set_value
from runtime_session import prop
from runtime_editor_host import widget,text
from runtime_catalog_ui import ITEM,LIST,number,join,prefix
from runtime_gizmo_controller import op
from runtime_community_mailbox import split,item,eq,length


def active(g):return combine(g,'browseractive',[get(g,'UIOpen'),validity(g,'communitypanelalive',get(g,'CommunityPanel')),call(g,'communityactive',STR+'EqualEqual_StrStr',{'A':get(g,'ActivePanel')},B='community'),call(g,'browseactive',STR+'EqualEqual_StrStr',{'A':get(g,'CommunityArea')},B='browse')])


def refresh():
    g=Graph();branch(g,'active',active(g));g.call('available','self:CanStartCommunityBrowse');branch(g,'allowed','available.Allowed');g.call('cancel','self:CancelCommunityFetch')
    lists=['CommunityBrowseRows','CommunityBrowseCodes','CommunityBrowseDescriptions','CommunityBrowseRequirements','CommunityBrowseCreators','CommunityBrowseRevisions','CommunityBrowseDocuments','CommunityBrowseStates','CommunityBrowseParts','CommunityBrowseFootprints','CommunityBrowseDates','CommunityBrowseReady','CommunityBrowsePackURLs']
    for i,name in enumerate(lists):
        arr(g,'clear'+str(i),'Clear',get(g,name))
        g.chain('cancel' if not i else 'clear'+str(i-1),'clear'+str(i))
    call(g,'clearlist',LIST+':ClearListItems',{'self':widget(g,'list','CommunityPanel','CommunityListings')})
    command=prefix(g,'command','CATALOG/',number(g,'page',get(g,'CommunityBrowsePage')))
    # "<newest|imports>\t<all|base>\t<search>"; usability is filtered here, per page.
    payload=call(g,'payload',STR+'Concat_StrStr',{'A':call(g,'sortpart',STR+'Concat_StrStr',{'A':get(g,'CommunityBrowseSort')},B='\tall\t'),'B':get(g,'CommunityBrowseSearch')})
    g.call('start','self:StartCommunityTransfer');g.wire((command,'start.Input'),(payload,'start.Payload'))
    g.set('loaded','CommunityBrowseLoaded','true');g.set('selected','CommunityBrowseSelected','-1')
    text(g,'loading','CommunityPanel','GalleryStatus',constant='Loading builds…');g.chain('entry','active','available','allowed','cancel');g.call('cleardetail','self:RefreshCommunityDetail');g.chain('clear12','clearlist','start','loaded','selected','loading','cleardetail')
    return g.function('RefreshCommunityGallery')


def ensure():
    g=Graph();branch(g,'loaded',get(g,'CommunityBrowseLoaded'));g.call('refresh','self:RefreshCommunityGallery');g.chain('entry','loaded');g.chain('loaded.else','refresh');return g.function('EnsureCommunityGallery')


def search():
    g=Graph();branch(g,'safe',combine(g,'safequery',[op(g,'bounded','LessEqual_IntInt',call(g,'len',STR+'Len',{'S':'entry.Text'}),B=80),call(g,'notsecret',KML+':Not_PreBool',{'A':call(g,'secret',STR+'Contains',{'SearchIn':'entry.Text'},Substring='zcu_',bUseCase='false')})]))
    set_value(g,'query','CommunityBrowseSearch','entry.Text');g.set('page','CommunityBrowsePage','0');g.call('refresh','self:RefreshCommunityGallery');g.call('available','self:CanStartCommunityBrowse');branch(g,'allowed','available.Allowed');g.chain('entry','available','allowed','safe','query','page','refresh');return g.function('SearchCommunityGallery',inputs=[v('Text','string')])


def page(next):
    g=Graph();target=op(g,'target','Add_IntInt' if next else 'Subtract_IntInt',get(g,'CommunityBrowsePage'),B=1)
    branch(g,'bounded',combine(g,'bounds',[op(g,'min','GreaterEqual_IntInt',target,B=0),op(g,'max','Less_IntInt',target,get(g,'CommunityBrowsePages'))]))
    set_value(g,'page','CommunityBrowsePage',target);g.call('refresh','self:RefreshCommunityGallery');g.call('available','self:CanStartCommunityBrowse');branch(g,'allowed','available.Allowed');g.chain('entry','available','allowed','bounded','page','refresh');return g.function('NextCommunityPage' if next else 'PreviousCommunityPage')


def gallery():
    g=Graph();lines=get(g,'CommunityWireLines');header=split(g,'header',item(g,'line',lines,1),'\t')
    branch(g,'headerok',length(g,'headercount',header,4));pages=call(g,'pages',STR+'Conv_StringToInt',{'InString':item(g,'pagesvalue',header,2)});total=call(g,'total',STR+'Conv_StringToInt',{'InString':item(g,'totalvalue',header,3)})
    branch(g,'bounded',combine(g,'bounds',[op(g,'min','GreaterEqual_IntInt',pages,B=0),op(g,'max','LessEqual_IntInt',pages,B=10000)]))
    set_value(g,'pagecount','CommunityBrowsePages',pages);set_value(g,'totalcount','CommunityBrowseTotal',total);g.set('reset','CommunityPreviewCursor','0');g.get('i','local:GalleryCursor');arr(g,'count','Length',lines)
    branch(g,'more',op(g,'within','Less_IntInt','i.GalleryCursor','count.ReturnValue'))
    arr(g,'lineget','Get',lines);g.wire(('i.GalleryCursor','lineget.Index'));branch(g,'end',eq(g,'endword','lineget.Item','end'))
    g.call('add','self:AddCommunityListing');g.wire(('lineget.Item','add.Line'));set_value(g,'next','local:GalleryCursor',op(g,'inc','Add_IntInt','i.GalleryCursor',B=1))
    g.set('pending','CommunityPending','false');g.call('release','self:ReleaseCommunityMailbox');g.call('show','self:ShowCommunityListings')
    g.chain('entry','headerok','bounded','pagecount','totalcount','reset','more','end','pending','release','show');g.chain('end.else','add','next','more')
    return g.function('ReadCommunityGallery',locals=[v('GalleryCursor','int','2')])


def add_listing():
    """card rows start a listing; the pack rows after it say what it needs."""
    g=Graph();fields=split(g,'fields','entry.Line','\t');tag=item(g,'tag',fields,0)
    branch(g,'card',combine(g,'cardcheck',[eq(g,'cardword',tag,'card'),length(g,'cardcount',fields,12)]))
    arr(g,'count','Length',get(g,'CommunityBrowseRows'));branch(g,'room',op(g,'roomcheck','Less_IntInt','count.ReturnValue',B=24))
    code=item(g,'code',fields,1);title=item(g,'title',fields,2);creator=item(g,'creator',fields,3);parts=item(g,'parts',fields,4);revision=item(g,'rev',fields,5)
    base=eq(g,'base',item(g,'basevalue',fields,7),'1');unknown=op(g,'unknown','Greater_IntInt',call(g,'unknowncount',STR+'Conv_StringToInt',{'InString':item(g,'unknownvalue',fields,8)}),B=0)
    g.call('library','self:CommunityCodeInLibrary');g.wire((code,'library.Code'))
    detail=join(g,'detail',prefix(g,'by','by ',creator),join(g,'partcaption',prefix(g,'partprefix',' · ',parts),call(g,'inlibrary',KML+':SelectString',{'bPickA':'library.Found'},A=' parts · IN LIBRARY',B=' parts')))
    ready=call(g,'readytext',KML+':SelectString',{'bPickA':base},A='Ready to import · base game only',B='Ready to import')
    ready=call(g,'unknowntext',KML+':SelectString',{'A':call(g,'unknownjoin',STR+'Concat_StrStr',{'A':ready},B=' · some parts come from mods HoloNet doesn’t list; they won’t appear unless you have them'),'B':ready,'bPickA':unknown})
    key=join(g,'key',get(g,'CommunityToken'),prefix(g,'keyindex',':',number(g,'index','count.ReturnValue')))
    g.call('new','self:NewCatalogItem');g.wire((key,'new.Key'),(title,'new.Title'),(detail,'new.Detail'))
    g.wire((ready,'new.Preview'))
    description=call(g,'escapes',STR+'Replace',{'SourceString':item(g,'description',fields,11)},From='\\\\',To='\t',SearchCase='CaseSensitive')
    description=call(g,'breaks',STR+'Replace',{'SourceString':description},From='\\n',To='\n',SearchCase='CaseSensitive')
    description=call(g,'slashes',STR+'Replace',{'SourceString':description},From='\t',To='\\',SearchCase='CaseSensitive')
    values={'Rows':'new.Item','Codes':code,'Descriptions':description,'Requirements':ready,'Creators':creator,'Revisions':call(g,'revision',STR+'Conv_StringToInt',{'InString':revision}),
            'Parts':parts,'Footprints':item(g,'footprint',fields,10),'Dates':call(g,'date',STR+'Left',{'SourceString':item(g,'datevalue',fields,9)},Count=10),'Ready':'readyflag.ReturnValue','PackURLs':'emptyurl.ReturnValue'}
    call(g,'readyflag',KML+':Not_PreBool',A='false');call(g,'emptyurl',STR+'Concat_StrStr',A='',B='')
    previous='new'
    for suffix,value in values.items():
        arr(g,'keep'+suffix,'Add',get(g,'CommunityBrowse'+suffix));g.wire((value,'keep'+suffix+'.NewItem'));g.chain(previous,'keep'+suffix);previous='keep'+suffix
    # pack rows
    branch(g,'pack',combine(g,'packcheck',[eq(g,'packword',tag,'pack'),length(g,'packcount',fields,7)]))
    arr(g,'last','Length',get(g,'CommunityBrowseCodes'));index=op(g,'lastindex','Subtract_IntInt','last.ReturnValue',B=1)
    arr(g,'lastcode','Get',get(g,'CommunityBrowseCodes'));g.wire((index,'lastcode.Index'))
    branch(g,'owner',combine(g,'ownercheck',[op(g,'haslast','GreaterEqual_IntInt',index,B=0),call(g,'samecode',STR+'EqualEqual_StrStr',{'A':'lastcode.Item','B':item(g,'packcode',fields,1)})]))
    branch(g,'catalog',validity(g,'catalogvalid',get(g,'CatalogProvider')))
    from runtime_catalog import CATALOG
    installed=prop(g,'installedids',CATALOG,'RegisteredPackIDs',get(g,'CatalogProvider'))
    arr(g,'installed','Contains',installed);g.wire((item(g,'packid',fields,2),'installed.ItemToFind'));branch(g,'have','installed.ReturnValue')
    packtitle=item(g,'packtitle',fields,3)
    arr(g,'oldready','Get',get(g,'CommunityBrowseRequirements'));g.wire((index,'oldready.Index'))
    arr(g,'setuses','Set',get(g,'CommunityBrowseRequirements'));g.wire((index,'setuses.Index'),(join(g,'uses',call(g,'readyprefix',STR+'Replace',{'SourceString':'oldready.Item'},From=' · base game only',To='',SearchCase='CaseSensitive'),prefix(g,'usesprefix',' · uses ',packtitle)),'setuses.Item'))
    arr(g,'wasready','Get',get(g,'CommunityBrowseReady'));g.wire((index,'wasready.Index'));branch(g,'firstmissing','wasready.Item')
    arr(g,'setneeds','Set',get(g,'CommunityBrowseRequirements'));g.wire((index,'setneeds.Index'),(call(g,'needs',STR+'Concat_StrStr',{'A':prefix(g,'needsprefix','Needs the ',packtitle)},B=' prop pack. Get it on Nexus, then import.'),'setneeds.Item'))
    arr(g,'setnotready','Set',get(g,'CommunityBrowseReady'));g.wire((index,'setnotready.Index'),(call(g,'notready',KML+':Not_PreBool',A='true'),'setnotready.Item'))
    arr(g,'seturl','Set',get(g,'CommunityBrowsePackURLs'));g.wire((index,'seturl.Index'),(item(g,'packurl',fields,6),'seturl.Item'))
    arr(g,'row','Get',get(g,'CommunityBrowseRows'));g.wire((index,'row.Index'))
    set_value(g,'preview',ITEM+':Preview',call(g,'needsshort',STR+'Concat_StrStr',{'A':prefix(g,'needsshortprefix','Needs ',packtitle)},B=' (prop pack)'));g.wire(('row.Item','preview.self'))
    g.chain('entry','card','room','library','new');g.chain('card.else','pack','owner','catalog','have','setuses');g.chain('have.else','firstmissing','setneeds','setnotready','seturl','preview');g.chain('catalog.else','firstmissing')
    return g.function('AddCommunityListing',inputs=[v('Line','string')])


def select():
    g=Graph();call(g,'split',STR+'Split',{'SourceString':'entry.Key'},InStr=':',SearchCase='CaseSensitive',SearchDir='FromStart');branch(g,'splitok','split.ReturnValue')
    index=call(g,'index',STR+'Conv_StringToInt',{'InString':'split.RightS'});arr(g,'count','Length',get(g,'CommunityBrowseRows'));branch(g,'bounds',combine(g,'boundscheck',[op(g,'min','GreaterEqual_IntInt',index,B=0),op(g,'max','Less_IntInt',index,'count.ReturnValue')]))
    arr(g,'row','Get',get(g,'CommunityBrowseRows'));g.wire((index,'row.Index'));branch(g,'current',call(g,'keymatch',STR+'EqualEqual_StrStr',{'A':'entry.Key','B':prop(g,'key',ITEM,'Key','row.Item')}))
    set_value(g,'selected','CommunityBrowseSelected',index);g.call('detail','self:RefreshCommunityDetail');g.chain('entry','splitok','bounds','current','selected','detail');return g.function('SelectCommunityListing',inputs=[v('Key','string')])


def detail():
    from runtime_editor_host import visibility
    g=Graph();arr(g,'count','Length',get(g,'CommunityBrowseRows'));index=get(g,'CommunityBrowseSelected');branch(g,'bounds',combine(g,'boundscheck',[op(g,'min','GreaterEqual_IntInt',index,B=0),op(g,'max','Less_IntInt',index,'count.ReturnValue')]))
    sources={}
    for suffix in ['Rows','Descriptions','Requirements','Revisions','Creators','Codes','Parts','Footprints','Dates','PackURLs']:
        arr(g,suffix,'Get',get(g,'CommunityBrowse'+suffix));g.wire((index,suffix+'.Index'));sources[suffix]=suffix+'.Item'
    byline=join(g,'byline',prefix(g,'byprefix','by ',sources['Creators']),join(g,'bylinerev',prefix(g,'revprefix',' · revision ',number(g,'revisionnum',sources['Revisions'])),prefix(g,'dateprefix',' · ',sources['Dates'])))
    footprint=call(g,'footprint',KML+':SelectString',{'A':sources['Footprints'],'bPickA':call(g,'hasfootprint',STR+'NotEqual_StrStr',{'A':sources['Footprints']},B='')},B='Not given')
    previous='bounds'
    for field,value in [('DetailTitle',prop(g,'title',ITEM,'Title',sources['Rows'])),('DetailByline',byline),('CommunityDetail',call(g,'description',KML+':SelectString',{'A':sources['Descriptions'],'bPickA':call(g,'hasdescription',STR+'NotEqual_StrStr',{'A':sources['Descriptions']},B='')},B='No description.')),
                        ('DetailReadyText',sources['Requirements']),('FactPartsValue',sources['Parts']),('FactFootprintValue',footprint),('FactCodeValue',sources['Codes'])]:
        text(g,'set'+field,'CommunityPanel',field,value=value);g.chain(previous,'set'+field);previous='set'+field
    visibility(g,'showready',widget(g,'readywidget','CommunityPanel','DetailReady'),'Visible')
    branch(g,'packlink',call(g,'haspack',STR+'NotEqual_StrStr',{'A':sources['PackURLs']},B=''))
    visibility(g,'showpack',widget(g,'packwidget','CommunityPanel','GetPack'),'Visible');visibility(g,'hidepack',widget(g,'packhidden','CommunityPanel','GetPack'),'Collapsed')
    g.chain(previous,'showready','packlink','showpack');g.chain('packlink.else','hidepack')
    # Nothing selected: an empty pane with a hint.
    text(g,'emptytitle','CommunityPanel','DetailTitle',constant='Select a build');text(g,'emptybyline','CommunityPanel','DetailByline',constant='')
    text(g,'emptydetail','CommunityPanel','CommunityDetail',constant='Pick a card to see what it is, who made it and what it needs.')
    visibility(g,'hideready',widget(g,'readyhidden','CommunityPanel','DetailReady'),'Collapsed')
    previous='hideready'
    for field in ['FactPartsValue','FactFootprintValue','FactCodeValue']:
        text(g,'clear'+field,'CommunityPanel',field,constant='');g.chain(previous,'clear'+field);previous='clear'+field
    g.chain('entry','bounds');g.chain('bounds.else','emptytitle','emptybyline','emptydetail','hideready')
    return g.function('RefreshCommunityDetail')


def preview_poll():
    g=Graph();branch(g,'active',active(g));branch(g,'idle',call(g,'notpending',KML+':Not_PreBool',{'A':get(g,'CommunityPending')}));arr(g,'count','Length',get(g,'CommunityBrowseRows'))
    branch(g,'more',op(g,'within','Less_IntInt',get(g,'CommunityPreviewCursor'),'count.ReturnValue'))
    index=get(g,'CommunityPreviewCursor');arr(g,'code','Get',get(g,'CommunityBrowseCodes'));g.wire((get(g,'CommunityPreviewIndex'),'code.Index'));arr(g,'revision','Get',get(g,'CommunityBrowseRevisions'));g.wire((get(g,'CommunityPreviewIndex'),'revision.Index'))
    set_value(g,'index','CommunityPreviewIndex',index);set_value(g,'next','CommunityPreviewCursor',op(g,'inc','Add_IntInt',index,B=1))
    key=join(g,'key','code.Item',prefix(g,'revisionkey','_',number(g,'revnum','revision.Item')));arr(g,'find','Find',get(g,'CommunityCachedKeys'));g.wire((key,'find.ItemToFind'));branch(g,'cached',op(g,'exists','GreaterEqual_IntInt','find.ReturnValue',B=0))
    arr(g,'doc','Get',get(g,'CommunityCachedDocuments'));g.wire(('find.ReturnValue','doc.Index'));g.call('use','self:FinishCommunityPreview');g.wire(('doc.Item','use.Document'))
    g.call('start','self:StartCommunityTransfer');g.wire((prefix(g,'command','PREVIEW/','code.Item'),'start.Input'),(number(g,'revisiontext','revision.Item'),'start.Payload'))
    g.call('previewimage','self:RefreshCommunityDetailPreview');g.call('ensuregallery','self:EnsureCommunityGallery');g.chain('entry','active','previewimage','idle','ensuregallery','more','index','next','cached','use');g.chain('cached.else','start');return g.function('PollCommunityPreviews')


def finish_preview():
    g=Graph();index=get(g,'CommunityPreviewIndex');arr(g,'count','Length',get(g,'CommunityBrowseRows'));branch(g,'bounds',combine(g,'boundscheck',[op(g,'min','GreaterEqual_IntInt',index,B=0),op(g,'max','Less_IntInt',index,'count.ReturnValue')]))
    arr(g,'row','Get',get(g,'CommunityBrowseRows'));g.wire((index,'row.Index'));arr(g,'code','Get',get(g,'CommunityBrowseCodes'));g.wire((index,'code.Index'));arr(g,'rev','Get',get(g,'CommunityBrowseRevisions'));g.wire((index,'rev.Index'))
    key=join(g,'key','code.Item',prefix(g,'revkey','_',number(g,'revnum','rev.Item')))
    set_value(g,'document',ITEM+':ThumbnailDocument','entry.Document');g.wire(('row.Item','document.self'))
    path=prefix(g,'path','/ZComDen/CompositionThumbs/Public_',call(g,'suffix',STR+'Concat_StrStr',{'A':key},B='.Composition'))
    set_value(g,'pathset',ITEM+':AssetPath',path);g.wire(('row.Item','pathset.self'))
    arr(g,'author','Get',get(g,'CommunityBrowseCreators'));g.wire((index,'author.Index'));arr(g,'parts','Length',prop(g,'entriesvalue',LAYOUT,'Entries','entry.Document'));set_value(g,'detail',ITEM+':Detail',join(g,'partcaption','author.Item',prefix(g,'partprefix',' · parts: ',number(g,'partsnum','parts.ReturnValue'))));g.wire(('row.Item','detail.self'))
    arr(g,'cachecount','Length',get(g,'CommunityCachedKeys'));branch(g,'room',op(g,'roomcheck','Less_IntInt','cachecount.ReturnValue',B=64));arr(g,'existing','Contains',get(g,'CommunityCachedKeys'));g.wire((key,'existing.ItemToFind'));branch(g,'exists','existing.ReturnValue')
    arr(g,'cachekey','Add',get(g,'CommunityCachedKeys'));g.wire((key,'cachekey.NewItem'));arr(g,'cachedoc','Add',get(g,'CommunityCachedDocuments'));g.wire(('entry.Document','cachedoc.NewItem'))
    g.set('pending','CommunityPending','false');g.set('release','CommunityDocument');g.call('mailbox','self:ReleaseCommunityMailbox');g.call('refresh','self:RefreshCommunityDetail');call(g,'regenerate','/Script/UMG.ListViewBase:RegenerateAllEntries',{'self':widget(g,'listrefresh','CommunityPanel','CommunityListings')});g.chain('refresh','regenerate')
    g.call('requirements','self:BuildCommunityRequirements');g.wire(('entry.Document','requirements.Document'));arr(g,'oldrequirements','Get',get(g,'CommunityBrowseRequirements'));g.wire((index,'oldrequirements.Index'));arr(g,'requirementsset','Set',get(g,'CommunityBrowseRequirements'));g.wire((index,'requirementsset.Index'),(join(g,'fullrequirements','oldrequirements.Item',prefix(g,'partrequirements','\n','requirements.Report')),'requirementsset.Item'))
    g.chain('entry','bounds','document','pathset','detail','requirements','requirementsset','room','exists','pending','release','mailbox','refresh');g.chain('exists.else','cachekey','cachedoc','pending');g.chain('room.else','pending');return g.function('FinishCommunityPreview',inputs=[v('Document','object:'+LAYOUT)])


def download():
    g=Graph();arr(g,'count','Length',get(g,'CommunityBrowseCodes'));index=get(g,'CommunityBrowseSelected');branch(g,'bounds',combine(g,'boundscheck',[op(g,'min','GreaterEqual_IntInt',index,B=0),op(g,'max','Less_IntInt',index,'count.ReturnValue')]))
    arr(g,'code','Get',get(g,'CommunityBrowseCodes'));g.wire((index,'code.Index'));arr(g,'rev','Get',get(g,'CommunityBrowseRevisions'));g.wire((index,'rev.Index'))
    g.call('start','self:StartCommunityTransfer');g.wire((prefix(g,'command','DOWNLOAD/','code.Item'),'start.Input'),(number(g,'revisiontext','rev.Item'),'start.Payload'))
    g.call('available','self:CanStartCommunityBrowse');branch(g,'allowed','available.Allowed');g.chain('entry','available','allowed','bounds','start');return g.function('DownloadCommunityListing')


def detail_image():
    from runtime_editor_host import visibility
    g=Graph();branch(g,'active',active(g));index=get(g,'CommunityBrowseSelected');arr(g,'count','Length',get(g,'CommunityBrowseRows'))
    branch(g,'bounds',combine(g,'boundscheck',[op(g,'min','GreaterEqual_IntInt',index,B=0),op(g,'max','Less_IntInt',index,'count.ReturnValue')]))
    arr(g,'row','Get',get(g,'CommunityBrowseRows'));g.wire((index,'row.Index'));texture=prop(g,'texture',ITEM,'Thumb','row.Item');branch(g,'valid',validity(g,'thumbvalid',texture))
    image=widget(g,'image','CommunityPanel','CommunityPreview');call(g,'brush','/Script/UMG.Image:SetBrushFromTexture',{'self':image,'Texture':texture},bMatchSize='false');visibility(g,'show',image,'Visible');visibility(g,'hide',image,'Hidden')
    g.chain('entry','active','bounds','valid','brush','show');g.chain('valid.else','hide');g.chain('bounds.else','hide');return g.function('RefreshCommunityDetailPreview')


def browse_available():
    g=Graph();available=combine(g,'available',[call(g,'idle',KML+':Not_PreBool',{'A':get(g,'CommunityPending')}),call(g,'catalog',STR+'StartsWith',{'SourceString':get(g,'CommunityRequest')},InPrefix='CATALOG/',SearchCase='CaseSensitive'),call(g,'preview',STR+'StartsWith',{'SourceString':get(g,'CommunityRequest')},InPrefix='PREVIEW/',SearchCase='CaseSensitive')],True)
    g.wire((available,'result.Allowed'));g.chain('entry','result');return g.function('CanStartCommunityBrowse',outputs=[v('Allowed','bool')])


def code_in_library(code_var='entry.Code'):
    """Whether a local composition came from this share: imports are named
    "<title> <code>" (CommitCommunityImport)."""
    g=Graph();g.get('i','local:Cursor');arr(g,'count','Length',get(g,'CommunitySourceNames'));branch(g,'more',op(g,'within','Less_IntInt','i.Cursor','count.ReturnValue'))
    arr(g,'name','Get',get(g,'CommunitySourceNames'));g.wire(('i.Cursor','name.Index'))
    branch(g,'match',call(g,'contains',STR+'Contains',{'SearchIn':'name.Item','Substring':prefix(g,'spaced',' ',code_var)},bUseCase='false'))
    set_value(g,'next','local:Cursor',op(g,'inc','Add_IntInt','i.Cursor',B=1));g.set('yes','local:Found','true');g.get('found','local:Found');g.wire(('found.Found','result.Found'))
    g.chain('entry','more','match','yes','result');g.chain('match.else','next','more');g.chain('more.else','result')
    return g.function('CommunityCodeInLibrary',inputs=[v('Code','string')],outputs=[v('Found','bool')],locals=[v('Cursor','int','0'),v('Found','bool','false')])


def show_listings():
    """Fills the card grid; with "Only what I can use" on, builds that need a
    missing prop pack stay off it."""
    g=Graph();call(g,'clear',LIST+':ClearListItems',{'self':widget(g,'list','CommunityPanel','CommunityListings')})
    g.get('i','local:Cursor');g.get('hidden','local:Hidden');arr(g,'count','Length',get(g,'CommunityBrowseRows'));branch(g,'more',op(g,'within','Less_IntInt','i.Cursor','count.ReturnValue'))
    arr(g,'ready','Get',get(g,'CommunityBrowseReady'));g.wire(('i.Cursor','ready.Index'))
    branch(g,'shown',combine(g,'show',[call(g,'nofilter',KML+':Not_PreBool',{'A':get(g,'CommunityBrowseUsable')}),'ready.Item'],True))
    arr(g,'row','Get',get(g,'CommunityBrowseRows'));g.wire(('i.Cursor','row.Index'))
    call(g,'add',LIST+':AddItem',{'self':widget(g,'listadd','CommunityPanel','CommunityListings'),'Item':'row.Item'})
    set_value(g,'skip','local:Hidden',op(g,'hide','Add_IntInt','hidden.Hidden',B=1))
    set_value(g,'next','local:Cursor',op(g,'inc','Add_IntInt','i.Cursor',B=1))
    page=join(g,'pagecaption',prefix(g,'pageprefix','Page ',number(g,'pagenum',op(g,'onebased','Add_IntInt',get(g,'CommunityBrowsePage'),B=1))),join(g,'totalcaption',prefix(g,'of',' of ',number(g,'pagesnum',get(g,'CommunityBrowsePages'))),prefix(g,'builds',' · builds: ',number(g,'totalnum',get(g,'CommunityBrowseTotal')))))
    page=call(g,'hiddencaption',KML+':SelectString',{'A':join(g,'withhidden',page,call(g,'hiddensuffix',STR+'Concat_StrStr',{'A':prefix(g,'hiddenprefix',' · hidden here: ',number(g,'hiddennum','hidden.Hidden'))},B='')),'B':page,'bPickA':op(g,'anyhidden','Greater_IntInt','hidden.Hidden',B=0)})
    label=call(g,'caption',KML+':SelectString',{'A':page,'bPickA':op(g,'nonempty','Greater_IntInt',get(g,'CommunityBrowseTotal'),B=0)},B='No shared builds match. Try a different search, or Refresh.')
    text(g,'status','CommunityPanel','GalleryStatus',value=label)
    scope=call(g,'scope',KML+':SelectString',{'bPickA':get(g,'CommunityBrowseUsable')},A='Showing builds you can use: base game and the prop packs you have installed.',B='Showing every shared composition. Previews render here from each build’s parts.')
    text(g,'scopetext','CommunityPanel','BrowseStatus',value=scope)
    g.chain('entry','clear','more','shown','add','next','more');g.chain('shown.else','skip','next');g.chain('more.else','status','scopetext')
    return g.function('ShowCommunityListings',locals=[v('Cursor','int','0'),v('Hidden','int','0')])


def sort(name):
    g=Graph();set_value(g,'sort','CommunityBrowseSort',call(g,'value',STR+'Concat_StrStr',A=name,B=''));g.set('page','CommunityBrowsePage','0');g.call('style','self:StyleHolonetBrowse')
    g.call('available','self:CanStartCommunityBrowse');branch(g,'allowed','available.Allowed');g.call('refresh','self:RefreshCommunityGallery')
    g.chain('entry','available','allowed','sort','page','style','refresh')
    return g.function('SortHolonet'+name.capitalize())


def usable():
    g=Graph();set_value(g,'flip','CommunityBrowseUsable',call(g,'not',KML+':Not_PreBool',{'A':get(g,'CommunityBrowseUsable')}));g.call('style','self:StyleHolonetBrowse');g.call('show','self:ShowCommunityListings')
    g.chain('entry','flip','style','show');return g.function('ToggleHolonetUsable')


def style_browse():
    from runtime_editor_host import style_toggle
    g=Graph();previous='entry'
    for button,on in [('SortNewest',eq(g,'newest',get(g,'CommunityBrowseSort'),'newest')),('SortImports',eq(g,'imports',get(g,'CommunityBrowseSort'),'imports')),('FilterUsable',get(g,'CommunityBrowseUsable'))]:
        style_toggle(g,'style'+button,'CommunityPanel',button,on);g.chain(previous,'style'+button);previous='style'+button
    return g.function('StyleHolonetBrowse')


def get_pack():
    """Opens the Nexus page (or Nexus search) the bridge checked for this pack."""
    g=Graph();arr(g,'count','Length',get(g,'CommunityBrowsePackURLs'));index=get(g,'CommunityBrowseSelected')
    branch(g,'bounds',combine(g,'boundscheck',[op(g,'min','GreaterEqual_IntInt',index,B=0),op(g,'max','Less_IntInt',index,'count.ReturnValue')]))
    arr(g,'url','Get',get(g,'CommunityBrowsePackURLs'));g.wire((index,'url.Index'))
    branch(g,'nexus',call(g,'isnexus',STR+'StartsWith',{'SourceString':'url.Item'},InPrefix='https://www.nexusmods.com/',SearchCase='CaseSensitive'))
    call(g,'open','/Script/Engine.KismetSystemLibrary:LaunchURL',{'URL':'url.Item'})
    g.chain('entry','bounds','nexus','open');return g.function('OpenHolonetPack')


def add_to_library():
    g=Graph();g.set('flag','CommunityPlaceAfterImport','false');g.call('download','self:DownloadCommunityListing');g.chain('entry','flag','download')
    return g.function('AddCommunityListingToLibrary')


def place():
    """Add and place now: import the selected build, then start placing it."""
    g=Graph();g.set('flag','CommunityPlaceAfterImport','true');g.call('download','self:DownloadCommunityListing');g.chain('entry','flag','download')
    return g.function('PlaceCommunityListing')


def variables():
    return [v('CommunityBrowseSort','string','newest'),v('CommunityBrowseUsable','bool','false'),v('CommunityPlaceAfterImport','bool','false'),v('CommunityBrowseParts','string[]'),v('CommunityBrowseFootprints','string[]'),v('CommunityBrowseDates','string[]'),v('CommunityBrowseReady','bool[]'),v('CommunityBrowsePackURLs','string[]'),v('CommunityBrowsePage','int'),v('CommunityBrowsePages','int'),v('CommunityBrowseTotal','int'),v('CommunityBrowseSelected','int','-1'),v('CommunityPreviewCursor','int'),v('CommunityPreviewIndex','int'),v('CommunityBrowseLoaded','bool'),v('CommunityBrowseSearch','string'),v('CommunityBrowseRows','object:'+ITEM+'[]')]+[v('CommunityBrowse'+name,'string[]') for name in ['Codes','Descriptions','Requirements','Creators']]+[v('CommunityBrowseRevisions','int[]'),v('CommunityBrowseDocuments','object:'+LAYOUT+'[]'),v('CommunityBrowseStates','int[]'),v('CommunityCachedKeys','string[]'),v('CommunityCachedDocuments','object:'+LAYOUT+'[]')]
def functions():return [refresh(),ensure(),search(),page(True),page(False),gallery(),add_listing(),select(),detail(),preview_poll(),finish_preview(),download(),detail_image(),browse_available(),
                         code_in_library(),show_listings(),sort('newest'),sort('imports'),usable(),style_browse(),get_pack(),place(),add_to_library()]
