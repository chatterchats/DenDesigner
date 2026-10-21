"""Composition cards and isolated, all-parts thumbnail capture.

Snapshots carry a library revision key, never a live level object. A single
worker owns the temporary actors; no render can change the working layout.
"""
from graph import Graph, variable as v, KML, KSL, GS
from runtime import ROOT, LAYOUT, ENTRY, arr, unpack
from runtime_store import call, branch, combine, STR
from runtime_world import ACTOR, WORLD, PROP, SMC, PRIMITIVE, validity, set_value, finish_bool
from runtime_apply import APPLY, get, clock
from runtime_session import method, prop
from runtime_transform import copy_entry
from runtime_gizmo_controller import op
from runtime_catalog_ui import ITEM, number, prefix, join
from runtime_layout_ui import PRESETS, LIBRARY
from runtime_thumbnails import STUDIO, TEXTURE, CAPTURE_BASE


def decorate():
    g=Graph();method(g,'find',PRESETS,'FindPreset',get(g,'CompositionService'),{'Library':'entry.Library','Name':'entry.Name'})
    branch(g,'found',op(g,'exists','GreaterEqual_IntInt','find.Index',B=0))
    arr(g,'row','Get',prop(g,'rows',LIBRARY,'Entries','entry.Library'));g.wire(('find.Index','row.Index'));unpack(g,'value',ROOT+'ST_DenPresetValue','row.Item')
    call(g,'create',GS+':CreateSaveGameObject',SaveGameClass=LAYOUT);g.node('cast','cast',**{'class':LAYOUT});g.wire(('create.ReturnValue','cast.Object'))
    set_value(g,'entries',LAYOUT+':Entries','value.Entries');g.wire(('cast.AsBP Den Layout Save','entries.self'))
    g.call('validate','self:ValidateComposition');g.wire(('cast.AsBP Den Layout Save','validate.Document'));branch(g,'valid','validate.Accepted')
    key=prefix(g,'key','/ZComDen/CompositionThumbs/v1_',join(g,'identity',prop(g,'revision',LIBRARY,'ContentID','entry.Library'),prefix(g,'index','_',number(g,'indexstr','find.Index'))))
    key=call(g,'objectkey',STR+'Concat_StrStr',{'A':key},B='.Composition')
    set_value(g,'path',ITEM+':AssetPath',key);g.wire(('entry.Item','path.self'))
    set_value(g,'document',ITEM+':ThumbnailDocument','cast.AsBP Den Layout Save');g.wire(('entry.Item','document.self'))
    arr(g,'count','Length','value.Entries');suffix=call(g,'suffix',KML+':SelectString',{'bPickA':op(g,'single','EqualEqual_IntInt','count.ReturnValue',B=1)},A=' part',B=' parts')
    detail=join(g,'caption',number(g,'countstr','count.ReturnValue'),suffix);set_value(g,'detail',ITEM+':Detail',detail);g.wire(('entry.Item','detail.self'))
    g.chain('entry','find','found','create','cast','entries','validate','valid','path','document','detail')
    return g.function('DecorateCompositionCard',inputs=[v('Item','object:'+ITEM),v('Library','object:'+LIBRARY),v('Name','string')])


def request():
    g=Graph();branch(g,'document',validity(g,'valid','entry.Document'));g.call('request','self:Request');g.wire(('entry.Path','request.Path'),('request.Texture','result.Texture'),('request.Status','result.Status'))
    arr(g,'index','Find',get(g,'CachePaths'));g.wire(('entry.Path','index.ItemToFind'));branch(g,'queued',combine(g,'pending',[op(g,'found','GreaterEqual_IntInt','index.ReturnValue',B=0),op(g,'pendingstatus','EqualEqual_IntInt','request.Status',B=0)]))
    arr(g,'keep','Set',get(g,'CacheDocuments'));g.wire(('index.ReturnValue','keep.Index'),('entry.Document','keep.Item'))
    g.chain('entry','document','request','queued','keep','result');g.chain('queued.else','result');g.chain('document.else','result')
    return g.function('RequestComposition',inputs=[v('Path','string'),v('Document','object:'+LAYOUT)],outputs=[v('Texture','object:'+TEXTURE),v('Status','int')])


def release():
    g=Graph();branch(g,'valid',validity(g,'alive',get(g,'CompositionRenderer')))
    method(g,'cancel',APPLY,'CancelWork',get(g,'CompositionRenderer'));method(g,'clear',WORLD,'Clear',get(g,'CompositionRenderer'));call(g,'destroy',ACTOR+':K2_DestroyActor',{'self':get(g,'CompositionRenderer')});g.set('release','CompositionRenderer')
    g.chain('entry','valid','cancel','clear','destroy','release');g.chain('valid.else','release');return g.function('ReleaseCompositionRenderer')


def begin():
    from runtime_thumbnail_queue import spawn
    g=Graph();g.node('self','self');spawn(g,'renderer',APPLY,'CompositionRenderer','AsBP Den Apply')
    g.set('ghost',APPLY+':PreviewOnly','true');g.wire((get(g,'CompositionRenderer'),'ghost.self'))
    method(g,'begin',APPLY,'BeginLayout',get(g,'CompositionRenderer'),{'Document':'entry.Document'});branch(g,'accepted','begin.Accepted');g.set('phase','Phase','4');set_value(g,'started','RequestAt',clock(g,'now'))
    g.call('fail','self:FinishThumbnail');g.chain('entry','rendererspawn');g.chain('renderersave','ghost','begin','accepted','phase','started');g.chain('renderercast.CastFailed','fail');g.chain('accepted.else','fail')
    return g.function('BeginCompositionThumbnail',inputs=[v('Document','object:'+LAYOUT)])


def poll():
    g=Graph();branch(g,'valid',validity(g,'renderer',get(g,'CompositionRenderer')));branch(g,'busy',prop(g,'busyvalue',APPLY,'Busy',get(g,'CompositionRenderer')))
    branch(g,'timeout',op(g,'late','Greater_DoubleDouble',op(g,'elapsed','Subtract_DoubleDouble',clock(g,'now'),get(g,'RequestAt')),B=90))
    branch(g,'complete',op(g,'noerrors','EqualEqual_IntInt',prop(g,'errors',APPLY,'ErrorCount',get(g,'CompositionRenderer')),B=0))
    method(g,'prepare',STUDIO,'PrepareComposition',get(g,'Studio'),{'Actors':prop(g,'actors',WORLD,'Placed',get(g,'CompositionRenderer')),'Path':get(g,'CurrentPath')});branch(g,'ready','prepare.Ready');g.set('phase','Phase','2')
    g.call('fail','self:FinishThumbnail');g.chain('entry','valid','busy','timeout','fail');g.chain('busy.else','complete','prepare','ready','phase')
    for pin in ['valid.else','complete.else','ready.else']:g.chain(pin,'fail')
    return g.function('PollCompositionThumbnail')


def prepare():
    # All actors are hidden/collisionless until loading finishes. Shift their
    # value transforms to the studio, then fit the union of transformed bounds.
    g=Graph();g.node('self','self');g.set('reset','Prepared','false');call(g,'clearshow',CAPTURE_BASE+':ClearShowOnlyComponents',{'self':get(g,'Capture')})
    call(g,'clearmesh',SMC+':SetStaticMesh',{'self':get(g,'Mesh')})
    arr(g,'count','Length','entry.Actors');branch(g,'bounded',combine(g,'size',[op(g,'nonempty','Greater_IntInt','count.ReturnValue',B=0),op(g,'limit','LessEqual_IntInt','count.ReturnValue',B=128)]))
    g.get('i','local:Cursor');branch(g,'more',op(g,'within','Less_IntInt','i.Cursor','count.ReturnValue'));arr(g,'actor','Get','entry.Actors');g.wire(('i.Cursor','actor.Index'));branch(g,'alive',validity(g,'actorvalid','actor.Item'))
    current=prop(g,'current',PROP,'Current','actor.Item');unpack(g,'value',ENTRY,current);origin=call(g,'origin',ACTOR+':K2_GetActorLocation',{'self':'self.self'})
    shifted=copy_entry(g,'shifted',current,{'Position':op(g,'position','Add_VectorVector','value.Position',origin)})
    method(g,'move',PROP,'PreviewTransform','actor.Item',{'Value':shifted});branch(g,'moved','move.Accepted');component=prop(g,'mesh',PROP,'Mesh','actor.Item')
    call(g,'channels',PRIMITIVE+':SetLightingChannels',{'self':component},bChannel0='false',bChannel1='true',bChannel2='false')
    call(g,'outline',PRIMITIVE+':SetRenderCustomDepth',{'self':component},bValue='false');call(g,'show',ACTOR+':SetActorHiddenInGame',{'self':'actor.Item'},bNewHidden='false')
    call(g,'showonly',CAPTURE_BASE+':ShowOnlyComponent',{'self':get(g,'Capture'),'InComponent':component})
    call(g,'bounds',KSL+':GetComponentBounds',{'Component':component})
    center=op(g,'relative','Subtract_VectorVector','bounds.Origin',origin)
    for name,pin in [('low',op(g,'low','Subtract_VectorVector',center,'bounds.BoxExtent')),('high',op(g,'high','Add_VectorVector',center,'bounds.BoxExtent'))]:call(g,name+'parts',KML+':BreakVector',{'InVec':pin})
    previous='showonly'
    for axis in 'XYZ':
        g.get('min'+axis,'local:Min'+axis);g.get('max'+axis,'local:Max'+axis)
        set_value(g,'setmin'+axis,'local:Min'+axis,op(g,'minvalue'+axis,'FMin','min'+axis+'.Min'+axis,'lowparts.'+axis));set_value(g,'setmax'+axis,'local:Max'+axis,op(g,'maxvalue'+axis,'FMax','max'+axis+'.Max'+axis,'highparts.'+axis));g.chain(previous,'setmin'+axis,'setmax'+axis);previous='setmax'+axis
    set_value(g,'next','local:Cursor',op(g,'advance','Add_IntInt','i.Cursor',B=1));g.chain(previous,'next','more')
    midpoint=call(g,'midpoint',KML+':MakeVector',{a:op(g,'half'+a,'Multiply_DoubleDouble',op(g,'sum'+a,'Add_DoubleDouble','min'+a+'.Min'+a,'max'+a+'.Max'+a),B=.5) for a in 'XYZ'})
    extent=call(g,'extent',KML+':MakeVector',{a:op(g,'extent'+a,'Multiply_DoubleDouble',op(g,'diff'+a,'Subtract_DoubleDouble','max'+a+'.Max'+a,'min'+a+'.Min'+a),B=.5) for a in 'XYZ'})
    set_value(g,'center','CompositionCenter',midpoint);set_value(g,'extentout','CompositionExtent',extent);set_value(g,'path','MeshPath','entry.Path')
    g.set('yes','local:OK','true');finish_bool(g,'Ready')
    g.chain('entry','reset','clearshow','clearmesh','bounded','more','alive','move','moved','channels','outline','show','showonly');g.chain('more.else','center','extentout','path','yes','result')
    for pin in ['bounded.else','alive.else','moved.else']:g.chain(pin,'result')
    return g.function('StageComposition',inputs=[v('Actors','object:'+PROP+'[]'),v('Path','string')],outputs=[v('Ready','bool')],locals=[v('Cursor','int','0'),v('OK','bool','false')]+[v(p+a,'double','1e20' if p=='Min' else '-1e20') for p in ['Min','Max'] for a in 'XYZ'])


def prepare_frame():
    g=Graph();g.call('stage','self:StageComposition');g.wire(('entry.Actors','stage.Actors'),('entry.Path','stage.Path'));branch(g,'ready','stage.Ready')
    g.call('frame','self:ConfigureFrame');g.wire((get(g,'CompositionCenter'),'frame.Center'),(get(g,'CompositionExtent'),'frame.Extent'),(call(g,'radius',KML+':VSize',{'A':get(g,'CompositionExtent')}),'frame.Radius'),('frame.Ready','result.Ready'))
    g.chain('entry','stage','ready','frame','result');g.chain('ready.else','result')
    return g.function('PrepareComposition',inputs=[v('Actors','object:'+PROP+'[]'),v('Path','string')],outputs=[v('Ready','bool')])
