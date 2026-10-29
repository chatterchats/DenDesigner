"""Bounded native thumbnail cache and a single asynchronous rendering worker."""
from graph import Graph, variable as v, KML, GS
from runtime import ROOT, LAYOUT, arr
from runtime_store import call, branch, combine, STR
from runtime_world import ACTOR, MESH, validity, set_value
from runtime_assets import JOB, valid_asset_path
from runtime_apply import APPLY, get, clock, clear
from runtime_session import prop, method
from runtime_gizmo_controller import op
from runtime_thumbnails import STUDIO, TEXTURE, AT

QUEUE=ROOT+'BP_DenThumbnails'
FIELDS=['CachePaths','CacheTextures','CacheStates','CacheDocuments']


def spawn(g,name,cls,member,castpin,location='0,0,0'):
    xf=call(g,name+'xf',KML+':MakeTransform',Location=location,Scale='1,1,1')
    pending=call(g,name+'spawn',GS+':BeginDeferredActorSpawnFromClass',{'WorldContextObject':'self.self','Owner':'self.self','SpawnTransform':xf},ActorClass=cls,CollisionHandlingOverride='AlwaysSpawn')
    actor=call(g,name+'finish',GS+':FinishSpawningActor',{'Actor':pending,'SpawnTransform':xf})
    g.node(name+'cast','cast',**{'class':cls});g.wire((actor,name+'cast.Object'));set_value(g,name+'save',member,name+'cast.'+castpin);g.chain(name+'spawn',name+'finish',name+'cast',name+'save')


def remove(g,name,index):
    for i,field in enumerate(FIELDS):
        arr(g,name+str(i),'Remove',get(g,field));g.wire((index,name+str(i)+'.IndexToRemove'))
        if i:g.chain(name+str(i-1),name+str(i))


def request():
    g=Graph();g.call('valid','self:ValidAssetPath');g.wire(('entry.Path','valid.Path'));branch(g,'validpath','valid.Valid')
    arr(g,'index','Find',get(g,'CachePaths'));g.wire(('entry.Path','index.ItemToFind'));branch(g,'cached',op(g,'found','GreaterEqual_IntInt','index.ReturnValue',B=0))
    for name,field in [('texture','CacheTextures'),('state','CacheStates')]:arr(g,name,'Get',get(g,field));g.wire(('index.ReturnValue',name+'.Index'))
    set_value(g,'textureout','local:ResultTexture','texture.Item');set_value(g,'stateout','local:ResultState','state.Item')
    arr(g,'count','Length',get(g,'CachePaths'));branch(g,'full',op(g,'limit','GreaterEqual_IntInt','count.ReturnValue',B=96))
    # Evict a completed FIFO slot; pending requests are never evicted underneath the worker.
    g.get('i','local:EvictIndex');branch(g,'more',op(g,'remaining','Less_IntInt','i.EvictIndex','count.ReturnValue'));arr(g,'candidate','Get',get(g,'CacheStates'));g.wire(('i.EvictIndex','candidate.Index'));branch(g,'done',op(g,'complete','Greater_IntInt','candidate.Item',B=0));remove(g,'remove','i.EvictIndex')
    set_value(g,'advance','local:EvictIndex',op(g,'next','Add_IntInt','i.EvictIndex',B=1))
    previous='remove3'
    for name,field,pin in [('path','CachePaths','entry.Path'),('null','CacheTextures',None),('zero','CacheStates',None),('document','CacheDocuments',None),('queue','PendingPaths','entry.Path')]:
        arr(g,name+'add','Add',get(g,field))
        if pin:g.wire((pin,name+'add.NewItem'))
        g.chain(previous,name+'add');previous=name+'add'
    g.set('pending','local:ResultState','0');g.get('outtexture','local:ResultTexture');g.get('outstate','local:ResultState');g.wire(('outtexture.ResultTexture','result.Texture'),('outstate.ResultState','result.Status'))
    g.chain('entry','valid','validpath','cached','textureout','stateout','result');g.chain('cached.else','full','more','done','remove0');g.chain('done.else','advance','more');g.chain('full.else','pathadd');g.chain(previous,'pending','result');g.chain('more.else','pending');g.chain('validpath.else','result')
    return g.function('Request',inputs=[v('Path','string')],outputs=[v('Texture','object:'+TEXTURE),v('Status','int')],locals=[v('ResultTexture','object:'+TEXTURE),v('ResultState','int','2'),v('EvictIndex','int','0')])


def release_job():
    g=Graph();branch(g,'valid',validity(g,'alive',get(g,'Job')));call(g,'destroy',ACTOR+':K2_DestroyActor',{'self':get(g,'Job')});g.set('clear','Job');g.chain('entry','valid','destroy','clear');g.chain('valid.else','clear');return g.function('ReleaseJob')


def release_studio():
    g=Graph();branch(g,'valid',validity(g,'alive',get(g,'Studio')));call(g,'destroy',ACTOR+':K2_DestroyActor',{'self':get(g,'Studio')});g.set('clear','Studio');g.chain('entry','valid','destroy','clear');g.chain('valid.else','clear');return g.function('ReleaseCaptureStudio')


def finish():
    g=Graph();arr(g,'index','Find',get(g,'CachePaths'));g.wire((get(g,'CurrentPath'),'index.ItemToFind'));branch(g,'found',op(g,'exists','GreaterEqual_IntInt','index.ReturnValue',B=0))
    arr(g,'texture','Set',get(g,'CacheTextures'));g.wire(('index.ReturnValue','texture.Index'),('entry.Texture','texture.Item'))
    state=call(g,'state',KML+':SelectInt',{'bPickA':validity(g,'texturevalid','entry.Texture')},A=1,B=2);arr(g,'status','Set',get(g,'CacheStates'));g.wire(('index.ReturnValue','status.Index'),(state,'status.Item'))
    g.call('release','self:ReleaseJob');g.call('composition','self:ReleaseCompositionRenderer');g.set('phase','Phase','0');g.set('path','CurrentPath','');set_value(g,'idle','IdleAt',clock(g,'now'));set_value(g,'throttle','NextAt',op(g,'nexttime','Add_DoubleDouble',get(g,'IdleAt'),B=.05))
    g.chain('entry','found','texture','status','release','composition','phase','path','idle','throttle');g.chain('found.else','release');return g.function('FinishThumbnail',inputs=[v('Texture','object:'+TEXTURE)])


def cancel():
    g=Graph();g.call('job','self:ReleaseJob');g.call('composition','self:ReleaseCompositionRenderer');g.set('phase','Phase','0');g.set('path','CurrentPath','');clear(g,'queue','PendingPaths')
    arr(g,'count','Length',get(g,'CachePaths'));set_value(g,'start','local:CancelIndex',op(g,'last','Subtract_IntInt','count.ReturnValue',B=1));g.get('i','local:CancelIndex');branch(g,'more',op(g,'nonnegative','GreaterEqual_IntInt','i.CancelIndex',B=0));arr(g,'state','Get',get(g,'CacheStates'));g.wire(('i.CancelIndex','state.Index'));branch(g,'pending',op(g,'zero','EqualEqual_IntInt','state.Item',B=0));remove(g,'remove','i.CancelIndex');set_value(g,'next','local:CancelIndex',op(g,'decrement','Subtract_IntInt','i.CancelIndex',B=1))
    set_value(g,'idle','IdleAt',clock(g,'now'));g.chain('entry','job','composition','phase','path','queue','start','more','pending','remove0');g.chain('remove3','next','more');g.chain('pending.else','next');g.chain('more.else','idle');return g.function('CancelPending',locals=[v('CancelIndex','int','0')])


def begin():
    g=Graph();g.node('self','self');arr(g,'count','Length',get(g,'PendingPaths'));branch(g,'pending',op(g,'any','Greater_IntInt','count.ReturnValue',B=0));branch(g,'throttle',op(g,'time','GreaterEqual_DoubleDouble',clock(g,'now'),get(g,'NextAt')))
    arr(g,'first','Get',get(g,'PendingPaths'),Index=0);set_value(g,'path','CurrentPath','first.Item');arr(g,'pop','Remove',get(g,'PendingPaths'),IndexToRemove=0)
    branch(g,'studio',validity(g,'validstudio',get(g,'Studio')));spawn(g,'studio',STUDIO,'Studio','AsBP Den Thumbnail Studio',AT)
    method(g,'cache',STUDIO,'ReadCached',get(g,'Studio'),{'Path':get(g,'CurrentPath')});branch(g,'hit',validity(g,'cachevalid','cache.Texture'));g.call('finishcache','self:FinishThumbnail');g.wire(('cache.Texture','finishcache.Texture'))
    arr(g,'cacheindex','Find',get(g,'CachePaths'));g.wire((get(g,'CurrentPath'),'cacheindex.ItemToFind'));arr(g,'document','Get',get(g,'CacheDocuments'));g.wire(('cacheindex.ReturnValue','document.Index'));branch(g,'composition',validity(g,'documentvalid','document.Item'));g.call('begincomposition','self:BeginCompositionThumbnail');g.wire(('document.Item','begincomposition.Document'))
    branch(g,'enabled',get(g,'Enabled'));spawn(g,'job',JOB,'Job','AsBP Den Asset Job');method(g,'request',JOB,'Request',get(g,'Job'),{'Path':get(g,'CurrentPath')});branch(g,'accepted','request.Accepted');g.set('phase','Phase','1');set_value(g,'started','RequestAt',clock(g,'starttime'))
    g.call('fail','self:FinishThumbnail');g.chain('entry','pending','throttle','path','pop','studio','cache','hit','finishcache');g.chain('studio.else','studiospawn');g.chain('studiosave','cache');g.chain('hit.else','enabled','composition','begincomposition');g.chain('composition.else','jobspawn');g.chain('jobsave','request','accepted','phase','started')
    for pin in ['enabled.else','studiocast.CastFailed','jobcast.CastFailed','accepted.else']:g.chain(pin,'fail')
    branch(g,'idle',op(g,'elapsed','Greater_DoubleDouble',op(g,'duration','Subtract_DoubleDouble',clock(g,'idlenow'),get(g,'IdleAt')),B=3));g.call('release','self:ReleaseCaptureStudio');g.chain('pending.else','idle','release')
    return g.function('BeginNext')


def poll():
    g=Graph();branch(g,'composition',op(g,'four','EqualEqual_IntInt',get(g,'Phase'),B=4));g.call('pollcomposition','self:PollCompositionThumbnail');branch(g,'idle',op(g,'zero','EqualEqual_IntInt',get(g,'Phase'),B=0));g.call('next','self:BeginNext')
    branch(g,'loading',op(g,'one','EqualEqual_IntInt',get(g,'Phase'),B=1));branch(g,'job',validity(g,'jobvalid',get(g,'Job')));branch(g,'done',prop(g,'donevalue',JOB,'Done',get(g,'Job')))
    g.node('mesh','cast',**{'class':MESH});g.wire((prop(g,'loaded',JOB,'Result',get(g,'Job')),'mesh.Object'));method(g,'prepare',STUDIO,'Prepare',get(g,'Studio'),{'Mesh':'mesh.AsStatic Mesh'});branch(g,'ready','prepare.Ready');g.call('release','self:ReleaseJob');g.set('capturephase','Phase','2')
    branch(g,'timeout',op(g,'late','Greater_DoubleDouble',op(g,'duration','Subtract_DoubleDouble',clock(g,'now'),get(g,'RequestAt')),B=30));g.call('fail','self:FinishThumbnail')
    branch(g,'capture',op(g,'two','EqualEqual_IntInt',get(g,'Phase'),B=2));method(g,'render',STUDIO,'CaptureFrame',get(g,'Studio'));g.set('exportphase','Phase','3')
    method(g,'export',STUDIO,'WriteCache',get(g,'Studio'));g.call('finish','self:FinishThumbnail');g.wire(('export.Texture','finish.Texture'))
    # Compositions also get the 512 px HoloNet preview and a remembered footprint.
    branch(g,'composition4share',call(g,'iscomposition',STR+'StartsWith',{'SourceString':get(g,'CurrentPath')},InPrefix='/ZComDen/CompositionThumbs/',SearchCase='CaseSensitive'))
    method(g,'share',STUDIO,'WriteSharePreview',get(g,'Studio'));g.call('footprint','self:RememberFootprint')
    g.chain('entry','composition','pollcomposition');g.chain('composition.else','idle','next');g.chain('idle.else','loading','job','done','mesh','prepare','ready','release','capturephase');g.chain('done.else','timeout','fail')
    for pin in ['job.else','mesh.CastFailed','ready.else']:g.chain(pin,'fail')
    g.chain('loading.else','capture','render','exportphase');g.chain('capture.else','export','composition4share','share','footprint','finish');g.chain('composition4share.else','finish');return g.function('PumpThumbnails')


def remember_footprint():
    """Footprint (bounding box size, cm) of the composition just rendered, keyed
    by its card file name (Composition_<hash>.png), for HoloNet sharing."""
    g=Graph();method(g,'path',STUDIO,'CachePath',get(g,'Studio'),{'Path':get(g,'CurrentPath')})
    size=op(g,'size','Multiply_VectorFloat',prop(g,'extent',STUDIO,'CompositionExtent',get(g,'Studio')),B=2)
    arr(g,'find','Find',get(g,'FootprintNames'));g.wire(('path.Name','find.ItemToFind'));branch(g,'known',op(g,'found','GreaterEqual_IntInt','find.ReturnValue',B=0))
    arr(g,'update','Set',get(g,'FootprintSizes'));g.wire(('find.ReturnValue','update.Index'),(size,'update.Item'))
    arr(g,'addname','Add',get(g,'FootprintNames'));g.wire(('path.Name','addname.NewItem'));arr(g,'addsize','Add',get(g,'FootprintSizes'));g.wire((size,'addsize.NewItem'))
    g.chain('entry','path','find','known','update');g.chain('known.else','addname','addsize')
    return g.function('RememberFootprint')


def footprint():
    g=Graph();arr(g,'find','Find',get(g,'FootprintNames'));g.wire(('entry.Name','find.ItemToFind'));branch(g,'known',op(g,'found','GreaterEqual_IntInt','find.ReturnValue',B=0))
    arr(g,'read','Get',get(g,'FootprintSizes'));g.wire(('find.ReturnValue','read.Index'));set_value(g,'keep','local:Size','read.Item')
    g.set('yes','local:Found','true');g.get('foundvalue','local:Found');g.get('sizevalue','local:Size');g.wire(('foundvalue.Found','result.Found'),('sizevalue.Size','result.Size'))
    g.chain('entry','known','keep','yes','result');g.chain('known.else','result')
    return g.function('CompositionFootprint',inputs=[v('Name','string')],outputs=[v('Found','bool'),v('Size','vector')],locals=[v('Found','bool','false'),v('Size','vector')])


def spec():
    from runtime_composition_thumbnails import request as composition_request,release as composition_release,begin as composition_begin,poll as composition_poll
    g=Graph();g.node('tick','event',name='ReceiveTick');g.call('pump','self:PumpThumbnails');g.chain('tick','pump');g.node('end','event',name='ReceiveEndPlay');g.call('cancel','self:CancelPending');g.call('release','self:ReleaseCaptureStudio');g.chain('end','cancel','release')
    return dict(kind='blueprint',path=QUEUE,parent=ACTOR,defaults={'PrimaryActorTick.bCanEverTick':'true','PrimaryActorTick.bStartWithTickEnabled':'true'},
        variables=[v('CacheDocuments','object:'+LAYOUT+'[]'),v('CompositionRenderer','object:'+APPLY),v('CachePaths','string[]'),v('CacheTextures','object:'+TEXTURE+'[]'),v('CacheStates','int[]'),v('PendingPaths','string[]'),v('CurrentPath','string'),v('Phase','int'),v('Job','object:'+JOB),v('Studio','object:'+STUDIO),v('RequestAt','double'),v('IdleAt','double'),v('NextAt','double'),v('Enabled','bool','true'),v('FootprintNames','string[]'),v('FootprintSizes','vector[]')],graph=g.spec(),functions=[composition_request(),composition_release(),composition_begin(),composition_poll(),valid_asset_path(),request(),release_job(),release_studio(),finish(),cancel(),begin(),poll(),remember_footprint(),footprint()])
