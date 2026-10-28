"""Pak-only layout storage using separate rotating SaveGame slots.

Uses mod SaveGame slots without accessing campaign saves or external filesystem APIs.
Load status: 0 absent, 1 loaded, 2 recovered with damaged bank(s), 3 damaged with
no usable copy, 4 newer schema, 5 invalid request. Save status: 1 verified success;
otherwise the load status, or 6 write/readback failure, 7 invalid document.
"""
from graph import Graph, variable as v, KML, KSL, GS

STR = '/Script/Engine.KismetStringLibrary:'
ARRAY = '/Script/Engine.KismetArrayLibrary:'
ROOT_SLOT = 'ZComDen/Native/v1/'
# All fields are copied and compared on readback. Adding a persisted field must
# add it here too (Entries uses the wildcard Array_Identical implementation).
FIELDS = {'SchemaVersion': 'int', 'StorageKey': 'string', 'Scope': 'string',
          'HasCompositionAnchor': 'bool', 'CompositionAnchor': 'vector',
          'CampaignID': 'string', 'Enabled': 'bool', 'DisplayName': 'string', 'GameVersion': 'string',
          'Revision': 'int64', 'ContentID': 'string', 'WrittenAt': 'string', 'IsDraft': 'bool',
          'DraftBaseRevision': 'int64', 'DraftBaseID': 'string', 'EntryCount': 'int',
          'Entries': 'array', 'WriteCompleteID': 'string'}


def call(g, name, function, inputs=None, **defaults):
    g.call(name, function, **defaults)
    for pin, source in (inputs or {}).items():
        g.wire((source, name + '.' + pin))
    return name + '.ReturnValue'


def combine(g, name, pins, either=False):
    result = pins[0]
    for i, other in enumerate(pins[1:]):
        result = call(g, name + str(i), KML + (':BooleanOR' if either else ':BooleanAND'), {'A': result, 'B': other})
    return result


def branch(g, name, condition):
    g.node(name, 'branch')
    g.wire((condition, name + '.Condition'))


def count_banks(g):
    return call(g, 'banks', KML + ':SelectInt', {'bPickA': 'entry.Draft'}, A=2, B=6)


def valid_key():
    g = Graph()
    size = call(g, 'size', STR + 'Len', {'S': 'entry.Key'})
    low = call(g, 'low', KML + ':Greater_IntInt', {'A': size}, B=0)
    high = call(g, 'high', KML + ':LessEqual_IntInt', {'A': size}, B=96)
    branch(g, 'length', combine(g, 'lengthok', [low, high]))
    g.get('i', 'local:Cursor')
    within = call(g, 'within', KML + ':Less_IntInt', {'A':'i.Cursor','B':size})
    branch(g, 'loop', within)
    char = call(g, 'char', STR + 'GetCharacterAsNumber', {'SourceString': 'entry.Key', 'Index': 'i.Cursor'})
    allowed = []
    for name, lo, hi in [('upper',65,90), ('lower',97,122), ('digit',48,57)]:
        a = call(g, name+'lo', KML + ':GreaterEqual_IntInt', {'A':char}, B=lo)
        b = call(g, name+'hi', KML + ':LessEqual_IntInt', {'A':char}, B=hi)
        allowed.append(combine(g,name,[a,b]))
    for name, code in [('dash',45), ('underscore',95)]:
        allowed.append(call(g,name,KML+':EqualEqual_IntInt',{'A':char},B=code))
    branch(g,'allowed',combine(g,'any',allowed,True))
    nxt=call(g,'next',KML+':Add_IntInt',{'A':'i.Cursor'},B=1)
    g.set('advance','local:Cursor')
    g.wire((nxt,'advance.Cursor'))
    g.set('valid','local:IsValidKey','true')
    g.get('out','local:IsValidKey')
    g.wire(('out.IsValidKey','result.Valid'))
    g.chain('entry','length','loop','allowed','advance','loop')
    g.chain('length.else','result')
    g.chain('allowed.else','result')
    g.chain('loop.else','valid','result')
    return g.function('ValidKey',inputs=[v('Key','string')],outputs=[v('Valid','bool')],
                      locals=[v('Cursor','int','0'),v('IsValidKey','bool','false')])


def bank_slot():
    g=Graph()
    suffix=call(g,'suffix',KML+':SelectString',{'bPickA':'entry.Draft'},A='-draft-',B='-layout-')
    prefix=call(g,'prefix',STR+'Concat_StrStr',{'B':'entry.Key'},A=ROOT_SLOT)
    keyed=call(g,'keyed',STR+'Concat_StrStr',{'A':prefix,'B':suffix})
    number=call(g,'number',STR+'Conv_IntToString',{'InInt':'entry.Bank'})
    result=call(g,'slot',STR+'Concat_StrStr',{'A':keyed,'B':number})
    g.wire((result,'result.Slot'))
    g.chain('entry','result')
    return g.function('BankSlot',inputs=[v('Key','string'),v('Bank','int'),v('Draft','bool')],outputs=[v('Slot','string')])


def load_layout(layout):
    g=Graph()
    g.call('key','self:ValidKey')
    g.wire(('entry.Key','key.Key'))
    beforeok=call(g,'beforeok',KML+':GreaterEqual_Int64Int64',{'A':'entry.BeforeRevision'},B=0)
    branch(g,'valid',combine(g,'requestok',['key.Valid',beforeok]))
    g.set('invalid','local:LoadStatus','5')
    g.get('i','local:Cursor')
    banks=count_banks(g)
    within=call(g,'within',KML+':Less_IntInt',{'A':'i.Cursor','B':banks})
    branch(g,'loop',within)
    g.call('slot','self:BankSlot')
    g.wire(('entry.Key','slot.Key'),('entry.Draft','slot.Draft'),('i.Cursor','slot.Bank'))
    call(g,'exists',GS+':DoesSaveGameExist',{'SlotName':'slot.Slot'},UserIndex=0)
    branch(g,'has','exists.ReturnValue')
    call(g,'load',GS+':LoadGameFromSlot',{'SlotName':'slot.Slot'},UserIndex=0)
    g.node('cast','cast',**{'class':layout})
    g.wire(('load.ReturnValue','cast.Object'))
    candidate='cast.AsBP Den Layout Save'
    for name in ['SchemaVersion','StorageKey','Revision','IsDraft','ContentID','EntryCount','Entries','WriteCompleteID']:
        g.get('candidate'+name,layout+':'+name)
        g.wire((candidate,'candidate'+name+'.self'))
    future=call(g,'future',KML+':Greater_IntInt',{'A':'candidateSchemaVersion.SchemaVersion'},B=1)
    branch(g,'isfuture',future)
    g.set('rememberfuture','local:HasFuture','true')
    checks=[call(g,'schema',KML+':EqualEqual_IntInt',{'A':'candidateSchemaVersion.SchemaVersion'},B=1),
            call(g,'samekey',STR+'EqualEqual_StrStr',{'A':'candidateStorageKey.StorageKey','B':'entry.Key'}),
            call(g,'samedraft',KML+':EqualEqual_BoolBool',{'A':'candidateIsDraft.IsDraft','B':'entry.Draft'}),
            call(g,'positive',KML+':Greater_Int64Int64',{'A':'candidateRevision.Revision'},B=0)]
    g.node('entrycount','array_call',function=ARRAY+'Array_Length')
    g.wire(('candidateEntries.Entries','entrycount.TargetArray'))
    checks.extend([call(g,'hasid',STR+'NotEqual_StrStr',{'A':'candidateContentID.ContentID'},B=''),
                   call(g,'complete',STR+'EqualEqual_StrStr',{'A':'candidateContentID.ContentID','B':'candidateWriteCompleteID.WriteCompleteID'}),
                   call(g,'countmatches',KML+':EqualEqual_IntInt',{'A':'candidateEntryCount.EntryCount','B':'entrycount.ReturnValue'})])
    branch(g,'sane',combine(g,'saneall',checks))
    g.set('damage','local:HasDamage','true')
    g.get('bestrev','local:BestRevision')
    newer=call(g,'newer',KML+':Greater_Int64Int64',{'A':'candidateRevision.Revision','B':'bestrev.BestRevision'})
    unbounded=call(g,'unbounded',KML+':EqualEqual_Int64Int64',{'A':'entry.BeforeRevision'},B=0)
    older=call(g,'older',KML+':Less_Int64Int64',{'A':'candidateRevision.Revision','B':'entry.BeforeRevision'})
    eligible=combine(g,'eligible',[newer,combine(g,'below',[unbounded,older],True)])
    branch(g,'choose',eligible)
    g.set('best','local:Best')
    g.set('bestrevision','local:BestRevision')
    g.set('bestbank','local:BestBank')
    g.wire((candidate,'best.Best'),('candidateRevision.Revision','bestrevision.BestRevision'),('i.Cursor','bestbank.BestBank'))
    nxt=call(g,'next',KML+':Add_IntInt',{'A':'i.Cursor'},B=1)
    g.set('advance','local:Cursor')
    g.wire((nxt,'advance.Cursor'))
    g.get('futureread','local:HasFuture')
    branch(g,'finishfuture','futureread.HasFuture')
    g.set('unsupported','local:LoadStatus','4')
    g.set('clearbest','local:Best')
    g.get('bestread','local:Best')
    hasbest=call(g,'hasbest',KSL+':IsValid',{'Object':'bestread.Best'})
    branch(g,'finishbest',hasbest)
    g.get('damageread','local:HasDamage')
    branch(g,'recovered','damageread.HasDamage')
    branch(g,'broken','damageread.HasDamage')
    for node,status in [('normal',1),('recovery',2),('corrupt',3)]:
        g.set(node,'local:LoadStatus',str(status))
    g.get('statusread','local:LoadStatus')
    g.get('bankread','local:BestBank')
    g.wire(('bestread.Best','result.Document'),('statusread.LoadStatus','result.Status'),('bankread.BestBank','result.Bank'))
    g.chain('entry','key','valid','loop','slot','exists','has','load','cast','isfuture','rememberfuture','advance','loop')
    g.chain('valid.else','invalid','result')
    g.chain('has.else','advance')
    g.chain('cast.CastFailed','damage','advance')
    g.chain('isfuture.else','sane','choose','best','bestrevision','bestbank','advance')
    g.chain('sane.else','damage')
    g.chain('choose.else','advance')
    g.chain('loop.else','finishfuture','unsupported','clearbest','result')
    g.chain('finishfuture.else','finishbest','recovered','recovery','result')
    g.chain('recovered.else','normal','result')
    g.chain('finishbest.else','broken','corrupt','result')
    g.chain('broken.else','result')
    return g.function('LoadLayout',inputs=[v('Key','string'),v('Draft','bool'),v('BeforeRevision','int64')],
        outputs=[v('Document','object:'+layout),v('Status','int'),v('Bank','int')],
        locals=[v('Cursor','int','0'),v('Best','object:'+layout),v('BestRevision','int64','0'),
                v('BestBank','int','-1'),v('HasDamage','bool','false'),v('HasFuture','bool','false'),v('LoadStatus','int','0')])


def clone_layout(layout):
    g=Graph()
    valid=call(g,'valid',KSL+':IsValid',{'Object':'entry.Document'})
    branch(g,'guard',valid)
    call(g,'create',GS+':CreateSaveGameObject',SaveGameClass=layout)
    g.node('cast','cast',**{'class':layout})
    g.wire(('create.ReturnValue','cast.Object'))
    g.set('cache','local:Copy')
    g.wire(('cast.AsBP Den Layout Save','cache.Copy'))
    g.get('copied','local:Copy')
    nodes=['entry','guard','create','cast','cache']
    for name in FIELDS:
        g.get('read'+name,layout+':'+name)
        g.set('write'+name,layout+':'+name)
        g.wire(('entry.Document','read'+name+'.self'),('copied.Copy','write'+name+'.self'),
               ('read'+name+'.'+name,'write'+name+'.'+name))
        nodes.append('write'+name)
    g.chain(*nodes,'result')
    g.chain('guard.else','result')
    g.chain('cast.CastFailed','result')
    g.wire(('copied.Copy','result.DocumentCopy'))
    return g.function('CloneLayout',inputs=[v('Document','object:'+layout)],outputs=[v('DocumentCopy','object:'+layout)],locals=[v('Copy','object:'+layout)])


def same_layout(layout):
    g=Graph()
    a=call(g,'av',KSL+':IsValid',{'Object':'entry.A'})
    b=call(g,'bv',KSL+':IsValid',{'Object':'entry.B'})
    branch(g,'guard',combine(g,'bothvalid',[a,b]))
    checks=[]
    for name,kind in FIELDS.items():
        for side in ['A','B']:
            g.get(side+name,layout+':'+name)
            g.wire(('entry.'+side,side+name+'.self'))
        if kind=='array':
            g.node('equal'+name,'array_call',function=ARRAY+'Array_Identical')
            g.wire(('A'+name+'.'+name,'equal'+name+'.ArrayA'),('B'+name+'.'+name,'equal'+name+'.ArrayB'))
            checks.append('equal'+name+'.ReturnValue')
        else:
            fn={'string':STR+'EqualEqual_StrStr','int':KML+':EqualEqual_IntInt',
                'vector':KML+':EqualEqual_VectorVector','int64':KML+':EqualEqual_Int64Int64','bool':KML+':EqualEqual_BoolBool'}[kind]
            checks.append(call(g,'equal'+name,fn,{'A':'A'+name+'.'+name,'B':'B'+name+'.'+name}, **({'ErrorTolerance':0} if kind=='vector' else {})))
    g.set('equal','local:Same')
    g.wire((combine(g,'allfields',checks),'equal.Same'))
    g.get('out','local:Same')
    g.wire(('out.Same','result.Equal'))
    g.chain('entry','guard','equal','result')
    g.chain('guard.else','result')
    return g.function('SameLayout',inputs=[v('A','object:'+layout),v('B','object:'+layout)],outputs=[v('Equal','bool')],locals=[v('Same','bool','false')])


def save_layout(layout):
    g=Graph()
    g.call('load','self:LoadLayout',BeforeRevision=0)
    g.wire(('entry.Key','load.Key'),('entry.Draft','load.Draft'))
    g.set('status','local:SaveStatus')
    g.wire(('load.Status','status.SaveStatus'))
    statusok=call(g,'statusok',KML+':LessEqual_IntInt',{'A':'load.Status'},B=2)
    branch(g,'allowed',statusok)
    inputvalid=call(g,'inputvalid',KSL+':IsValid',{'Object':'entry.Document'})
    branch(g,'valid',inputvalid)
    g.get('schema',layout+':SchemaVersion')
    g.wire(('entry.Document','schema.self'))
    schemaok=call(g,'schemaok',KML+':EqualEqual_IntInt',{'A':'schema.SchemaVersion'},B=1)
    baseok=call(g,'baseok',KML+':GreaterEqual_Int64Int64',{'A':'entry.BaseRevision'},B=0)
    zero=call(g,'basezero',KML+':EqualEqual_Int64Int64',{'A':'entry.BaseRevision'},B=0)
    empty=call(g,'baseempty',STR+'EqualEqual_StrStr',{'A':'entry.BaseID'},B='')
    paired=call(g,'basepaired',KML+':EqualEqual_BoolBool',{'A':zero,'B':empty})
    savedbase=combine(g,'savedbase',['entry.Draft',combine(g,'nobase',[zero,empty])],True)
    branch(g,'schemaallowed',combine(g,'inputok',[schemaok,baseok,paired,savedbase]))
    g.set('invalid','local:SaveStatus','7')
    oldvalid=call(g,'oldvalid',KSL+':IsValid',{'Object':'load.Document'})
    branch(g,'old','oldvalid.ReturnValue')
    g.get('oldrev',layout+':Revision')
    g.wire(('load.Document','oldrev.self'))
    newrev=call(g,'nextrevision',KML+':Add_Int64Int64',{'A':'oldrev.Revision'},B=1)
    g.set('rev','local:NextRevision')
    g.wire((newrev,'rev.NextRevision'))
    g.get('revread','local:NextRevision')
    positive=call(g,'positive',KML+':Greater_Int64Int64',{'A':'revread.NextRevision'},B=0)
    branch(g,'nooverflow',positive)
    g.call('clone','self:CloneLayout')
    g.wire(('entry.Document','clone.Document'))
    copyvalid=call(g,'copyvalid',KSL+':IsValid',{'Object':'clone.DocumentCopy'})
    branch(g,'copied',copyvalid)
    g.set('candidate','local:Candidate')
    g.wire(('clone.DocumentCopy','candidate.Candidate'))
    g.get('candidateget','local:Candidate')
    now=call(g,'now',KML+':UtcNow')
    unix=call(g,'unix',KML+':ToUnixTimestamp',{'Time':now})
    timestamp=call(g,'timestamp',STR+'Conv_Int64ToString',{'InInt':unix})
    guid=call(g,'guid','/Script/Engine.KismetGuidLibrary:NewGuid')
    identity=call(g,'identity','/Script/Engine.KismetGuidLibrary:Conv_GuidToString',{'InGuid':guid})
    g.get('entries',layout+':Entries')
    g.wire(('candidateget.Candidate','entries.self'))
    g.node('entrycount','array_call',function=ARRAY+'Array_Length')
    g.wire(('entries.Entries','entrycount.TargetArray'))
    g.get('idread',layout+':ContentID')
    g.wire(('candidateget.Candidate','idread.self'))
    values={'StorageKey':'entry.Key','Revision':'revread.NextRevision','IsDraft':'entry.Draft',
            'DraftBaseRevision':'entry.BaseRevision','DraftBaseID':'entry.BaseID', 'WrittenAt':timestamp,
            'ContentID':identity,'EntryCount':'entrycount.ReturnValue','WriteCompleteID':'idread.ContentID'}
    writes=[]
    for name,source in values.items():
        node='write'+name
        g.set(node,layout+':'+name)
        g.wire(('candidateget.Candidate',node+'.self'),(source,node+'.'+name))
        writes.append(node)
    banks=count_banks(g)
    nextbank=call(g,'nextbank',KML+':Add_IntInt',{'A':'load.Bank'},B=1)
    bank=call(g,'bank',KML+':Percent_IntInt',{'A':nextbank,'B':banks})
    g.call('slot','self:BankSlot')
    g.wire(('entry.Key','slot.Key'),('entry.Draft','slot.Draft'),(bank,'slot.Bank'))
    g.set('writing','local:SaveStatus','6')
    call(g,'save',GS+':SaveGameToSlot',{'SaveGameObject':'candidateget.Candidate','SlotName':'slot.Slot'},UserIndex=0)
    branch(g,'saved','save.ReturnValue')
    call(g,'readback',GS+':LoadGameFromSlot',{'SlotName':'slot.Slot'},UserIndex=0)
    g.node('cast','cast',**{'class':layout})
    g.wire(('readback.ReturnValue','cast.Object'))
    g.call('verify','self:SameLayout')
    g.wire(('candidateget.Candidate','verify.A'),('cast.AsBP Den Layout Save','verify.B'))
    branch(g,'verified','verify.Equal')
    g.set('success','local:SaveStatus','1')
    g.set('persisted','local:Persisted')
    g.wire(('cast.AsBP Den Layout Save','persisted.Persisted'))
    g.get('out','local:Persisted')
    g.get('statusout','local:SaveStatus')
    g.wire(('out.Persisted','result.SavedDocument'),('statusout.SaveStatus','result.Status'))
    g.chain('entry','load','status','allowed','valid','schemaallowed','old','rev','nooverflow','clone','copied','candidate',*writes,'slot','writing','save','saved','readback','cast','verify','verified','success','persisted','result')
    g.chain('allowed.else','result')
    g.chain('valid.else','invalid','result')
    g.chain('schemaallowed.else','invalid')
    g.chain('old.else','nooverflow')
    g.chain('nooverflow.else','invalid')
    g.chain('copied.else','invalid')
    g.chain('saved.else','result')
    g.chain('cast.CastFailed','result')
    g.chain('verified.else','result')
    return g.function('SaveLayout',inputs=[v('Key','string'),v('Document','object:'+layout),v('Draft','bool'),v('BaseRevision','int64'),v('BaseID','string')],
        outputs=[v('SavedDocument','object:'+layout),v('Status','int')],
        locals=[v('SaveStatus','int','0'),v('NextRevision','int64','1'),v('Candidate','object:'+layout),v('Persisted','object:'+layout)])


def clear_draft():
    g=Graph()
    g.call('key','self:ValidKey')
    g.wire(('entry.Key','key.Key'))
    branch(g,'valid','key.Valid')
    g.set('ok','local:AllRemoved','true')
    g.get('i','local:Cursor')
    within=call(g,'within',KML+':Less_IntInt',{'A':'i.Cursor'},B=2)
    branch(g,'loop',within)
    g.call('slot','self:BankSlot',Draft='true')
    g.wire(('entry.Key','slot.Key'),('i.Cursor','slot.Bank'))
    call(g,'exists',GS+':DoesSaveGameExist',{'SlotName':'slot.Slot'},UserIndex=0)
    branch(g,'has','exists.ReturnValue')
    call(g,'delete',GS+':DeleteGameInSlot',{'SlotName':'slot.Slot'},UserIndex=0)
    call(g,'still',GS+':DoesSaveGameExist',{'SlotName':'slot.Slot'},UserIndex=0)
    branch(g,'remains','still.ReturnValue')
    g.set('failed','local:AllRemoved','false')
    nxt=call(g,'next',KML+':Add_IntInt',{'A':'i.Cursor'},B=1)
    g.set('advance','local:Cursor')
    g.wire((nxt,'advance.Cursor'))
    g.get('out','local:AllRemoved')
    g.wire(('out.AllRemoved','result.Cleared'))
    g.chain('entry','key','valid','ok','loop','slot','exists','has','delete','still','remains','failed','advance','loop')
    g.chain('has.else','advance')
    g.chain('remains.else','advance')
    g.chain('loop.else','result')
    g.chain('valid.else','result')
    return g.function('ClearDraft',inputs=[v('Key','string')],outputs=[v('Cleared','bool')],locals=[v('AllRemoved','bool','false'),v('Cursor','int','0')])


def spec(root,layout,store_name='BP_DenStore',cast_name='AsBP Den Layout Save',method_suffix='Layout'):
    result = dict(kind='blueprint',path=root+store_name,parent='/Script/CoreUObject.Object',
                functions=[valid_key(),bank_slot(),load_layout(layout),clone_layout(layout),same_layout(layout),save_layout(layout),clear_draft()])

    # The same storage algorithm also persists the preset library, whose Entries
    # array contains preset values rather than scene entries. Specialize types
    # and method names at authoring time; no runtime reflection is needed.
    methods = {x + 'Layout': x + method_suffix for x in ['Load','Save','Clone','Same']}
    def specialize(value):
        if isinstance(value, str):
            value = value.replace('AsBP Den Layout Save', cast_name)
            for old,new in methods.items():
                if value == old:
                    return new
                value = value.replace('self:' + old, 'self:' + new)
            return value
        if isinstance(value, list):
            return [specialize(x) for x in value]
        if isinstance(value, dict):
            return {k:specialize(x) for k,x in value.items()}
        return value
    return specialize(result)
