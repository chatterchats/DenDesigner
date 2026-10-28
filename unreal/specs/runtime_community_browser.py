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
    for i,name in enumerate(['CommunityBrowseRows','CommunityBrowseCodes','CommunityBrowseDescriptions','CommunityBrowseRequirements','CommunityBrowseCreators','CommunityBrowseRevisions','CommunityBrowseDocuments','CommunityBrowseStates']):
        arr(g,'clear'+str(i),'Clear',get(g,name))
        g.chain('cancel' if not i else 'clear'+str(i-1),'clear'+str(i))
    call(g,'clearlist',LIST+':ClearListItems',{'self':widget(g,'list','CommunityPanel','CommunityListings')})
    command=prefix(g,'command','CATALOG/',number(g,'page',get(g,'CommunityBrowsePage')))
    payload=call(g,'query',KML+':SelectString',{'A':get(g,'CommunityBrowseSearch'),'bPickA':call(g,'hasquery',STR+'NotEqual_StrStr',{'A':get(g,'CommunityBrowseSearch')},B='')},B=' ')
    g.call('start','self:StartCommunityTransfer');g.wire((command,'start.Input'),(payload,'start.Payload'))
    g.set('loaded','CommunityBrowseLoaded','true');g.set('selected','CommunityBrowseSelected','-1')
    text(g,'loading','CommunityPanel','GalleryStatus',constant='Loading public compositions…');g.chain('entry','active','available','allowed','cancel');text(g,'cleardetail','CommunityPanel','CommunityDetail',constant='Select a public composition to inspect it, then Download to add it to the local library.');g.chain('clear7','clearlist','start','loaded','selected','loading','cleardetail')
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
    branch(g,'bounded',combine(g,'bounds',[op(g,'min','GreaterEqual_IntInt',pages,B=0),op(g,'max','LessEqual_IntInt',pages,B=8)]))
    set_value(g,'pagecount','CommunityBrowsePages',pages);set_value(g,'totalcount','CommunityBrowseTotal',total);g.set('reset','CommunityPreviewCursor','0');g.get('i','local:GalleryCursor');arr(g,'count','Length',lines)
    branch(g,'more',op(g,'within','Less_IntInt','i.GalleryCursor','count.ReturnValue'))
    arr(g,'lineget','Get',lines);g.wire(('i.GalleryCursor','lineget.Index'));branch(g,'end',eq(g,'endword','lineget.Item','end'))
    g.call('add','self:AddCommunityListing');g.wire(('lineget.Item','add.Line'));set_value(g,'next','local:GalleryCursor',op(g,'inc','Add_IntInt','i.GalleryCursor',B=1))
    g.set('pending','CommunityPending','false');g.call('release','self:ReleaseCommunityMailbox')
    status=join(g,'pagecaption',prefix(g,'pageprefix','Page ',number(g,'pagenum',op(g,'onebased','Add_IntInt',get(g,'CommunityBrowsePage'),B=1))),join(g,'totalcaption',prefix(g,'of',' of ',number(g,'pagesnum',get(g,'CommunityBrowsePages'))),prefix(g,'matches',' · public matches: ',number(g,'totalnum',get(g,'CommunityBrowseTotal')))))
    label=call(g,'caption',KML+':SelectString',{'A':status,'bPickA':op(g,'nonempty','Greater_IntInt',get(g,'CommunityBrowseTotal'),B=0)},B='No public compositions match this search. Try a different search or Refresh.')
    text(g,'status','CommunityPanel','GalleryStatus',value=label)
    text(g,'scope','CommunityPanel','BrowseStatus',constant='Public service feed · latest available listings. Cards render locally as their validated parts arrive.')
    g.chain('entry','headerok','bounded','pagecount','totalcount','reset','more','end','pending','release','status','scope');g.chain('end.else','add','next','more')
    return g.function('ReadCommunityGallery',locals=[v('GalleryCursor','int','2')])


def add_listing():
    g=Graph();fields=split(g,'fields','entry.Line','\t');branch(g,'bounded',length(g,'fieldcount',fields,8));arr(g,'count','Length',get(g,'CommunityBrowseRows'));branch(g,'room',op(g,'roomcheck','Less_IntInt','count.ReturnValue',B=6))
    code=item(g,'code',fields,1);title=item(g,'title',fields,2);creator=item(g,'creator',fields,4);count=item(g,'parts',fields,5);revision=item(g,'rev',fields,6)
    detail=join(g,'detail',creator,prefix(g,'countcaption',' · parts: ',count));preview=item(g,'requirements',fields,7)
    key=join(g,'key',get(g,'CommunityToken'),prefix(g,'keyindex',':',number(g,'index','count.ReturnValue')))
    g.call('new','self:NewCatalogItem');g.wire((key,'new.Key'),(title,'new.Title'),(detail,'new.Detail'),(preview,'new.Preview'))
    values={'Rows':'new.Item','Codes':code,'Descriptions':item(g,'description',fields,3),'Requirements':preview,'Creators':creator,'Revisions':call(g,'revision',STR+'Conv_StringToInt',{'InString':revision})}
    previous='new'
    for suffix,value in values.items():
        arr(g,'keep'+suffix,'Add',get(g,'CommunityBrowse'+suffix));g.wire((value,'keep'+suffix+'.NewItem'));g.chain(previous,'keep'+suffix);previous='keep'+suffix
    
    call(g,'add',LIST+':AddItem',{'self':widget(g,'view','CommunityPanel','CommunityListings'),'Item':'new.Item'})
    g.chain('entry','bounded','room','new');g.chain(previous,'add');return g.function('AddCommunityListing',inputs=[v('Line','string')])


def select():
    g=Graph();call(g,'split',STR+'Split',{'SourceString':'entry.Key'},InStr=':',SearchCase='CaseSensitive',SearchDir='FromStart');branch(g,'splitok','split.ReturnValue')
    index=call(g,'index',STR+'Conv_StringToInt',{'InString':'split.RightS'});arr(g,'count','Length',get(g,'CommunityBrowseRows'));branch(g,'bounds',combine(g,'boundscheck',[op(g,'min','GreaterEqual_IntInt',index,B=0),op(g,'max','Less_IntInt',index,'count.ReturnValue')]))
    arr(g,'row','Get',get(g,'CommunityBrowseRows'));g.wire((index,'row.Index'));branch(g,'current',call(g,'keymatch',STR+'EqualEqual_StrStr',{'A':'entry.Key','B':prop(g,'key',ITEM,'Key','row.Item')}))
    set_value(g,'selected','CommunityBrowseSelected',index);g.call('detail','self:RefreshCommunityDetail');g.chain('entry','splitok','bounds','current','selected','detail');return g.function('SelectCommunityListing',inputs=[v('Key','string')])


def detail():
    g=Graph();arr(g,'count','Length',get(g,'CommunityBrowseRows'));index=get(g,'CommunityBrowseSelected');branch(g,'bounds',combine(g,'boundscheck',[op(g,'min','GreaterEqual_IntInt',index,B=0),op(g,'max','Less_IntInt',index,'count.ReturnValue')]))
    sources={}
    for suffix in ['Rows','Descriptions','Requirements','Revisions','Creators']:
        arr(g,suffix,'Get',get(g,'CommunityBrowse'+suffix));g.wire((index,suffix+'.Index'));sources[suffix]=suffix+'.Item'
    caption=join(g,'caption',prop(g,'title',ITEM,'Title','Rows.Item'),prefix(g,'creatorcaption',' · ','Creators.Item'))
    caption=join(g,'description',caption,prefix(g,'descriptionprefix','\n','Descriptions.Item'))
    caption=join(g,'revision',caption,prefix(g,'revisionprefix','\nRevision: ',number(g,'revisionnum','Revisions.Item')))
    caption=join(g,'requirementcaption',caption,prefix(g,'requirementprefix','\n','Requirements.Item'))
    text(g,'detail','CommunityPanel','CommunityDetail',value=caption)
    g.chain('entry','bounds','detail');return g.function('RefreshCommunityDetail')


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


def variables():
    return [v('CommunityBrowsePage','int'),v('CommunityBrowsePages','int'),v('CommunityBrowseTotal','int'),v('CommunityBrowseSelected','int','-1'),v('CommunityPreviewCursor','int'),v('CommunityPreviewIndex','int'),v('CommunityBrowseLoaded','bool'),v('CommunityBrowseSearch','string'),v('CommunityBrowseRows','object:'+ITEM+'[]')]+[v('CommunityBrowse'+name,'string[]') for name in ['Codes','Descriptions','Requirements','Creators']]+[v('CommunityBrowseRevisions','int[]'),v('CommunityBrowseDocuments','object:'+LAYOUT+'[]'),v('CommunityBrowseStates','int[]'),v('CommunityCachedKeys','string[]'),v('CommunityCachedDocuments','object:'+LAYOUT+'[]')]
def functions():return [refresh(),ensure(),search(),page(True),page(False),gallery(),add_listing(),select(),detail(),preview_poll(),finish_preview(),download(),detail_image(),browse_available()]
