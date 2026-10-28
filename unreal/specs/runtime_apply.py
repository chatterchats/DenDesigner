"""Frame-budgeted native layout application; no blocking loads or widget callbacks.

Full layouts replace pending work. Incremental batches are accepted only while
idle, preserving existing actors and baseline snapshots. Missing vanilla objects
are retried before being reported; the input document is never modified.
"""
from graph import Graph, variable as v, KML, KSL, GS
from runtime import ROOT, ENTRY, MUTATION, LAYOUT, arr, unpack, struct
from runtime_store import call, branch, combine
from runtime_world import ACTOR, WORLD, RECORD, MESH, MATERIAL, set_value, validity, finish_bool
from runtime_assets import JOB

APPLY=ROOT+'BP_DenApply'
ISSUE=ROOT+'ST_DenApplyIssue'


def get(g,name):
    ident='get'+name
    if not any(n['id']==ident for n in g.nodes):g.get(ident,name)
    return ident+'.'+name


def clock(g,name):
    call(g,name,GS+':GetAccurateRealTime')
    return call(g,name+'sum',KML+':Add_DoubleDouble',{'A':name+'.Seconds','B':name+'.PartialSeconds'})


def bump(g,name,var):
    result=call(g,name+'add',KML+':Add_IntInt',{'A':get(g,var)},B=1)
    set_value(g,name,var,result)


def clear(g,name,var):
    arr(g,name,'Clear',get(g,var))


def simple_result(g,source='true'):
    g.node('resultvalue','call',function=KML+':Not_PreBool',defaults={'A':'false' if source=='true' else 'true'})
    g.wire(('resultvalue.ReturnValue','result.Continue'))


def cancel():
    g=Graph();branch(g,'valid',validity(g,'check',get(g,'PendingJob')))
    call(g,'destroy',ACTOR+':K2_DestroyActor',{'self':get(g,'PendingJob')})
    g.set('job','PendingJob');g.set('mesh','ReadyMesh');clear(g,'materials','ReadyMaterials')
    g.set('fp','FPFound');clear(g,'fpcomponents','FPComponents')
    clear(g,'work','WorkItems');clear(g,'pending','RetryItems');clear(g,'nextretry','NextRetry')
    clear(g,'indexchanges','IndexMutations');g.set('indexinvalid','IndexDeltaValid','false')
    g.set('stop','Busy','false');g.set('phase','Phase','0');bump(g,'generation','Generation')
    g.chain('entry','valid','destroy','job','mesh','materials','fp','fpcomponents','work','pending','nextretry','indexchanges','indexinvalid','stop','phase','generation')
    g.chain('valid.else','job')
    return g.function('CancelWork')


def begin_batch():
    g=Graph()
    idle=call(g,'idle',KML+':Not_PreBool',{'A':get(g,'Busy')})
    branch(g,'allowed',combine(g,'allowedstart',[idle,'entry.ReplaceAll'],True))
    set_value(g,'indexbase','local:PreviousIndexGeneration',get(g,'Generation'))
    same=call(g,'indexsame',KML+':EqualEqual_IntInt',{'A':get(g,'IndexThroughGeneration'),'B':get(g,'Generation')})
    incremental=call(g,'incremental',KML+':Not_PreBool',{'A':'entry.ReplaceAll'})
    branch(g,'carry',combine(g,'carryvalid',[get(g,'IndexDeltaValid'),same,incremental]))
    set_value(g,'carrychanges','local:PreviousIndexMutations',get(g,'IndexMutations'));set_value(g,'carrybase','local:PreviousIndexGeneration',get(g,'IndexFromGeneration'))
    g.call('cancel','self:CancelWork')
    set_value(g,'copy','WorkItems','entry.Mutations')
    reset=[]
    for var in ['WorkCursor','MaterialCursor','RetryPass','PlacedCount','HiddenCount','MovedCount','RefoundCount','DormantCount','ErrorCount','Frames']:
        name='reset'+var;g.set(name,var,'0');reset.append(name)
    for var in ['WorkSeconds','SlowestStep','TotalSeconds']:
        name='reset'+var;g.set(name,var,'0');reset.append(name)
    clear(g,'issues','Issues');set_value(g,'started','StartedAt',clock(g,'now'))
    g.set('busy','Busy','true');branch(g,'replace','entry.ReplaceAll')
    g.set('cleanup','Phase','1');g.call('refresh','self:RefreshActors');g.set('vanilla','Phase','2')
    g.get('previousindex','local:PreviousIndexMutations');set_value(g,'indexcopy','IndexMutations','previousindex.PreviousIndexMutations')
    arr(g,'indexappend','Append',get(g,'IndexMutations'));g.wire(('entry.Mutations','indexappend.SourceArray'))
    g.get('previousgeneration','local:PreviousIndexGeneration');set_value(g,'indexfrom','IndexFromGeneration','previousgeneration.PreviousIndexGeneration')
    set_value(g,'indexthrough','IndexThroughGeneration',get(g,'Generation'));g.set('indexvalid','IndexDeltaValid','true')
    g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','allowed','indexbase','carry','carrychanges','carrybase','cancel','copy',*reset,'issues','started','busy','replace','cleanup','yes','result')
    g.chain('carry.else','cancel');g.chain('replace.else','indexcopy','indexappend','indexfrom','indexthrough','indexvalid','refresh','vanilla','yes');g.chain('allowed.else','result')
    return g.function('BeginBatch',inputs=[v('Mutations','struct:'+MUTATION+'[]'),v('ReplaceAll','bool')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false'),v('PreviousIndexGeneration','int'),v('PreviousIndexMutations','struct:'+MUTATION+'[]')])


def begin_layout():
    g=Graph();branch(g,'valid',validity(g,'check','entry.Document'))
    g.get('schema',LAYOUT+':SchemaVersion');g.wire(('entry.Document','schema.self'))
    branch(g,'supported',call(g,'version',KML+':EqualEqual_IntInt',{'A':'schema.SchemaVersion'},B=1))
    g.get('enabled',LAYOUT+':Enabled');g.wire(('entry.Document','enabled.self'));branch(g,'active','enabled.Enabled')
    g.get('entries',LAYOUT+':Entries');g.wire(('entry.Document','entries.self'))
    g.get('i','local:Index');g.get('list','local:Batch')
    arr(g,'length','Length','entries.Entries')
    branch(g,'loop',call(g,'within',KML+':Less_IntInt',{'A':'i.Index','B':'length.ReturnValue'}))
    arr(g,'item','Get','entries.Entries');g.wire(('i.Index','item.Index'))
    g.node('mutation','make_struct',struct=MUTATION,defaults={'Present':'true'})
    g.wire(('item.Item','mutation.Value'));arr(g,'append','Add','list.Batch');g.wire(('mutation.ST_DenMutation','append.NewItem'))
    set_value(g,'advance','local:Index',call(g,'next',KML+':Add_IntInt',{'A':'i.Index'},B=1))
    g.call('begin','self:BeginBatch',ReplaceAll='true');g.wire(('list.Batch','begin.Mutations'))
    set_value(g,'ok','local:OK','begin.Accepted');finish_bool(g)
    g.chain('entry','valid','supported','active','loop','append','advance','loop');g.chain('valid.else','result');g.chain('supported.else','result');g.chain('active.else','begin');g.chain('loop.else','begin','ok','result')
    return g.function('BeginLayout',inputs=[v('Document','object:'+LAYOUT)],outputs=[v('Accepted','bool')],locals=[v('Index','int','0'),v('Batch','struct:'+MUTATION+'[]'),v('OK','bool','false')])


def issue():
    g=Graph();g.node('row','make_struct',struct=ISSUE)
    g.wire(('entry.Value','row.Value'),('entry.Code','row.Code'))
    arr(g,'append','Add',get(g,'Issues'));g.wire(('row.ST_DenApplyIssue','append.NewItem'))
    branch(g,'dormant',call(g,'missing',KML+':EqualEqual_IntInt',{'A':'entry.Code'},B=2))
    bump(g,'missingcount','DormantCount');bump(g,'errors','ErrorCount')
    g.chain('entry','append','dormant','missingcount');g.chain('dormant.else','errors')
    return g.function('ReportIssue',inputs=[v('Value','struct:'+ENTRY),v('Code','int')])


def count_native():
    g=Graph();unpack(g,'data',ENTRY,'entry.Value');branch(g,'present','entry.Present')
    branch(g,'hidden','data.Hidden');bump(g,'hiddenplus','HiddenCount')
    branch(g,'moved',combine(g,'hastransform',['data.HasPosition','data.HasRotation','data.HasScale'],True));bump(g,'moveplus','MovedCount')
    g.chain('entry','present','hidden','hiddenplus','moved','moveplus');g.chain('hidden.else','moved')
    return g.function('CountNative',inputs=[v('Value','struct:'+ENTRY),v('Present','bool')])


def consume_index_changes():
    g=Graph();clear(g,'clear','IndexMutations');g.set('invalid','IndexDeltaValid','false');g.chain('entry','clear','invalid')
    return g.function('ConsumeIndexChanges')


def finish():
    g=Graph();g.set('stop','Busy','false');g.set('phase','Phase','0')
    elapsed=call(g,'elapsed',KML+':Subtract_DoubleDouble',{'A':clock(g,'now'),'B':get(g,'StartedAt')})
    set_value(g,'total','TotalSeconds',elapsed)
    clear(g,'work','WorkItems');clear(g,'retry','RetryItems');clear(g,'next','NextRetry')
    g.chain('entry','stop','phase','total','work','retry','next')
    return g.function('FinishWork')


def cleanup_step():
    g=Graph();arr(g,'plen','Length',get(g,'Placed'))
    branch(g,'hasprops',call(g,'pnonempty',KML+':Greater_IntInt',{'A':'plen.ReturnValue'},B=0))
    arr(g,'prop','Get',get(g,'Placed'),Index=0)
    branch(g,'propvalid',validity(g,'pvalid','prop.Item'));call(g,'destroy',ACTOR+':K2_DestroyActor',{'self':'prop.Item'})
    arr(g,'removeprop','Remove',get(g,'Placed'),IndexToRemove=0)
    arr(g,'rlen','Length',get(g,'Records'))
    branch(g,'hasrecords',call(g,'rnonempty',KML+':Greater_IntInt',{'A':'rlen.ReturnValue'},B=0))
    arr(g,'record','Get',get(g,'Records'),Index=0)
    branch(g,'recordvalid',validity(g,'rvalid','record.Item'))
    call(g,'restore',RECORD+':Apply',{'self':'record.Item'},Present='false')
    arr(g,'removerecord','Remove',get(g,'Records'),IndexToRemove=0)
    g.call('refresh','self:RefreshActors');g.set('next','Phase','2');simple_result(g)
    g.chain('entry','hasprops','propvalid','destroy','removeprop','result');g.chain('propvalid.else','removeprop')
    g.chain('hasprops.else','hasrecords','recordvalid','restore','removerecord','result');g.chain('recordvalid.else','removerecord')
    g.chain('hasrecords.else','refresh','next','result')
    return g.function('CleanupStep',outputs=[v('Continue','bool')])



def drop_retry():
    # A later operation for the same identity supersedes an earlier unresolved
    # operation in this batch (including removal of an object not yet loaded).
    from runtime_store import STR
    g=Graph();g.get('i','local:PendingIndex');arr(g,'len','Length',get(g,'RetryItems'))
    branch(g,'loop',call(g,'within',KML+':Less_IntInt',{'A':'i.PendingIndex','B':'len.ReturnValue'}))
    arr(g,'item','Get',get(g,'RetryItems'));g.wire(('i.PendingIndex','item.Index'))
    unpack(g,'mutation',MUTATION,'item.Item');unpack(g,'data',ENTRY,'mutation.Value')
    branch(g,'same',call(g,'equal',STR+'EqualEqual_StrStr',{'A':'data.Key','B':'entry.Key'}))
    arr(g,'remove','Remove',get(g,'RetryItems'));g.wire(('i.PendingIndex','remove.IndexToRemove'))
    set_value(g,'advance','local:PendingIndex',call(g,'next',KML+':Add_IntInt',{'A':'i.PendingIndex'},B=1))
    g.chain('entry','loop','same','remove','loop');g.chain('same.else','advance','loop')
    return g.function('DropPendingNative',inputs=[v('Key','string')],locals=[v('PendingIndex','int','0')])


def native_step(retry=False):
    g=Graph();items=get(g,'RetryItems' if retry else 'WorkItems');cursor=get(g,'WorkCursor')
    arr(g,'len','Length',items);branch(g,'loop',call(g,'within',KML+':Less_IntInt',{'A':cursor,'B':'len.ReturnValue'}))
    arr(g,'item','Get',items);g.wire((cursor,'item.Index'));unpack(g,'mutation',MUTATION,'item.Item');unpack(g,'value',ENTRY,'mutation.Value')
    branch(g,'isnative',call(g,'kind',KML+':EqualEqual_IntInt',{'A':'value.Kind'},B=2))
    g.call('apply','self:SetVanilla');g.wire(('value.Key','apply.Key'),('mutation.Value','apply.Value'),('mutation.Present','apply.Present'))
    branch(g,'success',call(g,'ok',KML+':EqualEqual_IntInt',{'A':'apply.Status'},B=1))
    g.call('count','self:CountNative');g.wire(('mutation.Value','count.Value'),('mutation.Present','count.Present'))
    branch(g,'missing',call(g,'dormant',KML+':EqualEqual_IntInt',{'A':'apply.Status'},B=2))
    arr(g,'defer','Add',get(g,'NextRetry' if retry else 'RetryItems'));g.wire(('item.Item','defer.NewItem'))
    g.call('issue','self:ReportIssue');g.wire(('mutation.Value','issue.Value'),('apply.Status','issue.Code'))
    bump(g,'advance','WorkCursor');simple_result(g)
    g.chain('entry','loop','isnative')
    if not retry:
        g.call('drop','self:DropPendingNative');g.wire(('value.Key','drop.Key'));g.chain('isnative','drop','apply')
    else:g.chain('isnative','apply')
    g.chain('apply','success','count','advance','result')
    g.chain('isnative.else','advance');g.chain('success.else','missing','defer','advance');g.chain('missing.else','issue','advance')
    g.set('reset','WorkCursor','0')
    if retry:
        set_value(g,'copy','RetryItems',get(g,'NextRetry'));clear(g,'clear','NextRetry')
        g.call('schedule','self:ScheduleRetry')
        g.chain('loop.else','reset','copy','clear','schedule','result')
    else:
        g.set('phase','Phase','3');g.chain('loop.else','reset','phase','result')
    return g.function('RetryStep' if retry else 'NativeStep',outputs=[v('Continue','bool')])


def schedule_retry():
    g=Graph();arr(g,'len','Length',get(g,'RetryItems'))
    branch(g,'pending',call(g,'nonempty',KML+':Greater_IntInt',{'A':'len.ReturnValue'},B=0))
    branch(g,'allowed',call(g,'attempts',KML+':Less_IntInt',{'A':get(g,'RetryPass'),'B':get(g,'MaxRetries')}))
    deadline=call(g,'deadline',KML+':Add_DoubleDouble',{'A':clock(g,'now'),'B':get(g,'RetryInterval')})
    set_value(g,'settime','RetryAt',deadline);g.set('wait','Phase','7')
    g.set('dormant','Phase','9');g.set('reset','WorkCursor','0');g.call('finish','self:FinishWork')
    g.chain('entry','reset','pending','allowed','settime','wait');g.chain('allowed.else','dormant');g.chain('pending.else','finish')
    return g.function('ScheduleRetry')


def wait_retry():
    g=Graph();branch(g,'ready',call(g,'due',KML+':GreaterEqual_DoubleDouble',{'A':clock(g,'now'),'B':get(g,'RetryAt')}))
    g.call('refresh','self:RefreshActors');bump(g,'pass','RetryPass');g.set('phase','Phase','8');g.set('yes','local:OK','true');finish_bool(g,'Continue')
    g.chain('entry','ready','refresh','pass','phase','yes','result');g.chain('ready.else','result')
    return g.function('WaitRetry',outputs=[v('Continue','bool')],locals=[v('OK','bool','false')])


def start_asset():
    g=Graph();g.node('self','self');identity=call(g,'identity',KML+':MakeTransform',Scale='1,1,1')
    spawned=call(g,'spawn',GS+':BeginDeferredActorSpawnFromClass',{'WorldContextObject':'self.self','Owner':'self.self','SpawnTransform':identity},ActorClass=JOB,CollisionHandlingOverride='AlwaysSpawn')
    actor=call(g,'finish',GS+':FinishSpawningActor',{'Actor':spawned,'SpawnTransform':identity})
    g.node('cast','cast',**{'class':JOB});g.wire((actor,'cast.Object'))
    set_value(g,'remember','PendingJob','cast.AsBP Den Asset Job')
    call(g,'request',JOB+':Request',{'self':get(g,'PendingJob'),'Path':'entry.Path'})
    set_value(g,'ok','local:OK','request.Accepted');set_value(g,'time','RequestAt',clock(g,'now'));finish_bool(g)
    g.chain('entry','spawn','finish','cast','remember','request','ok','time','result');g.chain('cast.CastFailed','result')
    return g.function('StartAsset',inputs=[v('Path','string')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def release_asset():
    g=Graph();branch(g,'valid',validity(g,'check',get(g,'PendingJob')))
    call(g,'destroy',ACTOR+':K2_DestroyActor',{'self':get(g,'PendingJob')});g.set('forget','PendingJob')
    g.chain('entry','valid','destroy','forget');g.chain('valid.else','forget')
    return g.function('ReleaseAsset')


def advance_placed():
    g=Graph();g.call('release','self:ReleaseAsset');g.set('mesh','ReadyMesh');clear(g,'materials','ReadyMaterials')
    g.set('materialindex','MaterialCursor','0');bump(g,'advance','WorkCursor');g.set('phase','Phase','3')
    g.chain('entry','release','mesh','materials','materialindex','advance','phase')
    return g.function('AdvancePlaced')


def placed_step():
    g=Graph();arr(g,'len','Length',get(g,'WorkItems'))
    branch(g,'loop',call(g,'within',KML+':Less_IntInt',{'A':get(g,'WorkCursor'),'B':'len.ReturnValue'}))
    arr(g,'item','Get',get(g,'WorkItems'));g.wire((get(g,'WorkCursor'),'item.Index'))
    unpack(g,'mutation',MUTATION,'item.Item');unpack(g,'data',ENTRY,'mutation.Value')
    branch(g,'placed',call(g,'kind',KML+':EqualEqual_IntInt',{'A':'data.Kind'},B=0))
    validkind=combine(g,'skipkind',[call(g,'stored',KML+':EqualEqual_IntInt',{'A':'data.Kind'},B=1),call(g,'native',KML+':EqualEqual_IntInt',{'A':'data.Kind'},B=2)],True)
    branch(g,'skip',validkind);g.call('badkind','self:ReportIssue',Code=3);g.wire(('mutation.Value','badkind.Value'))
    branch(g,'present','mutation.Present');g.call('remove','self:RemovePlaced');g.wire(('data.Key','remove.Key'))
    set_value(g,'current','CurrentEntry','mutation.Value')
    g.call('load','self:StartAsset');g.wire(('data.Mesh','load.Path'));branch(g,'accepted','load.Accepted')
    g.set('phase','Phase','4');g.call('badmesh','self:ReportIssue',Code=4);g.wire(('mutation.Value','badmesh.Value'))
    g.call('next','self:AdvancePlaced');g.call('retry','self:ScheduleRetry');simple_result(g)
    g.chain('entry','loop','placed','present','current','load','accepted','phase','result')
    g.chain('accepted.else','badmesh','next','result');g.chain('present.else','remove','next');g.chain('placed.else','skip','next')
    g.chain('skip.else','badkind','next');g.chain('loop.else','retry','result')
    return g.function('PlacedStep',outputs=[v('Continue','bool')])


def wait_asset(material=False):
    g=Graph();branch(g,'valid',validity(g,'check',get(g,'PendingJob')))
    g.get('done',JOB+':Done');g.wire((get(g,'PendingJob'),'done.self'));branch(g,'donecheck','done.Done')
    g.get('loaded',JOB+':Result');g.wire((get(g,'PendingJob'),'loaded.self'))
    cls=MATERIAL if material else MESH
    g.node('cast','cast',**{'class':cls});g.wire(('loaded.Result','cast.Object'))
    pin='cast.AsMaterial Interface' if material else 'cast.AsStatic Mesh'
    if material:
        arr(g,'save','Add',get(g,'ReadyMaterials'));g.wire((pin,'save.NewItem'));bump(g,'advance','MaterialCursor')
    else:set_value(g,'save','ReadyMesh',pin)
    g.call('release','self:ReleaseAsset');g.set('phase','Phase','5')
    g.set('yes','local:OK','true');finish_bool(g,'Continue')
    elapsed=call(g,'elapsed',KML+':Subtract_DoubleDouble',{'A':clock(g,'now'),'B':get(g,'RequestAt')})
    branch(g,'expired',call(g,'timeout',KML+':GreaterEqual_DoubleDouble',{'A':elapsed,'B':get(g,'AssetTimeout')}))
    g.call('badasset','self:ReportIssue',Code=4);g.wire((get(g,'CurrentEntry'),'badasset.Value'))
    g.call('timedout','self:ReportIssue',Code=5);g.wire((get(g,'CurrentEntry'),'timedout.Value'))
    g.call('next','self:AdvancePlaced')
    g.chain('entry','valid','donecheck','cast','save',*(['advance'] if material else []),'release','phase','yes','result')
    g.chain('valid.else','badasset','next','yes');g.chain('cast.CastFailed','badasset')
    g.chain('donecheck.else','expired','timedout','next');g.chain('expired.else','result')
    return g.function('WaitMaterial' if material else 'WaitMesh',outputs=[v('Continue','bool')],locals=[v('OK','bool','false')])


def material_step():
    g=Graph();unpack(g,'data',ENTRY,get(g,'CurrentEntry'));arr(g,'len','Length','data.Materials')
    branch(g,'loop',call(g,'within',KML+':Less_IntInt',{'A':get(g,'MaterialCursor'),'B':'len.ReturnValue'}))
    arr(g,'path','Get','data.Materials');g.wire((get(g,'MaterialCursor'),'path.Index'))
    from runtime_store import STR
    branch(g,'default',call(g,'empty',STR+'EqualEqual_StrStr',{'A':'path.Item'},B=''))
    arr(g,'append','Add',get(g,'ReadyMaterials'));bump(g,'advance','MaterialCursor')
    g.call('load','self:StartAsset');g.wire(('path.Item','load.Path'));branch(g,'accepted','load.Accepted');g.set('phase','Phase','6')
    g.call('badmaterial','self:ReportIssue',Code=4);g.wire((get(g,'CurrentEntry'),'badmaterial.Value'))
    g.call('apply','self:SetPlaced');g.wire((get(g,'PreviewOnly'),'apply.Ghost'),(get(g,'CurrentEntry'),'apply.Value'),(get(g,'ReadyMesh'),'apply.LoadedMesh'),(get(g,'ReadyMaterials'),'apply.LoadedMaterials'))
    branch(g,'applied',call(g,'ok',KML+':EqualEqual_IntInt',{'A':'apply.Status'},B=1));bump(g,'count','PlacedCount')
    g.call('issue','self:ReportIssue');g.wire((get(g,'CurrentEntry'),'issue.Value'),('apply.Status','issue.Code'))
    g.call('next','self:AdvancePlaced');simple_result(g)
    g.chain('entry','loop','default','append','advance','result');g.chain('default.else','load','accepted','phase','result')
    g.chain('accepted.else','badmaterial','next','result');branch(g,'previewonly',get(g,'PreviewOnly'));call(g,'hidepreview',ACTOR+':SetActorHiddenInGame',{'self':'apply.Prop'},bNewHidden='true');g.chain('loop.else','apply','applied','count','previewonly','hidepreview','next');g.chain('previewonly.else','next');g.chain('applied.else','issue','next')
    return g.function('MaterialStep',outputs=[v('Continue','bool')])


def step():
    g=Graph();finish_bool(g,'Continue')
    methods=['CleanupStep','NativeStep','PlacedStep','WaitMesh','MaterialStep','WaitMaterial','WaitRetry','RetryStep','DormantStep','FingerprintStep']
    for n,method in enumerate(methods,1):
        branch(g,'phase'+str(n),call(g,'equal'+str(n),KML+':EqualEqual_IntInt',{'A':get(g,'Phase')},B=n))
        g.call('call'+str(n),'self:'+method);set_value(g,'set'+str(n),'local:OK','call'+str(n)+'.Continue')
        g.chain('phase'+str(n),'call'+str(n),'set'+str(n),'result')
        if n>1:g.chain('phase'+str(n-1)+'.else','phase'+str(n))
    g.call('finish','self:FinishWork');g.chain('entry','phase1');g.chain('phase10.else','finish','result')
    return g.function('StepWork',outputs=[v('Continue','bool')],locals=[v('OK','bool','false')])


def pump():
    g=Graph();branch(g,'busy',get(g,'Busy'));bump(g,'frame','Frames');set_value(g,'start','local:FrameStart',clock(g,'beginclock'))
    g.get('i','local:Steps');g.get('starttime','local:FrameStart');g.get('steptime','local:StepStart')
    bounded=call(g,'bounded',KML+':Less_IntInt',{'A':'i.Steps','B':get(g,'MaxSteps')})
    elapsed=call(g,'elapsed',KML+':Subtract_DoubleDouble',{'A':clock(g,'clock'),'B':'starttime.FrameStart'})
    budget=call(g,'budget',KML+':Less_DoubleDouble',{'A':elapsed,'B':get(g,'BudgetSeconds')})
    first=call(g,'first',KML+':EqualEqual_IntInt',{'A':'i.Steps'},B=0)
    branch(g,'loop',combine(g,'continue',[get(g,'Busy'),bounded,combine(g,'timeok',[first,budget],True)]))
    set_value(g,'stepstart','local:StepStart',clock(g,'stepclock'));g.call('step','self:StepWork')
    duration=call(g,'duration',KML+':Subtract_DoubleDouble',{'A':clock(g,'endclock'),'B':'steptime.StepStart'})
    set_value(g,'durationcopy','local:Duration',duration);g.get('d','local:Duration')
    total=call(g,'total',KML+':Add_DoubleDouble',{'A':get(g,'WorkSeconds'),'B':'d.Duration'});set_value(g,'work','WorkSeconds',total)
    slow=call(g,'max',KML+':FMax',{'A':get(g,'SlowestStep'),'B':'d.Duration'});set_value(g,'slowest','SlowestStep',slow)
    set_value(g,'advance','local:Steps',call(g,'next',KML+':Add_IntInt',{'A':'i.Steps'},B=1))
    branch(g,'more','step.Continue')
    g.chain('entry','busy','frame','start','loop','stepstart','step','durationcopy','work','slowest','advance','more','loop')
    return g.function('Pump',locals=[v('FrameStart','double'),v('StepStart','double'),v('Duration','double'),v('Steps','int','0')])


def specs():
    from runtime_refind import prepare as refind_prepare, consider as refind_consider, finish as refind_finish, scan as refind_scan, variables as refind_variables
    yield '16_ST_DenApplyIssue',struct(ISSUE,[v('Value','struct:'+ENTRY),v('Code','int')])
    g=Graph();g.node('tick','event',name='ReceiveTick');g.call('pump','self:Pump');g.chain('tick','pump')
    g.node('end','event',name='ReceiveEndPlay');g.call('cancel','self:CancelWork');g.call('forget','self:Forget');g.chain('end','cancel','forget')
    variables=[v('PreviewOnly','bool','false'),v('Busy','bool','false'),v('Phase','int','0'),v('Generation','int','0'),v('WorkItems','struct:'+MUTATION+'[]'),
        v('IndexMutations','struct:'+MUTATION+'[]'),v('IndexDeltaValid','bool'),v('IndexFromGeneration','int','-1'),v('IndexThroughGeneration','int','-1'),
        v('RetryItems','struct:'+MUTATION+'[]'),v('NextRetry','struct:'+MUTATION+'[]'),v('Issues','struct:'+ISSUE+'[]'),
        v('CurrentEntry','struct:'+ENTRY),v('PendingJob','object:'+JOB),v('ReadyMesh','object:'+MESH),v('ReadyMaterials','object:'+MATERIAL+'[]'),
        v('MaxSteps','int','32'),v('BudgetSeconds','double','0.004'),v('MaxRetries','int','8'),v('RetryInterval','double','1.5'),v('AssetTimeout','double','30')]
    variables += [v(n,'int','0') for n in ['WorkCursor','MaterialCursor','RetryPass','PlacedCount','HiddenCount','MovedCount','DormantCount','ErrorCount','Frames']]
    variables += [v(n,'double','0') for n in ['StartedAt','RequestAt','RetryAt','WorkSeconds','SlowestStep','TotalSeconds']]
    variables += refind_variables()
    yield '17_BP_DenApply',dict(kind='blueprint',path=APPLY,parent=WORLD,variables=variables,
        defaults={'PrimaryActorTick.bCanEverTick':'true','PrimaryActorTick.bStartWithTickEnabled':'true'},graph=g.spec(),
        functions=[cancel(),begin_batch(),begin_layout(),issue(),count_native(),consume_index_changes(),finish(),cleanup_step(),drop_retry(),native_step(),
                   schedule_retry(),wait_retry(),native_step(True),refind_prepare(),refind_consider(),refind_finish(),refind_scan(),start_asset(),release_asset(),advance_placed(),
                   placed_step(),wait_asset(),material_step(),wait_asset(True),step(),pump()])
