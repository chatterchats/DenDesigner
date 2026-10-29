"""In-game connection controls; only the dedicated native key file persists."""
from graph import Graph, variable as v, KML
from runtime_store import call, branch, combine, STR
from runtime_apply import get
from runtime_world import validity, set_value, finish_bool
from runtime_editor_host import widget
from runtime_gizmo_controller import op
from runtime_community_mailbox import HOLONET


def valid_key():
    g=Graph();length=call(g,'length',STR+'Len',{'S':'entry.Key'})
    prefix=call(g,'prefix',STR+'Left',{'SourceString':'entry.Key'},Count=4)
    branch(g,'shape',combine(g,'checks',[op(g,'size','EqualEqual_IntInt',length,B=68),call(g,'prefixmatch',STR+'EqualEqual_StrStr',{'A':prefix},B='zcu_')]))
    g.get('i','local:ConnectionKeyIndex');branch(g,'more',op(g,'within','Less_IntInt','i.ConnectionKeyIndex',B=68))
    char=call(g,'char',STR+'GetSubstring',{'SourceString':'entry.Key','StartIndex':'i.ConnectionKeyIndex'},Length=1)
    branch(g,'hex',call(g,'hexcheck',STR+'Contains',{'Substring':char},SearchIn='0123456789abcdef',bUseCase='true'))
    set_value(g,'next','local:ConnectionKeyIndex',op(g,'advance','Add_IntInt','i.ConnectionKeyIndex',B=1))
    g.set('yes','local:OK','true');finish_bool(g,'Valid')
    g.chain('entry','shape','more','hex','next','more');g.chain('more.else','yes','result')
    for pin in ['shape.else','hex.else']:g.chain(pin,'result')
    return g.function('ValidCommunityKey',inputs=[v('Key','string')],outputs=[v('Valid','bool')],locals=[v('ConnectionKeyIndex','int','4'),v('OK','bool','false')])


def connect():
    g=Graph();branch(g,'panel',validity(g,'alive',get(g,'CommunityPanel')))
    value=call(g,'read','/Script/UMG.EditableTextBox:GetText',{'self':widget(g,'keyfield','CommunityPanel','CommunityKey')})
    value=call(g,'string','/Script/Engine.KismetTextLibrary:Conv_TextToString',{'InText':value})
    set_value(g,'copy','local:ConnectionKeyCopy',value)
    call(g,'clear','/Script/UMG.EditableTextBox:SetText',{'self':widget(g,'clearfield','CommunityPanel','CommunityKey')},InText='')
    g.get('key','local:ConnectionKeyCopy');branch(g,'empty',call(g,'emptycheck',STR+'EqualEqual_StrStr',{'A':'key.ConnectionKeyCopy'},B=''))
    g.call('restore','self:StartCommunityFetch',Input='CONNECT')
    g.call('validate','self:ValidCommunityKey');g.wire(('key.ConnectionKeyCopy','validate.Key'));branch(g,'valid','validate.Valid')
    flag=call(g,'flag',KML+':SelectString',{'bPickA':get(g,'CommunityRemember')},A='1\t',B='0\t')
    payload=call(g,'payload',STR+'Concat_StrStr',{'A':flag,'B':'key.ConnectionKeyCopy'})
    g.call('send','self:StartCommunityTransfer',Input='AUTH');g.wire((payload,'send.Payload'))
    g.set('release','local:ConnectionKeyCopy','');g.set('status','CommunityMessage','Checking your HoloNet connection…');g.call('refresh','self:RefreshCommunityFeedback')
    g.set('invalid','CommunityMessage','Enter a complete game upload key from '+HOLONET+'/account. The key field has been cleared.')
    g.chain('entry','panel','copy','clear','empty','restore','release','refresh');g.chain('empty.else','validate','valid','send','status','release');g.chain('valid.else','invalid','release')
    return g.function('ConnectCommunity',locals=[v('ConnectionKeyCopy','string')])


def toggle():
    g=Graph();set_value(g,'toggle','CommunityRemember',call(g,'inverse',KML+':Not_PreBool',{'A':get(g,'CommunityRemember')}));g.call('refresh','self:RefreshCommunityFeedback');g.chain('entry','toggle','refresh');return g.function('ToggleRememberCommunity')


def forget():
    g=Graph();branch(g,'panel',validity(g,'alive',get(g,'CommunityPanel')));call(g,'clear','/Script/UMG.EditableTextBox:SetText',{'self':widget(g,'keyfield','CommunityPanel','CommunityKey')},InText='')
    g.set('off','CommunityRemember','false');g.call('send','self:StartCommunityFetch',Input='FORGET');g.chain('entry','panel','clear','off','send');g.chain('panel.else','off');return g.function('ForgetCommunity')


def clear():
    g=Graph();branch(g,'valid',validity(g,'alive',get(g,'CommunityPanel')));call(g,'clear','/Script/UMG.EditableTextBox:SetText',{'self':widget(g,'key','CommunityPanel','CommunityKey')},InText='');g.chain('entry','valid','clear');return g.function('ClearCommunityKey')


def functions():return [valid_key(),connect(),toggle(),forget(),clear()]
