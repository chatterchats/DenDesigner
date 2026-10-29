"""Optional transport boundary. Core runtime knows only bounded value messages.

No networking, file IO or downloaded Blueprint/class loading lives here. An
optional adapter observes Request/Token and delivers values through these methods.
"""
from graph import Graph, variable as v, GS, KML
from runtime import LAYOUT, ENTRY, arr, unpack
from runtime_store import call, branch, combine, STR
from runtime_world import validity, set_value, finish_bool
from runtime_apply import get, clock
from runtime_session import prop, method
from runtime_gizmo_controller import op
from runtime_community_mailbox import HOLONET

PUBLISHED='Published: https://'+HOLONET+'/comp/'
from runtime_transform import copy_entry
from runtime_layout_ui import PRESETS


def current(g):
    return combine(g,'currentcheck',[get(g,'UIOpen'),get(g,'CommunityPending'),
        call(g,'sametoken',STR+'EqualEqual_StrStr',{'A':'entry.Token','B':get(g,'CommunityToken')})])


def cancel():
    g=Graph();g.call('mailbox','self:ReleaseCommunityMailbox');g.set('outgoing','CommunityOutgoing','');g.set('pending','CommunityPending','false');g.set('token','CommunityToken','');g.set('release','CommunityDocument')
    g.set('message','CommunityMessage','HoloNet request cancelled.');g.call('refresh','self:RefreshCommunityFeedback')
    g.call('clearkey','self:ClearCommunityKey');g.chain('entry','clearkey','mailbox','outgoing','pending','token','release','message','refresh');return g.function('CancelCommunityFetch')


def normalize():
    g=Graph();clean=call(g,'clean',STR+'TrimTrailing',{'SourceString':call(g,'trim',STR+'Trim',{'SourceString':'entry.Input'})})
    secret=call(g,'secret',STR+'Contains',{'SearchIn':clean},Substring='zcu_',bUseCase='false');branch(g,'notsecret',call(g,'notsecretcheck',KML+':Not_PreBool',{'A':secret}))
    count=call(g,'length',STR+'Len',{'S':clean});branch(g,'size',combine(g,'sizecheck',[op(g,'min','Greater_IntInt',count,B=0),op(g,'max','LessEqual_IntInt',count,B=256)]))
    g.get('i','local:Cursor');branch(g,'more',op(g,'within','Less_IntInt','i.Cursor',count))
    char=call(g,'character',STR+'GetSubstring',{'SourceString':clean,'StartIndex':'i.Cursor'},Length=1)
    branch(g,'allowed',call(g,'ascii',STR+'Contains',{'Substring':char},SearchIn='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-/.:',bUseCase='true'))
    set_value(g,'next','local:Cursor',op(g,'advance','Add_IntInt','i.Cursor',B=1));g.set('yes','local:OK','true');finish_bool(g,'Valid');g.wire((clean,'result.CleanInput'))
    g.chain('entry','notsecret');g.chain('notsecret.else','result');g.chain('notsecret','size','more','allowed','next','more');g.chain('more.else','yes','result');g.chain('size.else','result');g.chain('allowed.else','result')
    return g.function('NormalizeCommunityInput',inputs=[v('Input','string')],outputs=[v('CleanInput','string'),v('Valid','bool')],locals=[v('Cursor','int','0'),v('OK','bool','false')])


def start(payload=False):
    g=Graph();g.call('cancel','self:CancelCommunityFetch');g.call('ready','self:CanEdit')
    branch(g,'available',combine(g,'availablecheck',[get(g,'UIOpen'),'ready.Ready']))
    g.call('normalize','self:NormalizeCommunityInput');g.wire(('entry.Input','normalize.Input'));branch(g,'bounded','normalize.Valid')
    guid=call(g,'guid','/Script/Engine.KismetGuidLibrary:NewGuid');token=call(g,'guidtext','/Script/Engine.KismetGuidLibrary:Conv_GuidToString',{'InGuid':guid})
    token=call(g,'compact',STR+'Replace',{'SourceString':token},From='-',To='',SearchCase='CaseSensitive')
    token=call(g,'lower',STR+'ToLower',{'SourceString':token})
    set_value(g,'outgoing','CommunityOutgoing','entry.Payload' if payload else get(g,'CommunityOutgoing'));set_value(g,'token','CommunityToken',token);set_value(g,'input','CommunityRequest','normalize.CleanInput');set_value(g,'at','CommunityStarted',clock(g,'now'))
    g.set('pending','CommunityPending','true');g.call('write','self:WriteCommunityRequest');g.set('message','CommunityMessage','Contacting HoloNet… (needs the Den Designer HoloNet bridge installed)');g.call('refresh','self:RefreshCommunityFeedback')
    g.set('releaseoutgoing','CommunityOutgoing','');g.set('invalid','CommunityMessage','Enter a share code or a zcom.app composition link.')
    g.chain('entry','cancel','ready','available','normalize','bounded','outgoing','token','input','at','pending','message','write','releaseoutgoing','refresh');g.chain('bounded.else','invalid','refresh')
    return g.function('StartCommunityTransfer' if payload else 'StartCommunityFetch',inputs=[v('Input','string')]+([v('Payload','string')] if payload else []))


def poll():
    g=Graph();g.call('mailbox','self:PollCommunityMailbox');branch(g,'pending',get(g,'CommunityPending'))
    limit=call(g,'deadline',KML+':SelectFloat',{'bPickA':call(g,'publishing',STR+'EqualEqual_StrStr',{'A':get(g,'CommunityRequest')},B='PUBLISH')},A=600,B=65)
    branch(g,'expired',combine(g,'expiredcheck',[op(g,'timeout','Greater_DoubleDouble',op(g,'elapsed','Subtract_DoubleDouble',clock(g,'now'),get(g,'CommunityStarted')),limit),call(g,'closed',KML+':Not_PreBool',{'A':get(g,'UIOpen')})],True))
    g.call('cancel','self:CancelCommunityFetch');g.set('message','CommunityMessage','HoloNet didn’t answer in time, or the editor closed. Check your connection and that the bridge is installed, then try again.');g.call('refresh','self:RefreshCommunityFeedback')
    g.chain('entry','pending','expired','cancel','message','refresh');g.chain('expired.else','mailbox');return g.function('PollCommunityFetch')


def fail():
    g=Graph();branch(g,'current',current(g));g.call('cancel','self:CancelCommunityFetch')
    message=call(g,'bounded',STR+'Left',{'SourceString':'entry.Message'},Count=2048)
    set_value(g,'message','CommunityMessage',message);g.call('refresh','self:RefreshCommunityFeedback')
    branch(g,'remembered',call(g,'rememberedcheck',STR+'Contains',{'SearchIn':'entry.Message'},Substring='Remembered connection.',bUseCase='true'));g.set('remember','CommunityRemember','true')
    branch(g,'account',combine(g,'accountchecks',[call(g,'isconnect',STR+'EqualEqual_StrStr',{'A':get(g,'CommunityRequest')},B='CONNECT'),call(g,'isauth',STR+'EqualEqual_StrStr',{'A':get(g,'CommunityRequest')},B='AUTH'),call(g,'isdisconnect',STR+'EqualEqual_StrStr',{'A':get(g,'CommunityRequest')},B='DISCONNECT'),call(g,'isforget',STR+'EqualEqual_StrStr',{'A':get(g,'CommunityRequest')},B='FORGET'),call(g,'disconnectedreply',STR+'StartsWith',{'SourceString':'entry.Message'},InPrefix='Not connected',SearchCase='CaseSensitive'),call(g,'revokedreply',STR+'StartsWith',{'SourceString':'entry.Message'},InPrefix='Key invalid',SearchCase='CaseSensitive')],True))
    from runtime_editor_host import text
    set_value(g,'profile','CommunityProfile',message);text(g,'profilelabel','CommunityPanel','CommunityProfile',value=message)
    branch(g,'published',call(g,'publishedcheck',STR+'StartsWith',{'SourceString':'entry.Message'},InPrefix=PUBLISHED,SearchCase='CaseSensitive'))
    url=call(g,'url',STR+'RightChop',{'SourceString':'entry.Message'},Count=11)
    code=call(g,'code',STR+'RightChop',{'SourceString':url},Count=len(PUBLISHED)-len('Published: '))
    set_value(g,'publicurl','CommunityPublicURL',url);set_value(g,'publiccode','CommunityPublicCode',code);text(g,'publicationlabel','CommunityPanel','PublishResult',value=call(g,'shortlink',STR+'RightChop',{'SourceString':url},Count=8))
    # Share a build shows the result; an update is now one revision newer.
    text(g,'sharecode','CommunityPanel','ShareResultCode',value=code)
    from runtime_community_ui import has_target
    updated=combine(g,'updated',[get(g,'HolonetShareUpdate'),has_target(g)])
    text(g,'sharetitle','CommunityPanel','ShareResultTitle',value=call(g,'sharetitletext',KML+':SelectString',{'bPickA':updated},A='Shared · the update is live',B='Shared · your build is live'))
    branch(g,'bump',updated);arr(g,'oldrev','Get',get(g,'HolonetShareRevisions'));g.wire((get(g,'HolonetShareTarget'),'oldrev.Index'))
    arr(g,'newrev','Set',get(g,'HolonetShareRevisions'));g.wire((get(g,'HolonetShareTarget'),'newrev.Index'),(op(g,'plusone','Add_IntInt','oldrev.Item',B=1),'newrev.Item'))
    g.set('showresult','HolonetShowResult','true');g.set('staleshares','HolonetSharesStale','true');g.call('sharepanel','self:RefreshHolonetShare')
    branch(g,'sharesfailed',call(g,'sharesrequest',STR+'StartsWith',{'SourceString':get(g,'CommunityRequest')},InPrefix='MYSHARES/',SearchCase='CaseSensitive'));text(g,'shareserror','CommunityPanel','SharesStatus',value=message)
    g.set('newaccount','HolonetSharesStale','true')
    branch(g,'galleryfailed',call(g,'galleryrequest',STR+'StartsWith',{'SourceString':get(g,'CommunityRequest')},InPrefix='CATALOG/',SearchCase='CaseSensitive'));text(g,'galleryerror','CommunityPanel','GalleryStatus',value=message);g.chain('refresh','galleryfailed','galleryerror');g.chain('galleryfailed.else','sharesfailed','shareserror')
    g.chain('entry','current','account','profile','profilelabel','newaccount','published');g.chain('account.else','published');g.chain('published','publicurl','publiccode','publicationlabel','sharecode','sharetitle','bump','newrev','showresult','staleshares','sharepanel','remembered');g.chain('bump.else','showresult');g.chain('published.else','remembered')
    g.chain('remembered','remember','cancel','message','refresh');g.chain('remembered.else','cancel');return g.function('FailCommunityFetch',inputs=[v('Token','string'),v('Message','string')])



def begin():
    g=Graph();branch(g,'current',current(g));branch(g,'bounded',combine(g,'countcheck',[op(g,'min','Greater_IntInt','entry.Count',B=0),op(g,'max','LessEqual_IntInt','entry.Count',B=128)]))
    call(g,'create',GS+':CreateSaveGameObject',SaveGameClass=LAYOUT);g.node('cast','cast',**{'class':LAYOUT});g.wire(('create.ReturnValue','cast.Object'))
    set_value(g,'document','CommunityDocument','cast.AsBP Den Layout Save');set_value(g,'count','CommunityExpected','entry.Count')
    method(g,'normalize',PRESETS,'NormalizeName',get(g,'CompositionService'),{'Name':'entry.Name'})
    # Ensure service before NormalizeName; names never become paths or save slots.
    g.call('ensure','self:EnsureCompositionService');branch(g,'namevalid','normalize.Valid');set_value(g,'name','CommunityName','normalize.CleanName')
    set_value(g,'report','CommunityReport',call(g,'boundedreport',STR+'Left',{'SourceString':'entry.Report'},Count=2048))
    g.set('anchorflag',LAYOUT+':HasCompositionAnchor','true');g.wire((get(g,'CommunityDocument'),'anchorflag.self'))
    set_value(g,'anchor',LAYOUT+':CompositionAnchor','entry.Anchor');g.wire((get(g,'CommunityDocument'),'anchor.self'))
    g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','current','bounded','create','cast','document','count','ensure','normalize','namevalid','name','report','anchorflag','anchor','yes','result')
    for pin in ['current.else','bounded.else','cast.CastFailed','namevalid.else']:g.chain(pin,'result')
    return g.function('BeginCommunityImport',inputs=[v('Token','string'),v('Name','string'),v('Count','int'),v('Anchor','vector'),v('Report','string')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def append():
    g=Graph();branch(g,'current',current(g));branch(g,'document',validity(g,'doc',get(g,'CommunityDocument')))
    rows=prop(g,'rows',LAYOUT,'Entries',get(g,'CommunityDocument'));arr(g,'count','Length',rows)
    branch(g,'room',op(g,'bounded','Less_IntInt','count.ReturnValue',get(g,'CommunityExpected')))
    g.node('part','make_struct',struct=ENTRY,defaults={'Kind':'0','HasPosition':'true','HasRotation':'true','HasScale':'true'})
    for key in ['Mesh','Position','Rotation','Scale','CollisionMode']:g.wire(('entry.'+key,'part.'+key))
    key=call(g,'key',STR+'Conv_IntToString',{'InInt':'count.ReturnValue'});g.wire((key,'part.Key'))
    g.call('validate','self:ValidCompositionTransform');g.wire(('part.ST_DenEntry','validate.Value'));g.call('path','self:ValidAssetPath');g.wire(('entry.Mesh','path.Path'))
    branch(g,'valid',combine(g,'validcheck',['validate.Valid','path.Valid',op(g,'collisionmin','GreaterEqual_IntInt','entry.CollisionMode',B=0),op(g,'collisionmax','LessEqual_IntInt','entry.CollisionMode',B=2)]))
    arr(g,'add','Add',rows);g.wire(('part.ST_DenEntry','add.NewItem'));g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','current','document','room','validate','path','valid','add','yes','result')
    for pin in ['current.else','document.else','room.else','valid.else']:g.chain(pin,'result')
    return g.function('AppendCommunityPart',inputs=[v('Token','string'),v('Mesh','string'),v('Position','vector'),v('Rotation','rotator'),v('Scale','vector'),v('CollisionMode','int')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def material():
    g=Graph();branch(g,'current',current(g));branch(g,'document',validity(g,'doc',get(g,'CommunityDocument')))
    rows=prop(g,'rows',LAYOUT,'Entries',get(g,'CommunityDocument'));arr(g,'count','Length',rows);branch(g,'part',op(g,'haspart','Greater_IntInt','count.ReturnValue',B=0))
    index=op(g,'index','Subtract_IntInt','count.ReturnValue',B=1);arr(g,'last','Get',rows);g.wire((index,'last.Index'));unpack(g,'partdata',ENTRY,'last.Item')
    arr(g,'countm','Length','partdata.Materials');branch(g,'room',op(g,'bounded','Less_IntInt','countm.ReturnValue',B=64))
    g.call('path','self:ValidAssetPath');g.wire(('entry.Path','path.Path'));branch(g,'valid',combine(g,'validcheck',['path.Valid',call(g,'empty',STR+'EqualEqual_StrStr',{'A':'entry.Path'},B='')],True))
    set_value(g,'copy','local:Materials','partdata.Materials');g.get('m','local:Materials');arr(g,'add','Add','m.Materials');g.wire(('entry.Path','add.NewItem'))
    value=copy_entry(g,'updated','last.Item',{'Materials':'m.Materials'});arr(g,'replace','Set',rows);g.wire((index,'replace.Index'),(value,'replace.Item'))
    g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','current','document','part','room','path','valid','copy','add','replace','yes','result')
    for pin in ['current.else','document.else','part.else','room.else','valid.else']:g.chain(pin,'result')
    return g.function('AppendCommunityMaterial',inputs=[v('Token','string'),v('Path','string')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false'),v('Materials','string[]')])


def commit():
    g=Graph();branch(g,'current',current(g));g.call('ready','self:CanEdit');branch(g,'readycheck','ready.Ready')
    g.call('validate','self:ValidateComposition');g.wire((get(g,'CommunityDocument'),'validate.Document'));branch(g,'valid','validate.Accepted')
    arr(g,'count','Length',prop(g,'rows',LAYOUT,'Entries',get(g,'CommunityDocument')));branch(g,'complete',op(g,'all','EqualEqual_IntInt','count.ReturnValue',get(g,'CommunityExpected')))
    g.call('refresh','self:RefreshCompositionLibrary');g.call('fresh','self:CompositionLibraryCurrent');branch(g,'freshcheck','fresh.Accepted')
    arr(g,'exists','Contains',get(g,'CompositionNames'));g.wire((get(g,'CommunityName'),'exists.ItemToFind'));branch(g,'duplicate','exists.ReturnValue')
    method(g,'save',PRESETS,'SavePreset',get(g,'CompositionService'),{'Name':get(g,'CommunityName'),'Document':get(g,'CommunityDocument')});branch(g,'saved',op(g,'success','EqualEqual_IntInt','save.Status',B=1))
    set_value(g,'selected','SelectedComposition','save.CleanName');g.set('pending','CommunityPending','false');g.set('token','CommunityToken','');g.set('release','CommunityDocument')
    set_value(g,'message','CommunityMessage',call(g,'caption',STR+'Concat_StrStr',{'B':get(g,'CommunityReport')},A='Added to your Compositions. ' ))
    g.call('cards','self:RefreshCompositionLibrary');g.set('yes','local:OK','true');finish_bool(g)
    # Add and place now: open Compositions and place the new card, as Place selected does.
    branch(g,'place',get(g,'CommunityPlaceAfterImport'));g.set('placed','CommunityPlaceAfterImport','false')
    g.call('compositions','self:SetEditorPanel',Name='compositions');g.call('placing','self:QueueCompositionAction',Name='load_composition',Argument='')
    branch(g,'preview',call(g,'previewmode',STR+'StartsWith',{'SourceString':get(g,'CommunityRequest')},InPrefix='PREVIEW/',SearchCase='CaseSensitive'));g.call('cachepreview','self:FinishCommunityPreview');g.wire((get(g,'CommunityDocument'),'cachepreview.Document'))
    g.chain('entry','current','ready','readycheck','validate','valid','complete','preview','cachepreview','yes','result');g.chain('preview.else','refresh','fresh','freshcheck','duplicate')
    g.chain('duplicate.else','save','saved','pending','token','release','message','cards','place','placed','compositions','placing','yes','result');g.chain('place.else','yes')
    for pin in ['current.else','readycheck.else','valid.else','complete.else','freshcheck.else','duplicate.then','saved.else']:g.chain(pin,'result')
    return g.function('CommitCommunityImport',inputs=[v('Token','string')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def variables():
    from runtime_community_ui import variables as ui_variables
    from runtime_community_sources import variables as source_variables
    from runtime_community_browser import variables as browser_variables
    return browser_variables()+source_variables()+ui_variables()+[v('CommunityRemember','bool','false'),v('CommunityOutgoing','string'),v('CommunityToken','string'),v('CommunityRequest','string'),v('CommunityStarted','double'),v('CommunityPending','bool'),v('CommunityDocument','object:'+LAYOUT),v('CommunityExpected','int'),v('CommunityName','string'),v('CommunityReport','string')]


def functions():
    from runtime_community_publish import serialize, thumbnail_name
    from runtime_community_connection import functions as connection_functions
    from runtime_community_ui import functions as ui_functions
    from runtime_community_sources import functions as source_functions
    from runtime_community_browser import functions as browser_functions
    return browser_functions()+source_functions()+ui_functions()+[cancel(),normalize(),start(),start(True),poll(),fail(),begin(),append(),material(),commit(),serialize(),thumbnail_name()]+connection_functions()
