"""Incremental fingerprint recovery for the native apply queue.

Only a unique mesh + original position match may recover a stale object path.
The scan examines one component at a time and never loads a level or mesh.
"""
from graph import Graph, variable as v, KML, KSL
from runtime import ENTRY, MUTATION, arr, unpack
from runtime_store import STR, call, branch, combine
from runtime_world import ACTOR, SCENE, SMC, set_value, validity
from runtime_apply import get, bump, clear, simple_result

COMP='/Script/Engine.ActorComponent'
ISM='/Script/Engine.InstancedStaticMeshComponent'


def prepare():
    g=Graph();arr(g,'len','Length',get(g,'RetryItems'))
    branch(g,'loop',call(g,'within',KML+':Less_IntInt',{'A':get(g,'WorkCursor'),'B':'len.ReturnValue'}))
    arr(g,'item','Get',get(g,'RetryItems'));g.wire((get(g,'WorkCursor'),'item.Index'))
    unpack(g,'mutation',MUTATION,'item.Item');unpack(g,'data',ENTRY,'mutation.Value')
    set_value(g,'remember','CurrentEntry','mutation.Value')
    branch(g,'fingerprint','data.HasFingerprint')
    call(g,'split',STR+'Split',{'SourceString':'data.Key'},InStr=':PersistentLevel.',SearchCase='CaseSensitive',SearchDir='FromStart')
    branch(g,'identity','split.ReturnValue')
    component=call(g,'component',STR+'Contains',{'SearchIn':'split.RightS'},Substring='.',bUseCase='true',bSearchFromEnd='false')
    actor=call(g,'actor',KML+':Not_PreBool',{'A':component});set_value(g,'targetkind','FPWantActor',actor)
    g.set('actorindex','FPActorIndex','0');g.set('componentindex','FPComponentIndex','-1')
    g.set('found','FPFound');g.set('ambiguous','FPAmbiguous','false');clear(g,'components','FPComponents');g.set('phase','Phase','10')
    g.call('dormant','self:ReportIssue',Code=2);g.wire(('mutation.Value','dormant.Value'))
    bump(g,'advance','WorkCursor');g.call('finish','self:FinishWork');simple_result(g)
    g.chain('entry','loop','remember','fingerprint','identity','targetkind','actorindex','componentindex','found','ambiguous','components','phase','result')
    g.chain('fingerprint.else','dormant','advance','result');g.chain('identity.else','dormant');g.chain('loop.else','finish','result')
    return g.function('DormantStep',outputs=[v('Continue','bool')])


def consider():
    g=Graph();unpack(g,'data',ENTRY,get(g,'CurrentEntry'))
    g.node('instance','cast',**{'class':ISM});g.wire(('entry.Component','instance.Object'))
    g.get('mesh',SMC+':StaticMesh');g.wire(('entry.Component','mesh.self'))
    branch(g,'meshvalid',validity(g,'validmesh','mesh.StaticMesh'))
    path=call(g,'path',KSL+':GetPathName',{'Object':'mesh.StaticMesh'})
    same=call(g,'same',STR+'EqualEqual_StrStr',{'A':path,'B':'data.FingerprintMesh'})
    location=call(g,'location',SCENE+':K2_GetComponentLocation',{'self':'entry.Component'})
    delta=call(g,'delta',KML+':Subtract_VectorVector',{'A':location,'B':'data.FingerprintPosition'})
    distance=call(g,'distance',KML+':Vector_GetAbsMax',{'A':delta})
    near=call(g,'near',KML+':LessEqual_DoubleDouble',{'A':distance},B=2)
    branch(g,'match',combine(g,'matches',[same,near]))
    branch(g,'actor',get(g,'FPWantActor'))
    owner=call(g,'owner',COMP+':GetOwner',{'self':'entry.Component'})
    set_value(g,'saveactor','local:Candidate',owner);set_value(g,'savecomponent','local:Candidate','entry.Component')
    g.get('candidate','local:Candidate')
    branch(g,'previous',validity(g,'hasfound',get(g,'FPFound')))
    sameobject=call(g,'sameobject',KML+':EqualEqual_ObjectObject',{'A':get(g,'FPFound'),'B':'candidate.Candidate'})
    branch(g,'duplicate',sameobject);g.set('ambiguous','FPAmbiguous','true')
    set_value(g,'remember','FPFound','candidate.Candidate')
    g.chain('entry','instance')
    g.chain('instance.CastFailed','meshvalid','match','actor','saveactor','previous','duplicate')
    g.chain('actor.else','savecomponent','previous');g.chain('previous.else','remember');g.chain('duplicate.else','ambiguous')
    return g.function('ConsiderFingerprint',inputs=[v('Component','object:'+SMC)],locals=[v('Candidate','object:/Script/CoreUObject.Object')])


def finish():
    g=Graph();unpack(g,'data',ENTRY,get(g,'CurrentEntry'))
    unique=call(g,'unique',KML+':Not_PreBool',{'A':get(g,'FPAmbiguous')})
    branch(g,'found',combine(g,'usable',[unique,validity(g,'valid',get(g,'FPFound'))]))
    g.call('bind','self:BindVanilla');g.wire(('data.Key','bind.Key'),(get(g,'FPFound'),'bind.Object'))
    branch(g,'bound','bind.Accepted')
    g.call('apply','self:SetVanilla',Present='true');g.wire(('data.Key','apply.Key'),(get(g,'CurrentEntry'),'apply.Value'))
    branch(g,'applied',call(g,'ok',KML+':EqualEqual_IntInt',{'A':'apply.Status'},B=1))
    g.call('count','self:CountNative',Present='true');g.wire((get(g,'CurrentEntry'),'count.Value'));bump(g,'refound','RefoundCount')
    g.call('dormant','self:ReportIssue',Code=2);g.wire((get(g,'CurrentEntry'),'dormant.Value'))
    g.call('invalid','self:ReportIssue');g.wire((get(g,'CurrentEntry'),'invalid.Value'),('apply.Status','invalid.Code'))
    bump(g,'advance','WorkCursor');g.set('phase','Phase','9');g.set('release','FPFound');clear(g,'clear','FPComponents')
    g.chain('entry','found','bind','bound','apply','applied','count','refound','advance','phase','release','clear')
    g.chain('found.else','dormant','advance');g.chain('bound.else','dormant');g.chain('applied.else','invalid','advance')
    return g.function('FinishFingerprint')


def scan():
    g=Graph();arr(g,'len','Length',get(g,'WorldActors'))
    branch(g,'actors',call(g,'awithin',KML+':Less_IntInt',{'A':get(g,'FPActorIndex'),'B':'len.ReturnValue'}))
    arr(g,'actor','Get',get(g,'WorldActors'));g.wire((get(g,'FPActorIndex'),'actor.Index'))
    branch(g,'valid',validity(g,'avalid','actor.Item'))
    owner=call(g,'owner',ACTOR+':GetOwner',{'self':'actor.Item'});g.node('self','self')
    managed=call(g,'managed',KML+':EqualEqual_ObjectObject',{'A':owner,'B':'self.self'});branch(g,'owned',managed)
    branch(g,'ready',call(g,'cindex',KML+':GreaterEqual_IntInt',{'A':get(g,'FPComponentIndex')},B=0))
    components=call(g,'list',ACTOR+':K2_GetComponentsByClass',{'self':'actor.Item'},ComponentClass=SMC)
    set_value(g,'cache','FPComponents',components);g.set('reset','FPComponentIndex','0')
    arr(g,'clen','Length',get(g,'FPComponents'))
    branch(g,'component',call(g,'cwithin',KML+':Less_IntInt',{'A':get(g,'FPComponentIndex'),'B':'clen.ReturnValue'}))
    arr(g,'item','Get',get(g,'FPComponents'));g.wire((get(g,'FPComponentIndex'),'item.Index'))
    branch(g,'cvalid',validity(g,'validcomponent','item.Item'))
    g.node('cast','cast',**{'class':SMC});g.wire(('item.Item','cast.Object'))
    g.call('consider','self:ConsiderFingerprint');g.wire(('cast.AsStatic Mesh Component','consider.Component'))
    bump(g,'advancecomponent','FPComponentIndex');bump(g,'advanceactor','FPActorIndex')
    g.set('unloaded','FPComponentIndex','-1');clear(g,'release','FPComponents')
    g.call('finish','self:FinishFingerprint');simple_result(g)
    g.chain('entry','actors','valid','owned','advanceactor','unloaded','release','result')
    g.chain('valid.else','advanceactor');g.chain('owned.else','ready','component','cvalid','cast','consider','advancecomponent','result')
    g.chain('ready.else','cache','reset','result');g.chain('component.else','advanceactor');g.chain('cvalid.else','advancecomponent')
    g.chain('cast.CastFailed','advancecomponent');g.chain('actors.else','finish','result')
    return g.function('FingerprintStep',outputs=[v('Continue','bool')])


def variables():
    return [v('FPActorIndex','int'),v('FPComponentIndex','int','-1'),v('FPWantActor','bool'),v('FPAmbiguous','bool'),
            v('FPFound','object:/Script/CoreUObject.Object'),v('FPComponents','object:'+COMP+'[]'),v('RefoundCount','int')]
