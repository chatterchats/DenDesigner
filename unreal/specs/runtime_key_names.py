"""Blueprint key codec for stable persisted names and UMG InputKeySelector.

FKey.KeyName is private; literal keys are authored into standard Blueprint pins.
Runtime conversion never reflects private fields or parses localized key labels.
"""
from graph import Graph, variable as v
from runtime_preferences import ROOT, KEY_NAMES, output
from runtime_store import call, branch, STR

CODEC=ROOT+'BP_DenKeyNames'
KEY='struct:/Script/InputCore.Key'
INPUT='/Script/Engine.KismetInputLibrary:'


def from_name():
    g=Graph();previous='entry'
    for i,name in enumerate(KEY_NAMES):
        ident='k'+str(i);branch(g,ident,call(g,ident+'same',STR+'EqualEqual_StrStr',{'A':'entry.Name'},B=name))
        g.set(ident+'value','local:ResultKey',name)
        g.chain(previous,ident,ident+'value','known');previous=ident+'.else'
    g.set('known','local:ResultKnown','true');g.chain('known','result');g.chain(previous,'result')
    return g.function('KeyFromName',inputs=[v('Name','string')],outputs=[v('Key',KEY),v('Known','bool')],
                      locals=[output(g,'Key',KEY,'None'),output(g,'Known','bool','false')])


def to_name():
    g=Graph();previous='entry'
    for i,name in enumerate(KEY_NAMES):
        ident='k'+str(i);branch(g,ident,call(g,ident+'same',INPUT+'EqualEqual_KeyKey',{'A':'entry.Key'},B=name))
        g.set(ident+'value','local:ResultName',name)
        g.chain(previous,ident,ident+'value','known');previous=ident+'.else'
    g.set('known','local:ResultKnown','true');g.chain('known','result');g.chain(previous,'result')
    label=call(g,'label',INPUT+'Key_GetDisplayName',{'Key':'entry.Key'},bLongDisplayName='true');g.wire((label,'result.Label'))
    return g.function('NameFromKey',inputs=[v('Key',KEY)],outputs=[v('Name','string'),v('Known','bool'),v('Label','text')],
                      locals=[output(g,'Name','string'),output(g,'Known','bool','false')])


def spec():
    return dict(kind='blueprint',path=CODEC,parent='/Script/CoreUObject.Object',functions=[from_name(),to_name()])
