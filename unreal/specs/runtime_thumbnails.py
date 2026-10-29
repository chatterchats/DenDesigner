"""Pak-only thumbnail studio and stable cache utilities.

The capture actor is isolated from layout data. Existing ASCII game-asset cache
filenames derive from stable mesh paths; native references own textures/render targets.
"""
import math as pymath
from graph import Graph, variable as v, KML, KSL, GS
from runtime import ROOT, arr
from runtime_store import call, branch, combine, STR
from runtime_world import ACTOR, SCENE, SMC, MESH, validity, set_value, finish_bool
from runtime_apply import get
from runtime_assets import valid_asset_path
from runtime_gizmo_controller import op, neg

STUDIO=ROOT+'BP_DenThumbnailStudio'
RENDER='/Script/Engine.KismetRenderingLibrary'
PATHS='/Script/Engine.BlueprintPathsLibrary'
TARGET='/Script/Engine.TextureRenderTarget2D'
TEXTURE='/Script/Engine.Texture2D'
CAPTURE='/Script/Engine.SceneCaptureComponent2D'
CAPTURE_BASE='/Script/Engine.SceneCaptureComponent'
LIGHT='/Script/Engine.PointLightComponent'
AT='-522700,13000,28800'
VIEW=(.75,-.55,.45)


def distance():
    g=Graph();call(g,'parts',KML+':BreakVector',{'InVec':'entry.Extent'})
    norm=lambda v:tuple(x/pymath.sqrt(sum(y*y for y in v)) for x in v)
    forward=norm(tuple(-x for x in VIEW));right=norm((-forward[1],forward[0],0));up=(right[1]*forward[2]-right[2]*forward[1],right[2]*forward[0]-right[0]*forward[2],right[0]*forward[1]-right[1]*forward[0])
    def dot(name,corner,axis):
        vec=call(g,name+'axis',KML+':MakeVector',X=axis[0],Y=axis[1],Z=axis[2]);return op(g,name,'Dot_VectorVector',corner,vec)
    best=None
    for i,(x,y,z) in enumerate(( (x,y,z) for x in [-1,1] for y in [-1,1] for z in [-1,1])):
        name='corner'+str(i)
        corner=call(g,name,KML+':MakeVector',{axis:op(g,name+axis,'Multiply_DoubleDouble','parts.'+axis,B=sign) for axis,sign in zip('XYZ',(x,y,z))})
        side=op(g,name+'side','FMax',op(g,name+'absR','Abs',dot(name+'right',corner,right)),op(g,name+'absU','Abs',dot(name+'up',corner,up)))
        need=op(g,name+'need','Subtract_DoubleDouble',op(g,name+'tan','Divide_DoubleDouble',side,B=pymath.tan(pymath.radians(15))),dot(name+'forward',corner,forward))
        best=op(g,name+'max','FMax',need,best) if best else op(g,name+'max','FMax',need,B=1)
    result=op(g,'margin','Multiply_DoubleDouble',best,B=1.08);g.wire((result,'result.Distance'));g.chain('entry','result')
    return g.function('FrameDistance',inputs=[v('Extent','vector')],outputs=[v('Distance','double')])


def filename():
    g=Graph();g.call('validate','self:ValidAssetPath');g.wire(('entry.Path','validate.Path'));branch(g,'valid','validate.Valid')
    g.get('cursor','local:CharacterIndex');g.get('hash','local:HashValue');length=call(g,'length',STR+'Len',{'S':'entry.Path'});branch(g,'more',op(g,'within','Less_IntInt','cursor.CharacterIndex',length))
    char=call(g,'character',STR+'GetCharacterAsNumber',{'SourceString':'entry.Path','Index':'cursor.CharacterIndex'})
    updated=op(g,'hashmod','Percent_Int64Int64',op(g,'hashadd','Add_Int64Int64',op(g,'hashmultiply','Multiply_Int64Int64','hash.HashValue',B=33),char),B=4294967296)
    set_value(g,'updatehash','local:HashValue',updated);set_value(g,'nextchar','local:CharacterIndex',op(g,'next','Add_IntInt','cursor.CharacterIndex',B=1))
    call(g,'split',STR+'Split',{'SourceString':'entry.Path'},InStr='.',SearchCase='CaseSensitive',SearchDir='FromEnd')
    g.set('reset','local:CharacterIndex','0');g.get('name','local:SafeName');name_length=call(g,'namelength',STR+'Len',{'S':'split.RightS'});branch(g,'namemore',op(g,'namewithin','Less_IntInt','cursor.CharacterIndex',name_length))
    code=call(g,'namechar',STR+'GetCharacterAsNumber',{'SourceString':'split.RightS','Index':'cursor.CharacterIndex'})
    ranges=[combine(g,'range'+str(i),[op(g,'lo'+str(i),'GreaterEqual_IntInt',code,B=a),op(g,'hi'+str(i),'LessEqual_IntInt',code,B=b)]) for i,(a,b) in enumerate([(48,57),(65,90),(97,122)])]
    allowed=combine(g,'allowed',ranges+[op(g,'underscore','EqualEqual_IntInt',code,B=95),op(g,'dash','EqualEqual_IntInt',code,B=45)],True)
    substring=call(g,'substring',STR+'GetSubstring',{'SourceString':'split.RightS','StartIndex':'cursor.CharacterIndex'},Length=1)
    sanitized=call(g,'sanitize',KML+':SelectString',{'A':substring,'bPickA':allowed},B='_')
    name=call(g,'appendname',STR+'Concat_StrStr',{'A':'name.SafeName','B':sanitized});set_value(g,'savename','local:SafeName',name);set_value(g,'namenext','local:CharacterIndex',op(g,'nameincrement','Add_IntInt','cursor.CharacterIndex',B=1))
    g.get('hex','local:HexValue');g.get('digits','local:HexDigits');branch(g,'hexmore',op(g,'hexwithin','Less_IntInt','digits.HexDigits',B=8))
    digit=op(g,'mod','Percent_Int64Int64','hash.HashValue',B=16);symbol=call(g,'symbol',STR+'GetSubstring',{'StartIndex':digit},SourceString='0123456789abcdef',Length=1)
    value=call(g,'appendhex',STR+'Concat_StrStr',{'A':symbol,'B':'hex.HexValue'});set_value(g,'savehex','local:HexValue',value);set_value(g,'divide','local:HashValue',op(g,'quotient','Divide_Int64Int64','hash.HashValue',B=16));set_value(g,'digitnext','local:HexDigits',op(g,'nextdigit','Add_IntInt','digits.HexDigits',B=1))
    prefix=call(g,'prefix',STR+'Concat_StrStr',{'A':'name.SafeName'},B='_');body=call(g,'body',STR+'Concat_StrStr',{'A':prefix,'B':'hex.HexValue'});file=call(g,'suffix',STR+'Concat_StrStr',{'A':body},B='.png');set_value(g,'output','local:CacheName',file);g.get('out','local:CacheName');g.wire(('out.CacheName','result.FileName'))
    g.chain('entry','validate','valid','more','updatehash','nextchar','more');g.chain('more.else','reset','namemore','savename','namenext','namemore');g.chain('namemore.else','hexmore','savehex','divide','digitnext','hexmore');g.chain('hexmore.else','output','result');g.chain('valid.else','result')
    return g.function('CacheFileName',inputs=[v('Path','string')],outputs=[v('FileName','string')],locals=[v('CharacterIndex','int','0'),v('HashValue','int64','5381'),v('SafeName','string'),v('HexValue','string'),v('HexDigits','int','0'),v('CacheName','string')])


def cache_path():
    g=Graph();saved=call(g,'saved',KSL+':GetProjectSavedDirectory');directory=call(g,'directory',STR+'Concat_StrStr',{'A':saved},B='ZComDen/thumbs/');g.call('file','self:CacheFileName');g.wire(('entry.Path','file.Path'))
    full=call(g,'full',STR+'Concat_StrStr',{'A':directory,'B':'file.FileName'});g.wire((directory,'result.Directory'),('file.FileName','result.Name'),(full,'result.FullPath'));g.chain('entry','file','result')
    return g.function('CachePath',inputs=[v('Path','string')],outputs=[v('Directory','string'),v('Name','string'),v('FullPath','string')])


def read_cache():
    g=Graph();g.node('self','self');g.call('path','self:CachePath');g.wire(('entry.Path','path.Path'));branch(g,'valid',call(g,'nonempty',STR+'NotEqual_StrStr',{'A':'path.Name'},B=''))
    exists=call(g,'exists',PATHS+':FileExists',{'InPath':'path.FullPath'});branch(g,'available',exists)
    texture=call(g,'import',RENDER+':ImportFileAsTexture2D',{'WorldContextObject':'self.self','Filename':'path.FullPath'});set_value(g,'save','local:CachedTexture',texture);g.get('texture','local:CachedTexture');g.wire(('texture.CachedTexture','result.Texture'))
    g.chain('entry','path','valid','available','import','save','result');g.chain('valid.else','result');g.chain('available.else','result')
    return g.function('ReadCached',inputs=[v('Path','string')],outputs=[v('Texture','object:'+TEXTURE)],locals=[v('CachedTexture','object:'+TEXTURE)])


def prepare():
    g=Graph();g.node('self','self');g.set('reset','Prepared','false');branch(g,'mesh',validity(g,'valid','entry.Mesh'))
    bounds=call(g,'bounds',MESH+':GetBounds',{'self':'entry.Mesh'});call(g,'box',KML+':BreakBoxSphereBounds',{'InBoxSphereBounds':bounds})
    call(g,'meshset',SMC+':SetStaticMesh',{'self':get(g,'Mesh'),'NewMesh':'entry.Mesh'})
    offset=op(g,'offset','Multiply_VectorFloat','box.Origin',B=-1);call(g,'center',SCENE+':K2_SetRelativeLocation',{'self':get(g,'Mesh'),'NewLocation':offset},bSweep='false',bTeleport='true')
    call(g,'clearshow',CAPTURE_BASE+':ClearShowOnlyComponents',{'self':get(g,'Capture')})
    call(g,'showonly',CAPTURE_BASE+':ShowOnlyComponent',{'self':get(g,'Capture'),'InComponent':get(g,'Mesh')})
    set_value(g,'path','MeshPath',call(g,'meshpath',KSL+':GetPathName',{'Object':'entry.Mesh'}))
    g.call('frame','self:ConfigureFrame',Center='0,0,0');g.wire(('box.BoxExtent','frame.Extent'),('box.SphereRadius','frame.Radius'),('frame.Ready','result.Ready'))
    g.chain('entry','reset','mesh','meshset','center','clearshow','showonly','path','frame','result');g.chain('mesh.else','result')
    return g.function('Prepare',inputs=[v('Mesh','object:'+MESH)],outputs=[v('Ready','bool')])


def frame():
    g=Graph();g.node('self','self');g.set('reset','Prepared','false')
    radius=op(g,'radius','FMax','entry.Radius',B=1)
    previous='reset'
    for name,xyz,intensity in [('KeyLight',(2.5,-1.5,2.5),14),('FillLight',(-2,2.5,1),5)]:
        location=call(g,name+'vector',KML+':MakeVector',X=xyz[0],Y=xyz[1],Z=xyz[2]);offset=op(g,name+'offset','Multiply_VectorFloat',location,radius);at=op(g,name+'at','Add_VectorVector',offset,'entry.Center')
        call(g,name+'move',SCENE+':K2_SetRelativeLocation',{'self':get(g,name),'NewLocation':at},bSweep='false',bTeleport='true')
        call(g,name+'radius',LIGHT+':SetAttenuationRadius',{'self':get(g,name),'NewRadius':op(g,name+'range','Multiply_DoubleDouble',radius,B=12)})
        power=op(g,name+'power','Multiply_DoubleDouble',op(g,name+'square','Multiply_DoubleDouble',radius,radius),B=intensity);call(g,name+'intensity','/Script/Engine.LightComponent:SetIntensity',{'self':get(g,name),'NewIntensity':power})
        g.chain(previous,name+'move',name+'radius',name+'intensity');previous=name+'intensity'
    g.call('distance','self:FrameDistance');g.wire(('entry.Extent','distance.Extent'))
    view=call(g,'view',KML+':MakeVector',X=VIEW[0],Y=VIEW[1],Z=VIEW[2]);unit=op(g,'unit','Normal',view,Tolerance=1e-12);camera=op(g,'camera','Add_VectorVector','entry.Center',op(g,'offset','Multiply_VectorFloat',unit,'distance.Distance'))
    rotation=call(g,'look',KML+':FindLookAtRotation',{'Start':camera,'Target':'entry.Center'});call(g,'cameraat',SCENE+':K2_SetRelativeLocationAndRotation',{'self':get(g,'Capture'),'NewLocation':camera,'NewRotation':rotation},bSweep='false',bTeleport='true')
    branch(g,'target',validity(g,'targetvalid',get(g,'Target')))
    target=call(g,'create',RENDER+':CreateRenderTarget2D',{'WorldContextObject':'self.self'},Width=128,Height=128,Format='RTF_RGBA8',ClearColor='(R=0,G=0,B=0,A=1)',bAutoGenerateMipMaps='false',bSupportUAVs='false');set_value(g,'save','Target',target)
    set_value(g,'assign',CAPTURE+':TextureTarget',get(g,'Target'));g.wire((get(g,'Capture'),'assign.self'))
    set_value(g,'prepared','Prepared',validity(g,'ready',get(g,'Target')));g.wire((get(g,'Prepared'),'result.Ready'))
    g.chain('entry','reset');g.chain(previous,'distance','cameraat','target','assign','prepared','result');g.chain('target.else','create','save','assign')
    return g.function('ConfigureFrame',inputs=[v('Center','vector'),v('Extent','vector'),v('Radius','double')],outputs=[v('Ready','bool')])


def capture():
    g=Graph();branch(g,'ready',get(g,'Prepared'));call(g,'capture',CAPTURE+':CaptureScene',{'self':get(g,'Capture')});g.chain('entry','ready','capture');return g.function('CaptureFrame')


def write_cache():
    g=Graph();g.node('self','self');branch(g,'ready',get(g,'Prepared'));g.call('path','self:CachePath');g.wire((get(g,'MeshPath'),'path.Path'))
    call(g,'export',RENDER+':ExportRenderTarget',{'WorldContextObject':'self.self','TextureRenderTarget':get(g,'Target'),'FilePath':'path.Directory','FileName':'path.Name'})
    g.call('read','self:ReadCached');g.wire((get(g,'MeshPath'),'read.Path'));set_value(g,'cache','local:ResultTexture','read.Texture');g.get('out','local:ResultTexture');g.wire(('out.ResultTexture','result.Texture'));g.chain('entry','ready','path','export','read','cache','result');g.chain('ready.else','result')
    return g.function('WriteCache',outputs=[v('Texture','object:'+TEXTURE)],locals=[v('ResultTexture','object:'+TEXTURE)])


def write_share():
    """HoloNet share preview: a separate 512 px capture of a staged composition,
    saved beside its card as <name>_512.png. The 128 px card target is untouched."""
    g=Graph();g.node('self','self');branch(g,'composition',combine(g,'ready',[get(g,'Prepared'),call(g,'iscomposition',STR+'StartsWith',{'SourceString':get(g,'MeshPath')},InPrefix='/ZComDen/CompositionThumbs/',SearchCase='CaseSensitive')]))
    branch(g,'target',validity(g,'targetvalid',get(g,'ShareTarget')))
    target=call(g,'create',RENDER+':CreateRenderTarget2D',{'WorldContextObject':'self.self'},Width=512,Height=512,Format='RTF_RGBA8',ClearColor='(R=0,G=0,B=0,A=1)',bAutoGenerateMipMaps='false',bSupportUAVs='false');set_value(g,'save','ShareTarget',target)
    set_value(g,'assign',CAPTURE+':TextureTarget',get(g,'ShareTarget'));g.wire((get(g,'Capture'),'assign.self'))
    call(g,'capture',CAPTURE+':CaptureScene',{'self':get(g,'Capture')})
    g.call('path','self:CachePath');g.wire((get(g,'MeshPath'),'path.Path'))
    name=call(g,'name',STR+'Replace',{'SourceString':'path.Name'},From='.png',To='_512.png',SearchCase='CaseSensitive')
    call(g,'export',RENDER+':ExportRenderTarget',{'WorldContextObject':'self.self','TextureRenderTarget':get(g,'ShareTarget'),'FilePath':'path.Directory','FileName':name})
    set_value(g,'restore',CAPTURE+':TextureTarget',get(g,'Target'));g.wire((get(g,'Capture'),'restore.self'))
    g.chain('entry','composition','target','assign','capture','path','export','restore');g.chain('target.else','create','save','assign')
    return g.function('WriteSharePreview')


def release():
    g=Graph();g.set('prepared','Prepared','false');g.set('path','MeshPath','');g.set('capturetarget',CAPTURE+':TextureTarget');g.wire((get(g,'Capture'),'capturetarget.self'))
    branch(g,'valid',validity(g,'validtarget',get(g,'Target')));call(g,'release',RENDER+':ReleaseRenderTarget2D',{'TextureRenderTarget':get(g,'Target')});g.set('clear','Target')
    call(g,'mesh',SMC+':SetStaticMesh',{'self':get(g,'Mesh')})
    branch(g,'sharevalid',validity(g,'validshare',get(g,'ShareTarget')));call(g,'releaseshare',RENDER+':ReleaseRenderTarget2D',{'TextureRenderTarget':get(g,'ShareTarget')});g.set('clearshare','ShareTarget')
    g.chain('entry','prepared','path','capturetarget','valid','release','clear','mesh','sharevalid','releaseshare','clearshare');g.chain('valid.else','clear');g.chain('sharevalid.else','clearshare');return g.function('ReleaseStudio')


def studio_spec():
    from runtime_composition_thumbnails import prepare as prepare_composition, prepare_frame as composition_frame
    g=Graph();g.node('end','event',name='ReceiveEndPlay');g.call('release','self:ReleaseStudio');g.chain('end','release')
    return dict(kind='blueprint',path=STUDIO,parent=ACTOR,
        components=[dict(name='Root',**{'class':SCENE},props={'Mobility':'Movable'}),
            dict(name='Mesh',**{'class':SMC},attach='Root',props={'Mobility':'Movable','BodyInstance.CollisionEnabled':'NoCollision','CastShadow':'false','LightingChannels':'(bChannel0=False,bChannel1=True,bChannel2=False)'}),
            *[dict(name=name,**{'class':LIGHT},attach='Root',props={'Mobility':'Movable','CastShadows':'false','LightingChannels':'(bChannel0=False,bChannel1=True,bChannel2=False)'}) for name in ['KeyLight','FillLight']],
            dict(name='Capture',**{'class':CAPTURE},attach='Root',props={'FOVAngle':'30','bCaptureEveryFrame':'false','bCaptureOnMovement':'false','PrimitiveRenderMode':'PRM_UseShowOnlyList','CaptureSource':'SCS_FinalColorLDR'})],
        variables=[v('CompositionCenter','vector'),v('CompositionExtent','vector'),v('Target','object:'+TARGET),v('ShareTarget','object:'+TARGET),v('MeshPath','string'),v('Prepared','bool')],graph=g.spec(),
        functions=[valid_asset_path(),distance(),filename(),cache_path(),read_cache(),prepare(),prepare_composition(),composition_frame(),frame(),capture(),write_cache(),write_share(),release()])
