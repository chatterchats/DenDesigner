"""Shared/campaign layout routing built on the native rotating store."""
from graph import Graph, variable as v, KML
from runtime_store import call, combine, branch, STR


def campaign_key():
    g=Graph()
    upper=call(g,'upper',STR+'ToUpper',{'SourceString':'entry.CampaignID'})
    size=call(g,'length',STR+'Len',{'S':upper})
    right=call(g,'rightlength',KML+':EqualEqual_IntInt',{'A':size},B=32)
    nonzero=call(g,'nonzero',STR+'NotEqual_StrStr',{'A':upper},B='0'*32)
    branch(g,'lengthok',combine(g,'knownid',[right,nonzero]))
    g.get('i','local:Cursor')
    within=call(g,'within',KML+':Less_IntInt',{'A':'i.Cursor'},B=32)
    branch(g,'loop',within)
    char=call(g,'char',STR+'GetCharacterAsNumber',{'SourceString':upper,'Index':'i.Cursor'})
    groups=[]
    for name,lo,hi in [('digit',48,57),('hex',65,70)]:
        a=call(g,name+'low',KML+':GreaterEqual_IntInt',{'A':char},B=lo)
        b=call(g,name+'high',KML+':LessEqual_IntInt',{'A':char},B=hi)
        groups.append(combine(g,name,[a,b]))
    branch(g,'allowed',combine(g,'any',groups,True))
    nxt=call(g,'next',KML+':Add_IntInt',{'A':'i.Cursor'},B=1)
    g.set('advance','local:Cursor')
    g.wire((nxt,'advance.Cursor'))
    key=call(g,'key',STR+'Concat_StrStr',{'B':upper},A='campaign-')
    g.set('output','local:StorageKey')
    g.wire((key,'output.StorageKey'))
    g.set('valid','local:Known','true')
    g.get('keyout','local:StorageKey')
    g.get('validout','local:Known')
    g.wire(('keyout.StorageKey','result.Key'),('validout.Known','result.Valid'),(upper,'result.CanonicalID'))
    g.chain('entry','lengthok','loop','allowed','advance','loop')
    g.chain('lengthok.else','result')
    g.chain('allowed.else','result')
    g.chain('loop.else','output','valid','result')
    return g.function('CampaignKey',inputs=[v('CampaignID','string')],
                      outputs=[v('Key','string'),v('Valid','bool'),v('CanonicalID','string')],
                      locals=[v('Cursor','int','0'),v('Known','bool','false'),v('StorageKey','string')])


def resolve(layout):
    g=Graph()
    g.call('key','self:CampaignKey')
    g.wire(('entry.CampaignID','key.CampaignID'))
    branch(g,'known','key.Valid')
    g.call('campaign','self:LoadLayout',Draft='false',BeforeRevision=0)
    g.wire(('key.Key','campaign.Key'))
    absent=call(g,'absent',KML+':EqualEqual_IntInt',{'A':'campaign.Status'},B=0)
    branch(g,'missing',absent)
    healthy=call(g,'healthy',KML+':LessEqual_IntInt',{'A':'campaign.Status'},B=2)
    branch(g,'healthybranch',healthy)
    g.get('enabled',layout+':Enabled')
    g.wire(('campaign.Document','enabled.self'))
    branch(g,'own','enabled.Enabled')
    for name,source in [('Key','key.Key'),('Document','campaign.Document'),('Status','campaign.Status')]:
        g.set('use'+name,'local:Resolved'+name)
        g.wire((source,'use'+name+'.Resolved'+name))
    g.set('ownflag','local:UseOwn','true')
    g.call('home','self:LoadLayout',Key='home',Draft='false',BeforeRevision=0)
    g.set('homedoc','local:ResolvedDocument')
    g.set('homestatus','local:ResolvedStatus')
    g.wire(('home.Document','homedoc.ResolvedDocument'),('home.Status','homestatus.ResolvedStatus'))
    for name in ['Key','Document','Status']:
        g.get('out'+name,'local:Resolved'+name)
        g.wire(('out'+name+'.Resolved'+name,'result.'+name))
    g.get('ownout','local:UseOwn')
    g.wire(('ownout.UseOwn','result.Own'),('key.Valid','result.CampaignKnown'))
    g.chain('entry','key','known','campaign','missing','home','homedoc','homestatus','result')
    g.chain('known.else','home')
    g.chain('missing.else','healthybranch','own','useKey','useDocument','useStatus','ownflag','result')
    g.chain('own.else','home')
    # A broken or newer campaign layout is not permission to edit home instead.
    g.chain('healthybranch.else','useKey')
    return g.function('ResolveLayout',inputs=[v('CampaignID','string')],
        outputs=[v('Document','object:'+layout),v('Status','int'),v('Key','string'),v('Own','bool'),v('CampaignKnown','bool')],
        locals=[v('ResolvedDocument','object:'+layout),v('ResolvedStatus','int','0'),v('ResolvedKey','string','home'),v('UseOwn','bool','false')])


def make_campaign(layout):
    g=Graph()
    g.call('key','self:CampaignKey')
    g.wire(('entry.CampaignID','key.CampaignID'))
    branch(g,'known','key.Valid')
    g.call('clone','self:CloneLayout')
    g.wire(('entry.Document','clone.Document'))
    valid=call(g,'valid','/Script/Engine.KismetSystemLibrary:IsValid',{'Object':'clone.DocumentCopy'})
    branch(g,'hasdoc',valid)
    for name,value in [('Scope','campaign'),('Enabled','true')]:
        g.set('write'+name,layout+':'+name,value)
        g.wire(('clone.DocumentCopy','write'+name+'.self'))
    g.set('id',layout+':CampaignID')
    g.wire(('clone.DocumentCopy','id.self'),('key.CanonicalID','id.CampaignID'))
    g.call('save','self:SaveLayout',Draft='false',BaseRevision=0,BaseID='')
    g.wire(('key.Key','save.Key'),('clone.DocumentCopy','save.Document'))
    g.set('status','local:ResultStatus')
    g.set('doc','local:ResultDocument')
    g.wire(('save.Status','status.ResultStatus'),('save.SavedDocument','doc.ResultDocument'))
    g.get('statusout','local:ResultStatus')
    g.get('docout','local:ResultDocument')
    g.wire(('statusout.ResultStatus','result.Status'),('docout.ResultDocument','result.SavedDocument'))
    g.chain('entry','key','known','clone','hasdoc','writeScope','writeEnabled','id','save','status','doc','result')
    g.chain('known.else','result')
    g.chain('hasdoc.else','result')
    return g.function('MakeCampaign',inputs=[v('CampaignID','string'),v('Document','object:'+layout)],
                      outputs=[v('SavedDocument','object:'+layout),v('Status','int')],
                      locals=[v('ResultStatus','int','7'),v('ResultDocument','object:'+layout)])


def use_home(layout):
    g=Graph()
    g.call('key','self:CampaignKey')
    g.wire(('entry.CampaignID','key.CampaignID'))
    branch(g,'known','key.Valid')
    g.call('load','self:LoadLayout',Draft='false',BeforeRevision=0)
    g.wire(('key.Key','load.Key'))
    g.set('status','local:ResultStatus')
    g.wire(('load.Status','status.ResultStatus'))
    absent=call(g,'absent',KML+':EqualEqual_IntInt',{'A':'load.Status'},B=0)
    branch(g,'missing',absent)
    healthy=call(g,'healthy',KML+':LessEqual_IntInt',{'A':'load.Status'},B=2)
    branch(g,'usable',healthy)
    g.get('enabled',layout+':Enabled')
    g.wire(('load.Document','enabled.self'))
    branch(g,'active','enabled.Enabled')
    g.call('clone','self:CloneLayout')
    g.wire(('load.Document','clone.Document'))
    g.set('disable',layout+':Enabled','false')
    g.wire(('clone.DocumentCopy','disable.self'))
    g.call('save','self:SaveLayout',Draft='false',BaseRevision=0,BaseID='')
    g.wire(('key.Key','save.Key'),('clone.DocumentCopy','save.Document'))
    g.set('saved','local:ResultStatus')
    g.wire(('save.Status','saved.ResultStatus'))
    g.set('ok','local:ResultStatus','1')
    g.get('out','local:ResultStatus')
    g.wire(('out.ResultStatus','result.Status'))
    g.chain('entry','key','known','load','status','missing','ok','result')
    g.chain('known.else','result')
    g.chain('missing.else','usable','active','clone','disable','save','saved','result')
    g.chain('usable.else','result')
    g.chain('active.else','ok')
    return g.function('UseHome',inputs=[v('CampaignID','string')],outputs=[v('Status','int')],locals=[v('ResultStatus','int','7')])


def spec(root,layout):
    return dict(kind='blueprint',path=root+'BP_DenLayouts',parent=root+'BP_DenStore',
                functions=[campaign_key(),resolve(layout),make_campaign(layout),use_home(layout)])
