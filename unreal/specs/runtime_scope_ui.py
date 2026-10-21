"""Campaign/Home transitions while retaining the native editor's camera and UI."""
from graph import Graph, variable as v, KML
from runtime import LAYOUT
from runtime_store import call, branch, combine, STR
from runtime_world import set_value, validity, finish_bool
from runtime_apply import get
from runtime_session import STORE, HISTORY, prop, method
from runtime_editor_host import text, widget, WIDGET
from runtime_layout_ui import ready
from runtime_gizmo_controller import op


def context():
    g=Graph();method(g,'key',STORE,'CampaignKey',get(g,'Storage'),{'CampaignID':get(g,'ActiveCampaignID')})
    home=call(g,'home',STR+'EqualEqual_StrStr',{'A':get(g,'SessionKey'),'B':get(g,'HomeStorageKey')});own=call(g,'own',STR+'EqualEqual_StrStr',{'A':get(g,'SessionKey'),'B':'key.Key'})
    g.wire(('key.Key','result.CampaignKey'),(own,'result.Own'),(combine(g,'allowed',['key.Valid',combine(g,'scopevalid',[home,own],True)]),'result.Known'));g.chain('entry','key','result');return g.function('EditorScopeContext',outputs=[v('CampaignKey','string'),v('Own','bool'),v('Known','bool')])


def refresh():
    g=Graph();branch(g,'panel',validity(g,'panelvalid',get(g,'LayoutsPanel')));g.call('context','self:EditorScopeContext');g.call('ready','self:CanEdit');branch(g,'own','context.Own')
    text(g,'owntext','LayoutsPanel','ScopeText',constant='Editing this campaign’s own layout. Changes here do not alter Home.');text(g,'ownbutton','LayoutsPanel','ScopeButtonLabel',constant='Return to Home')
    text(g,'home','LayoutsPanel','ScopeText',constant='Editing Home, shared by campaigns without their own layout.');text(g,'homebutton','LayoutsPanel','ScopeButtonLabel',constant='Create campaign layout')
    text(g,'hint','LayoutsPanel','ScopeHint',constant='Create a copy of the Den as it is now. Returning to Home keeps the campaign copy in backup history.')
    call(g,'enable',WIDGET+':SetIsEnabled',{'self':widget(g,'button','LayoutsPanel','ScopeButton'),'bInIsEnabled':combine(g,'enabled',['context.Known','ready.Ready'])})
    branch(g,'known','context.Known');text(g,'unknown','LayoutsPanel','ScopeText',constant='Campaign identity is unavailable. You can still edit this layout and use presets.')
    g.chain('entry','panel','context','ready','own','owntext','ownbutton','hint','enable','known');g.chain('own.else','home','homebutton','hint');g.chain('known.else','unknown')
    return g.function('RefreshLayoutScope')


def adopt():
    g=Graph();g.call('ready','self:CanEdit');branch(g,'allowed','ready.Ready');set_value(g,'old','local:PreviousKey',get(g,'SessionKey'));g.get('oldkey','local:PreviousKey');g.call('clear','self:ClearSelection');g.call('cancel','self:CancelPlacement');g.call('queue','self:ClearEditorMutations');g.set('close','Editing','false');g.call('open','self:OpenSession');g.wire(('entry.Key','open.Key'),('entry.Document','open.Document'),('entry.Status','open.LoadStatus'));branch(g,'opened','open.Accepted')
    method(g,'clearold',STORE,'ClearDraft',get(g,'Storage'),{'Key':'oldkey.PreviousKey'});branch(g,'cleared','clearold.Cleared');g.set('warning','LayoutMessage','Layout switched, but the previous draft could not be removed. It remains available for recovery.')
    g.call('offer','self:OfferRecovery');g.call('storeroom','self:StoreroomPanelChanged');g.call('scope','self:RefreshLayoutScope');g.call('labels','self:RefreshLayoutFeedback');g.set('yes','local:OK','true');finish_bool(g)
    g.set('restore','Editing','true');g.set('failure','LayoutMessage','The new layout could not be opened. Your previous editing session is still available.')
    g.chain('entry','ready','allowed','old','clear','cancel','queue','close','open','opened','clearold','cleared','offer','storeroom','scope','labels','yes','result');g.chain('cleared.else','warning','offer');g.chain('opened.else','restore','failure','result');g.chain('allowed.else','result')
    return g.function('AdoptEditorLayout',inputs=[v('Key','string'),v('Document','object:'+LAYOUT),v('Status','int')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false'),v('PreviousKey','string')])


def create_campaign():
    g=Graph();ready(g);g.call('context','self:EditorScopeContext');branch(g,'known',combine(g,'valid',['context.Known',call(g,'nothome',KML+':Not_PreBool',{'A':'context.Own'})]));g.call('current','self:BaselineCurrent');branch(g,'unchanged','current.Accepted')
    method(g,'save',STORE,'MakeCampaign',get(g,'Storage'),{'CampaignID':get(g,'ActiveCampaignID'),'Document':get(g,'WorkingDocument')});branch(g,'saved',op(g,'success','EqualEqual_IntInt','save.Status',B=1));g.set('message','LayoutMessage','This campaign now has its own copy of the current Den. Home is unchanged.');g.call('adopt','self:AdoptEditorLayout',Status=1);g.wire(('context.CampaignKey','adopt.Key'),('save.SavedDocument','adopt.Document'))
    g.set('conflict','LayoutMessage','The saved layout changed outside this session. Save or reopen it before switching scope.');g.set('error','LayoutMessage','The campaign copy could not be saved. Your current layout is unchanged.');g.call('labels','self:RefreshLayoutFeedback')
    method(g,'destination',STORE,'LoadLayout',get(g,'Storage'),{'Key':'context.CampaignKey'},Draft='false',BeforeRevision=0);branch(g,'absent',op(g,'missing','EqualEqual_IntInt','destination.Status',B=0));branch(g,'destinationreadable',op(g,'readable','LessEqual_IntInt','destination.Status',B=2));branch(g,'inactive',call(g,'disabled',KML+':Not_PreBool',{'A':prop(g,'destinationenabled',LAYOUT,'Enabled','destination.Document')}));g.set('destinationerror','LayoutMessage','A campaign layout already exists or could not be read. Reopen the editor before replacing it.')
    g.chain('allowed','context','known','current','unchanged','destination','absent','save','saved','message','adopt');g.chain('absent.else','destinationreadable','inactive','save');g.chain('destinationreadable.else','destinationerror','labels');g.chain('inactive.else','destinationerror');g.chain('unchanged.else','conflict','labels');g.chain('saved.else','error','labels')
    return g.function('CreateEditorCampaignLayout')


def use_home():
    g=Graph();ready(g);g.call('context','self:EditorScopeContext');branch(g,'known',combine(g,'valid',['context.Known','context.Own']));g.call('current','self:BaselineCurrent');branch(g,'unchanged','current.Accepted')
    method(g,'home',STORE,'LoadLayout',get(g,'Storage'),{'Key':get(g,'HomeStorageKey')},Draft='false',BeforeRevision=0);branch(g,'readable',op(g,'healthy','LessEqual_IntInt','home.Status',B=2))
    method(g,'disable',STORE,'UseHome',get(g,'Storage'),{'CampaignID':get(g,'ActiveCampaignID')});branch(g,'saved',op(g,'success','EqualEqual_IntInt','disable.Status',B=1));g.set('message','LayoutMessage','Back on Home. The campaign copy remains in backup history.');g.call('adopt','self:AdoptEditorLayout');g.wire((get(g,'HomeStorageKey'),'adopt.Key'),('home.Document','adopt.Document'),('home.Status','adopt.Status'))
    g.set('conflict','LayoutMessage','The campaign layout changed outside this session. Reopen it before switching.');g.set('error','LayoutMessage','Home could not be opened or the scope change could not be saved. Your current session is unchanged.');g.call('labels','self:RefreshLayoutFeedback')
    branch(g,'homeabsent',op(g,'missinghome','EqualEqual_IntInt','home.Status',B=0));branch(g,'homeenabled',prop(g,'enabledhome',LAYOUT,'Enabled','home.Document'))
    g.chain('allowed','context','known','current','unchanged','home','readable','homeabsent','disable','saved','message','adopt');g.chain('homeabsent.else','homeenabled','disable');g.chain('homeenabled.else','error');g.chain('unchanged.else','conflict','labels');g.chain('readable.else','error','labels');g.chain('saved.else','error')
    return g.function('UseEditorHomeLayout')


def request():
    g=Graph();ready(g);g.call('context','self:EditorScopeContext');branch(g,'known','context.Known');branch(g,'own','context.Own');g.call('confirm','self:ShowLayoutConfirmation',Action='scope_home',Title='Return to the shared Home layout?',Button='Return to Home',Message='Unsaved campaign edits will be dropped. The last saved campaign layout remains in backup history; Home and any Home recovery draft are preserved.');g.call('create','self:CreateEditorCampaignLayout');g.set('unknown','LayoutMessage','Campaign identity is unavailable. Save the campaign once before making its own layout.');g.call('labels','self:RefreshLayoutFeedback')
    g.chain('allowed','context','known','own','confirm');g.chain('own.else','create');g.chain('known.else','unknown','labels');return g.function('RequestEditorScopeChange')


def variables():return [v('ActiveCampaignID','string'),v('HomeStorageKey','string','home')]
def functions():return [context(),refresh(),adopt(),create_campaign(),use_home(),request()]
