"""Explicit crash recovery and coalesced autosave for the native editor session."""
from graph import Graph, variable as v, KML
from runtime import LAYOUT
from runtime_store import call, branch, combine, STR
from runtime_world import set_value, validity
from runtime_apply import get, clock
from runtime_session import STORE, HISTORY, prop, method, accepted


def check_recovery():
    g=Graph();method(g,'load',STORE,'LoadLayout',get(g,'Storage'),{'Key':get(g,'SessionKey')},Draft='true',BeforeRevision=0)
    set_value(g,'status','LastDraftStatus','load.Status');set_value(g,'document','RecoveryDocument','load.Document')
    pending=call(g,'pending',KML+':NotEqual_IntInt',{'A':'load.Status'},B=0);set_value(g,'mark','RecoveryPending',pending)
    g.set('reset','RecoveryMatchesBase','false');branch(g,'valid',validity(g,'validdoc','load.Document'))
    base=prop(g,'base',LAYOUT,'Revision',get(g,'BaselineDocument'));baseid=prop(g,'baseid',LAYOUT,'ContentID',get(g,'BaselineDocument'))
    rev=prop(g,'rev',LAYOUT,'DraftBaseRevision','load.Document');identity=prop(g,'identity',LAYOUT,'DraftBaseID','load.Document')
    known=call(g,'known',KML+':Greater_Int64Int64',{'A':rev},B=0)
    samerev=call(g,'samerev',KML+':EqualEqual_Int64Int64',{'A':base,'B':rev});sameid=call(g,'sameid',STR+'EqualEqual_StrStr',{'A':baseid,'B':identity})
    set_value(g,'match','RecoveryMatchesBase',combine(g,'exactbase',[known,samerev,sameid]))
    g.chain('entry','load','status','document','mark','reset','valid','match')
    return g.function('CheckRecovery')


def recover():
    g=Graph();g.set('status','LastStatus','9')
    idle=call(g,'idle',KML+':Not_PreBool',{'A':get(g,'Busy')})
    branch(g,'allowed',combine(g,'canrecover',[get(g,'Editing'),get(g,'RecoveryPending'),idle,validity(g,'validdoc',get(g,'RecoveryDocument'))]))
    branch(g,'confirmed',combine(g,'consent',[get(g,'RecoveryMatchesBase'),'entry.AcceptMismatchedBase'],True))
    g.set('mismatch','LastStatus','10')
    method(g,'clone',STORE,'CloneLayout',get(g,'Storage'),{'Document':get(g,'RecoveryDocument')});branch(g,'valid',validity(g,'copyvalid','clone.DocumentCopy'))
    g.call('apply','self:BeginLayout');g.wire(('clone.DocumentCopy','apply.Document'));branch(g,'applied','apply.Accepted')
    set_value(g,'working','WorkingDocument','clone.DocumentCopy');method(g,'initialize',HISTORY,'Initialize',get(g,'History'),{'Document':get(g,'WorkingDocument')})
    g.set('dirty',HISTORY+':SavedVersion','-1');g.wire((get(g,'History'),'dirty.self'))
    g.set('pending','RecoveryPending','false');g.set('release','RecoveryDocument');g.set('version','LastDraftVersion','-1')
    g.call('schedule','self:ScheduleDraft');g.set('okstatus','LastStatus','1');g.set('yes','local:OK','true');accepted(g)
    g.chain('entry','status','allowed','confirmed','clone','valid','apply','applied','working','initialize','dirty','pending','release','version','schedule','okstatus','yes','result')
    g.chain('confirmed.else','mismatch','result')
    for pin in ['allowed.else','valid.else','applied.else']:g.chain(pin,'result')
    return g.function('RecoverDraft',inputs=[v('AcceptMismatchedBase','bool')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def discard_recovery():
    g=Graph();g.set('status','LastStatus','9');branch(g,'editing',combine(g,'recoverychoice',[get(g,'Editing'),get(g,'RecoveryPending')]))
    method(g,'clear',STORE,'ClearDraft',get(g,'Storage'),{'Key':get(g,'SessionKey')});branch(g,'cleared','clear.Cleared')
    g.set('pending','RecoveryPending','false');g.set('release','RecoveryDocument');g.set('draft','LastDraftStatus','1');g.set('okstatus','LastStatus','1')
    g.set('yes','local:OK','true');accepted(g);g.set('failed','LastDraftStatus','6');g.set('failstatus','LastStatus','6')
    g.chain('entry','status','editing','clear','cleared','pending','release','draft','okstatus','yes','result')
    g.chain('editing.else','result');g.chain('cleared.else','failed','failstatus','result')
    return g.function('DiscardRecovery',outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def flush():
    g=Graph();decided=call(g,'decided',KML+':Not_PreBool',{'A':get(g,'RecoveryPending')})
    branch(g,'allowed',combine(g,'canflush',[get(g,'Editing'),get(g,'DraftEnabled'),decided,validity(g,'historyvalid',get(g,'History')),validity(g,'storevalid',get(g,'Storage')),validity(g,'docvalid',get(g,'WorkingDocument'))]))
    method(g,'dirty',HISTORY,'IsDirty',get(g,'History'));branch(g,'changed','dirty.Dirty')
    version=prop(g,'version',HISTORY,'Version',get(g,'History'))
    same=call(g,'same',KML+':EqualEqual_IntInt',{'A':version,'B':get(g,'LastDraftVersion')})
    previousok=call(g,'previousok',KML+':EqualEqual_IntInt',{'A':get(g,'LastDraftStatus')},B=1)
    branch(g,'already',combine(g,'alreadywritten',[same,previousok]))
    rev=prop(g,'revision',LAYOUT,'Revision',get(g,'BaselineDocument'));baseid=prop(g,'baseid',LAYOUT,'ContentID',get(g,'BaselineDocument'))
    method(g,'save',STORE,'SaveLayout',get(g,'Storage'),{'Key':get(g,'SessionKey'),'Document':get(g,'WorkingDocument'),'BaseRevision':rev,'BaseID':baseid},Draft='true')
    set_value(g,'status','LastDraftStatus','save.Status');branch(g,'saved',call(g,'savedok',KML+':EqualEqual_IntInt',{'A':'save.Status'},B=1))
    method(g,'clear',STORE,'ClearDraft',get(g,'Storage'),{'Key':get(g,'SessionKey')});branch(g,'cleared','clear.Cleared')
    g.set('clearok','LastDraftStatus','1');g.set('clearfail','LastDraftStatus','6')
    set_value(g,'remember','LastDraftVersion',version);g.set('pending','DraftPending','false');g.set('yes','local:OK','true');accepted(g)
    retry=call(g,'retry',KML+':Add_DoubleDouble',{'A':clock(g,'now'),'B':get(g,'DraftRetryInterval')})
    set_value(g,'time','DraftDue',retry);g.set('again','DraftPending','true')
    g.chain('entry','allowed','dirty','changed','already','pending','yes','result')
    g.chain('already.else','save','status','saved','remember','pending');g.chain('saved.else','time','again','result')
    g.chain('changed.else','clear','cleared','clearok','remember');g.chain('cleared.else','clearfail','time');g.chain('allowed.else','result')
    return g.function('FlushDraft',outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def poll():
    g=Graph();due=call(g,'due',KML+':GreaterEqual_DoubleDouble',{'A':clock(g,'now'),'B':get(g,'DraftDue')})
    branch(g,'ready',combine(g,'pollready',[get(g,'Editing'),get(g,'DraftEnabled'),get(g,'DraftPending'),due]))
    g.call('flush','self:FlushDraft');g.chain('entry','ready','flush')
    return g.function('PollDraft')


def functions():return [check_recovery(),recover(),discard_recovery(),flush(),poll()]
