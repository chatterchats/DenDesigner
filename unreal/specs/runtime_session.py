"""Native editor session: storage, history and queued world operations.

A coordinator supplies the resolved storage key/document. No campaign-save IO,
widget hooks or native extension functions are used here.
"""
from graph import Graph, variable as v, KML, KSL, GS
from runtime import ROOT, ENTRY, MUTATION, CHANGE, STEP, LAYOUT, arr, unpack
from runtime_store import call, branch, combine, STR
from runtime_world import set_value, validity, finish_bool
from runtime_apply import APPLY, get, clock

SESSION=ROOT+'BP_DenSession'
STORE=ROOT+'BP_DenLayouts'
HISTORY=ROOT+'BP_DenHistory'


def prop(g,name,cls,field,obj):
    g.get(name,cls+':'+field);g.wire((obj,name+'.self'));return name+'.'+field


def method(g,name,cls,fn,obj,inputs=None,**defaults):
    return call(g,name,cls+':'+fn,dict({'self':obj},**(inputs or {})),**defaults)


def accepted(g):
    finish_bool(g,source='local:OK')


def services():
    g=Graph();g.node('self','self')
    for n,var,cls,castpin in [('store','Storage',STORE,'AsBP Den Layouts'),('history','History',HISTORY,'AsBP Den History')]:
        branch(g,n+'valid',validity(g,n+'check',get(g,var)))
        obj=call(g,n+'create',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=cls)
        g.node(n+'cast','cast',**{'class':cls});g.wire((obj,n+'cast.Object'))
        set_value(g,n+'save',var,n+'cast.'+castpin)
        g.chain(n+'valid.else',n+'create',n+'cast',n+'save');g.chain(n+'cast.CastFailed','result')
    g.set('yes','local:OK','true');accepted(g)
    g.chain('entry','storevalid','historyvalid','yes','result');g.chain('storesave','historyvalid');g.chain('historysave','yes')
    return g.function('EnsureServices',outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def can_edit():
    g=Graph();notbusy=call(g,'idle',KML+':Not_PreBool',{'A':get(g,'Busy')})
    decided=call(g,'decided',KML+':Not_PreBool',{'A':get(g,'RecoveryPending')})
    ready=combine(g,'ready',[get(g,'Editing'),notbusy,decided,validity(g,'docvalid',get(g,'WorkingDocument')),validity(g,'historyvalid',get(g,'History')),validity(g,'storevalid',get(g,'Storage'))])
    g.wire((ready,'result.Ready'));g.chain('entry','result')
    return g.function('CanEdit',outputs=[v('Ready','bool')])


def open_session():
    g=Graph();g.set('status','LastStatus','9')
    idle=call(g,'idle',KML+':Not_PreBool',{'A':get(g,'Busy')});closed=call(g,'closed',KML+':Not_PreBool',{'A':get(g,'Editing')})
    branch(g,'available',combine(g,'availablecheck',[idle,closed]))
    g.call('services','self:EnsureServices');branch(g,'serviced','services.Accepted')
    method(g,'key',STORE,'ValidKey',get(g,'Storage'),{'Key':'entry.Key'});branch(g,'keyvalid','key.Valid')
    statuslo=call(g,'lo',KML+':GreaterEqual_IntInt',{'A':'entry.LoadStatus'},B=0)
    statushi=call(g,'hi',KML+':LessEqual_IntInt',{'A':'entry.LoadStatus'},B=2)
    branch(g,'loadok',combine(g,'readable',[statuslo,statushi]))
    set_value(g,'badload','LastStatus','entry.LoadStatus')
    branch(g,'absent',call(g,'missing',KML+':EqualEqual_IntInt',{'A':'entry.LoadStatus'},B=0))
    new=call(g,'create',GS+':CreateSaveGameObject',SaveGameClass=LAYOUT)
    g.node('cast','cast',**{'class':LAYOUT});g.wire((new,'cast.Object'))
    set_value(g,'newdoc','local:SourceDocument','cast.AsBP Den Layout Save')
    branch(g,'docvalid',validity(g,'documentvalid','entry.Document'))
    version=prop(g,'schema',LAYOUT,'SchemaVersion','entry.Document')
    enabled=prop(g,'enabled',LAYOUT,'Enabled','entry.Document')
    branch(g,'supported',combine(g,'usable',[call(g,'versionok',KML+':EqualEqual_IntInt',{'A':version},B=1),enabled]))
    set_value(g,'existing','local:SourceDocument','entry.Document')
    g.get('source','local:SourceDocument')
    method(g,'baseline',STORE,'CloneLayout',get(g,'Storage'),{'Document':'source.SourceDocument'})
    method(g,'working',STORE,'CloneLayout',get(g,'Storage'),{'Document':'source.SourceDocument'})
    branch(g,'copies',combine(g,'copied',[validity(g,'bvalid','baseline.DocumentCopy'),validity(g,'wvalid','working.DocumentCopy')]))
    set_value(g,'base','BaselineDocument','baseline.DocumentCopy');set_value(g,'work','WorkingDocument','working.DocumentCopy')
    set_value(g,'keycopy','SessionKey','entry.Key');set_value(g,'loadstatus','OpenedStatus','entry.LoadStatus')
    method(g,'initialize',HISTORY,'Initialize',get(g,'History'),{'Document':get(g,'WorkingDocument')})
    g.set('editing','Editing','true');g.set('pending','DraftPending','false');g.set('draftversion','LastDraftVersion','-1')
    g.call('apply','self:BeginLayout');g.wire((get(g,'WorkingDocument'),'apply.Document'))
    branch(g,'applied','apply.Accepted');g.call('draft','self:CheckRecovery')
    g.set('okstatus','LastStatus','1');g.set('yes','local:OK','true');accepted(g)
    g.set('invalid','LastStatus','7');g.set('stop','Editing','false')
    g.chain('entry','status','available','services','serviced','key','keyvalid','loadok','absent','create','cast','newdoc','baseline','working','copies','base','work','keycopy','loadstatus','initialize','editing','pending','draftversion','apply','applied','draft','okstatus','yes','result')
    g.chain('absent.else','docvalid','supported','existing','baseline');g.chain('loadok.else','badload','result')
    for pin in ['available.else','serviced.else']:g.chain(pin,'result')
    for pin in ['keyvalid.else','docvalid.else','supported.else','cast.CastFailed','copies.else']:g.chain(pin,'invalid','result')
    g.chain('applied.else','stop','result')
    return g.function('OpenSession',inputs=[v('Key','string'),v('Document','object:'+LAYOUT),v('LoadStatus','int')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false'),v('SourceDocument','object:'+LAYOUT)])


def schedule_draft():
    g=Graph();branch(g,'enabled',get(g,'DraftEnabled'));branch(g,'pending',get(g,'DraftPending'))
    due=call(g,'due',KML+':Add_DoubleDouble',{'A':clock(g,'now'),'B':get(g,'DraftInterval')})
    set_value(g,'time','DraftDue',due);g.set('mark','DraftPending','true')
    g.chain('entry','enabled','pending');g.chain('pending.else','time','mark')
    return g.function('ScheduleDraft')


def commit():
    g=Graph();g.set('status','LastStatus','9');g.call('ready','self:CanEdit');branch(g,'allowed','ready.Ready')
    # The queue accepts but does no world work before Pump. If history rejects
    # the batch, cancel that queued work before it can affect an actor.
    g.call('queue','self:BeginBatch',ReplaceAll='false');g.wire(('entry.Mutations','queue.Mutations'));branch(g,'queued','queue.Accepted')
    method(g,'commit',HISTORY,'Commit',get(g,'History'),{'Mutations':'entry.Mutations','Label':'entry.Label','MergeKey':'entry.MergeKey','Time':clock(g,'now')})
    branch(g,'committed','commit.Accepted');g.call('schedule','self:ScheduleDraft')
    g.set('okstatus','LastStatus','1');g.set('yes','local:OK','true');accepted(g)
    g.call('cancel','self:CancelWork');g.set('invalid','LastStatus','7')
    g.chain('entry','status','ready','allowed','queue','queued','commit','committed','schedule','okstatus','yes','result')
    g.chain('allowed.else','result');g.chain('queued.else','result');g.chain('committed.else','cancel','invalid','result')
    return g.function('CommitEdit',inputs=[v('Mutations','struct:'+MUTATION+'[]'),v('Label','string'),v('MergeKey','string')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def step_mutations(redo=False):
    g=Graph();side='After' if redo else 'Before';unpack(g,'step',STEP,'entry.Step')
    arr(g,'len','Length','step.Changes');g.get('i','local:ChangeIndex');g.get('edits','local:Edits')
    if not redo:
        set_value(g,'start','local:ChangeIndex',call(g,'last',KML+':Subtract_IntInt',{'A':'len.ReturnValue'},B=1))
    within=call(g,'within',KML+(':Less_IntInt' if redo else ':GreaterEqual_IntInt'),{'A':'i.ChangeIndex',**({'B':'len.ReturnValue'} if redo else {})},**({} if redo else {'B':0}))
    branch(g,'loop',within);arr(g,'item','Get','step.Changes');g.wire(('i.ChangeIndex','item.Index'));unpack(g,'change',CHANGE,'item.Item')
    g.node('mutation','make_struct',struct=MUTATION);g.wire(('change.'+side,'mutation.Value'),('change.'+side+'Exists','mutation.Present'))
    arr(g,'add','Add','edits.Edits');g.wire(('mutation.ST_DenMutation','add.NewItem'))
    set_value(g,'advance','local:ChangeIndex',call(g,'next',KML+':Add_IntInt',{'A':'i.ChangeIndex'},B=1 if redo else -1))
    g.wire(('edits.Edits','result.Mutations'));g.chain('entry',*(['start'] if not redo else []),'loop','add','advance','loop');g.chain('loop.else','result')
    return g.function('RedoMutations' if redo else 'UndoMutations',inputs=[v('Step','struct:'+STEP)],outputs=[v('Mutations','struct:'+MUTATION+'[]')],locals=[v('ChangeIndex','int','0'),v('Edits','struct:'+MUTATION+'[]')])


def travel(redo=False):
    g=Graph();name='Redo' if redo else 'Undo';g.set('status','LastStatus','9');g.call('ready','self:CanEdit');branch(g,'allowed','ready.Ready')
    steps=prop(g,'steps',HISTORY,'RedoSteps' if redo else 'UndoSteps',get(g,'History'));arr(g,'len','Length',steps)
    branch(g,'has',call(g,'nonempty',KML+':Greater_IntInt',{'A':'len.ReturnValue'},B=0))
    last=call(g,'last',KML+':Subtract_IntInt',{'A':'len.ReturnValue'},B=1);arr(g,'item','Get',steps);g.wire((last,'item.Index'))
    g.call('edits','self:'+name+'Mutations');g.wire(('item.Item','edits.Step'))
    g.call('queue','self:BeginBatch',ReplaceAll='false');g.wire(('edits.Mutations','queue.Mutations'));branch(g,'queued','queue.Accepted')
    method(g,'travel',HISTORY,name,get(g,'History'));branch(g,'travelled','travel.Succeeded')
    g.call('schedule','self:ScheduleDraft');g.set('okstatus','LastStatus','1');g.set('yes','local:OK','true');accepted(g)
    g.call('cancel','self:CancelWork')
    g.chain('entry','status','ready','allowed','has','edits','queue','queued','travel','travelled','schedule','okstatus','yes','result')
    for pin in ['allowed.else','has.else','queued.else']:g.chain(pin,'result')
    g.chain('travelled.else','cancel','result')
    return g.function(name+'Edit',outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def baseline_current():
    g=Graph();method(g,'load',STORE,'LoadLayout',get(g,'Storage'),{'Key':get(g,'SessionKey')},Draft='false',BeforeRevision=0)
    set_value(g,'status','LastStatus','load.Status')
    branch(g,'absent',call(g,'missing',KML+':EqualEqual_IntInt',{'A':'load.Status'},B=0))
    base=prop(g,'base',LAYOUT,'Revision',get(g,'BaselineDocument'))
    zero=call(g,'zero',KML+':EqualEqual_Int64Int64',{'A':base},B=0);set_value(g,'new','local:OK',zero)
    readable=call(g,'readable',KML+':LessEqual_IntInt',{'A':'load.Status'},B=2);branch(g,'healthy',readable)
    diskrev=prop(g,'diskrev',LAYOUT,'Revision','load.Document');diskid=prop(g,'diskid',LAYOUT,'ContentID','load.Document')
    baseid=prop(g,'baseid',LAYOUT,'ContentID',get(g,'BaselineDocument'))
    rev=call(g,'samerevision',KML+':EqualEqual_Int64Int64',{'A':base,'B':diskrev});ident=call(g,'sameid',STR+'EqualEqual_StrStr',{'A':baseid,'B':diskid})
    set_value(g,'equal','local:OK',combine(g,'same',[rev,ident]));g.get('ok','local:OK');branch(g,'matched','ok.OK');g.set('conflict','LastStatus','8');accepted(g)
    g.chain('entry','load','status','absent','new','matched','result');g.chain('matched.else','conflict','result')
    g.chain('absent.else','healthy','equal','matched');g.chain('healthy.else','result')
    return g.function('BaselineCurrent',outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def save():
    g=Graph();g.set('status','LastStatus','9');g.call('ready','self:CanEdit');branch(g,'allowed','ready.Ready')
    g.call('current','self:BaselineCurrent');branch(g,'unchanged','current.Accepted')
    method(g,'save',STORE,'SaveLayout',get(g,'Storage'),{'Key':get(g,'SessionKey'),'Document':get(g,'WorkingDocument')},Draft='false',BaseRevision=0,BaseID='')
    set_value(g,'savedstatus','LastStatus','save.Status');branch(g,'saved',call(g,'success',KML+':EqualEqual_IntInt',{'A':'save.Status'},B=1))
    set_value(g,'baseline','BaselineDocument','save.SavedDocument')
    method(g,'mark',HISTORY,'MarkSaved',get(g,'History'))
    g.set('pending','DraftPending','false');method(g,'clear',STORE,'ClearDraft',get(g,'Storage'),{'Key':get(g,'SessionKey')})
    branch(g,'cleared','clear.Cleared');g.set('draftok','LastDraftStatus','1');g.set('draftfail','LastDraftStatus','6')
    g.set('yes','local:OK','true');accepted(g)
    g.chain('entry','status','ready','allowed','current','unchanged','save','savedstatus','saved','baseline','mark','pending','clear','cleared','draftok','yes','result')
    g.chain('cleared.else','draftfail','yes')
    for pin in ['allowed.else','unchanged.else','saved.else']:g.chain(pin,'result')
    return g.function('SaveCurrent',outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def discard():
    g=Graph();g.set('status','LastStatus','9');branch(g,'editing',get(g,'Editing'))
    decided=call(g,'decided',KML+':Not_PreBool',{'A':get(g,'RecoveryPending')});branch(g,'norecovery',decided)
    method(g,'clone',STORE,'CloneLayout',get(g,'Storage'),{'Document':get(g,'BaselineDocument')})
    branch(g,'valid',validity(g,'copyvalid','clone.DocumentCopy'))
    g.call('apply','self:BeginLayout');g.wire(('clone.DocumentCopy','apply.Document'));branch(g,'applied','apply.Accepted')
    set_value(g,'working','WorkingDocument','clone.DocumentCopy');method(g,'initialize',HISTORY,'Initialize',get(g,'History'),{'Document':get(g,'WorkingDocument')})
    g.set('pending','DraftPending','false');method(g,'clear',STORE,'ClearDraft',get(g,'Storage'),{'Key':get(g,'SessionKey')})
    branch(g,'cleared','clear.Cleared');g.set('draftok','LastDraftStatus','1');g.set('draftfail','LastDraftStatus','6')
    g.set('okstatus','LastStatus','1');g.set('yes','local:OK','true');accepted(g)
    g.chain('entry','status','editing','norecovery','clone','valid','apply','applied','working','initialize','pending','clear','cleared','draftok','okstatus','yes','result')
    g.chain('cleared.else','draftfail','okstatus')
    for pin in ['editing.else','norecovery.else','valid.else','applied.else']:g.chain(pin,'result')
    return g.function('DiscardCurrent',outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def close():
    g=Graph();branch(g,'save','entry.SaveChanges');g.call('savechanges','self:SaveCurrent');branch(g,'saved','savechanges.Accepted')
    g.call('discard','self:DiscardCurrent');branch(g,'discarded','discard.Accepted')
    g.set('closed','Editing','false');g.set('yes','local:OK','true');accepted(g)
    g.chain('entry','save','savechanges','saved','closed','yes','result');g.chain('save.else','discard','discarded','closed')
    g.chain('saved.else','result');g.chain('discarded.else','result')
    return g.function('CloseSession',inputs=[v('SaveChanges','bool')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def spec():
    from runtime_drafts import functions as draft_functions
    g=Graph();g.node('tick','event',name='ReceiveTick');g.call('pump','self:Pump');g.call('draft','self:PollDraft');g.chain('tick','pump','draft')
    g.node('end','event',name='ReceiveEndPlay');g.call('flush','self:FlushDraft');g.set('close','Editing','false');g.call('cancel','self:CancelWork');g.call('forget','self:Forget');g.chain('end','flush','close','cancel','forget')
    return dict(kind='blueprint',path=SESSION,parent=APPLY,graph=g.spec(),
        variables=[v('Storage','object:'+STORE),v('History','object:'+HISTORY),v('WorkingDocument','object:'+LAYOUT),v('BaselineDocument','object:'+LAYOUT),
            v('RecoveryDocument','object:'+LAYOUT),v('Editing','bool','false'),v('SessionKey','string'),v('OpenedStatus','int'),v('LastStatus','int','9'),
            v('LastDraftStatus','int'),v('DraftEnabled','bool','true'),v('RecoveryPending','bool','false'),v('RecoveryMatchesBase','bool','false'),v('DraftPending','bool','false'),
            v('DraftDue','double'),v('DraftInterval','double','2'),v('DraftRetryInterval','double','5'),v('LastDraftVersion','int','-1')],
        functions=[services(),can_edit(),open_session(),schedule_draft(),commit(),step_mutations(),step_mutations(True),travel(),travel(True),baseline_current(),save(),discard(),close(),*draft_functions()])
