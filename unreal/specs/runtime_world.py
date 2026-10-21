"""Native world operations. Asset acquisition is separate from per-frame transforms.

Only engine classes and Blueprint VM are referenced at runtime. Vanilla snapshots
are transient UObject records, never serialized into layout saves.
"""
from graph import Graph, variable as v, KML, KSL, GS
from runtime_store import call, branch, combine, STR
from runtime import arr, unpack, ROOT, ENTRY
from runtime_assets import valid_asset_path

ACTOR='/Script/Engine.Actor'
SCENE='/Script/Engine.SceneComponent'
PRIMITIVE='/Script/Engine.PrimitiveComponent'
SMC='/Script/Engine.StaticMeshComponent'
MESH='/Script/Engine.StaticMesh'
MATERIAL='/Script/Engine.MaterialInterface'
PROP=ROOT+'BP_DenPlacedProp'
RECORD=ROOT+'BP_DenVanillaRecord'
WORLD=ROOT+'BP_DenWorld'


def void_function(g,name,**kwargs):
    g.links=[link for link in g.links if not any(pin.startswith('result.') for pin in link)]
    return g.function(name,**kwargs)


def set_value(g,name,var,source):
    g.set(name,var)
    g.wire((source,name+'.'+var.rsplit(':',1)[-1]))


def validity(g,name,source):
    return call(g,name,KSL+':IsValid',{'Object':source})


def finish_bool(g,name='Accepted',source='local:OK'):
    g.get('out',source)
    g.wire(('out.'+source.split(':')[-1],'result.'+name))


def vector_valid(g,name,value,positive=False):
    call(g,name+'break',KML+':BreakVector',{'InVec':value})
    ok=[]
    for axis in ['X','Y','Z']:
        pin=name+'break.'+axis
        lo=call(g,name+axis+'min',KML+(':Greater_DoubleDouble' if positive else ':GreaterEqual_DoubleDouble'),{'A':pin},B=0 if positive else -1e7)
        hi=call(g,name+axis+'max',KML+':LessEqual_DoubleDouble',{'A':pin},B=1e7)
        ok.extend([lo,hi])
    return combine(g,name+'valid',ok)


def valid_transform():
    g=Graph()
    unpack(g,'data',ENTRY,'entry.Value')
    checks=[vector_valid(g,'pos','data.Position'),vector_valid(g,'scale','data.Scale',True)]
    call(g,'rot',KML+':BreakRotator',{'InRot':'data.Rotation'})
    for axis in ['Roll','Pitch','Yaw']:
        lo=call(g,axis+'min',KML+':GreaterEqual_DoubleDouble',{'A':'rot.'+axis},B=-1e7)
        hi=call(g,axis+'max',KML+':LessEqual_DoubleDouble',{'A':'rot.'+axis},B=1e7)
        checks.extend([lo,hi])
    valid=combine(g,'valid',checks)
    g.wire((valid,'result.Valid'))
    g.chain('entry','result')
    return g.function('ValidTransform',inputs=[v('Value','struct:'+ENTRY)],outputs=[v('Valid','bool')])


def prop_transform():
    g=Graph()
    unpack(g,'data',ENTRY,'entry.Value')
    g.call('validate','self:ValidTransform')
    g.wire(('entry.Value','validate.Value'))
    g.get('current','Current');unpack(g,'prior',ENTRY,'current.Current')
    same=call(g,'samekey',STR+'EqualEqual_StrStr',{'A':'prior.Key','B':'data.Key'})
    new=call(g,'unassigned',STR+'EqualEqual_StrStr',{'A':'prior.Key'},B='')
    kind=call(g,'placedkind',KML+':EqualEqual_IntInt',{'A':'data.Kind'},B=0)
    branch(g,'valid',combine(g,'previewok',['validate.Valid',kind,combine(g,'identity',[same,new],True)]))
    call(g,'move',ACTOR+':K2_SetActorLocationAndRotation',{'NewLocation':'data.Position','NewRotation':'data.Rotation'},bSweep='false',bTeleport='true')
    call(g,'scale',ACTOR+':SetActorScale3D',{'NewScale3D':'data.Scale'})
    set_value(g,'remember','Current','entry.Value')
    g.set('yes','local:OK','true')
    finish_bool(g)
    g.chain('entry','validate','valid','move','scale','remember','yes','result')
    g.chain('valid.else','result')
    return g.function('PreviewTransform',inputs=[v('Value','struct:'+ENTRY)],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def valid_materials():
    g=Graph()
    unpack(g,'data',ENTRY,'entry.Value')
    arr(g,'expected','Length','data.Materials');arr(g,'actual','Length','entry.LoadedMaterials')
    same=call(g,'same',KML+':EqualEqual_IntInt',{'A':'expected.ReturnValue','B':'actual.ReturnValue'})
    branch(g,'size',same)
    g.get('i','local:Cursor')
    within=call(g,'within',KML+':Less_IntInt',{'A':'i.Cursor','B':'expected.ReturnValue'})
    branch(g,'loop',within)
    arr(g,'path','Get','data.Materials');g.wire(('i.Cursor','path.Index'))
    arr(g,'material','Get','entry.LoadedMaterials');g.wire(('i.Cursor','material.Index'))
    empty=call(g,'empty',STR+'EqualEqual_StrStr',{'A':'path.Item'},B='')
    branch(g,'default',empty)
    valid=validity(g,'objectvalid','material.Item')
    invalid=call(g,'invalid',KML+':Not_PreBool',{'A':valid})
    branch(g,'isnull',invalid)
    g.call('pathvalid','self:ValidAssetPath');g.wire(('path.Item','pathvalid.Path'));branch(g,'pathsafe','pathvalid.Valid')
    softpath=call(g,'softpath',KSL+':MakeSoftObjectPath',{'PathString':'path.Item'})
    softref=call(g,'softref',KSL+':Conv_SoftObjPathToSoftObjRef',{'SoftObjectPath':softpath})
    resolved=call(g,'resolved',KSL+':Conv_SoftObjectReferenceToObject',{'SoftObject':softref})
    equal=call(g,'equal',KML+':EqualEqual_ObjectObject',{'A':resolved,'B':'material.Item'})
    branch(g,'matches',combine(g,'matchesok',[valid,equal]))
    nxt=call(g,'next',KML+':Add_IntInt',{'A':'i.Cursor'},B=1)
    set_value(g,'advance','local:Cursor',nxt)
    g.set('yes','local:OK','true');finish_bool(g,'Valid')
    g.chain('entry','size','loop','default','isnull','advance','loop')
    g.chain('size.else','result');g.chain('loop.else','yes','result')
    g.chain('default.else','pathvalid','pathsafe','matches','advance');g.chain('pathsafe.else','result');g.chain('matches.else','result');g.chain('isnull.else','result')
    return g.function('ValidMaterials',inputs=[v('Value','struct:'+ENTRY),v('LoadedMaterials','object:'+MATERIAL+'[]')],
                      outputs=[v('Valid','bool')],locals=[v('Cursor','int','0'),v('OK','bool','false')])


def configure_prop():
    g=Graph()
    unpack(g,'data',ENTRY,'entry.Value')
    meshok=validity(g,'meshvalid','entry.LoadedMesh')
    kind=call(g,'kind',KML+':EqualEqual_IntInt',{'A':'data.Kind'},B=0)
    key=call(g,'key',STR+'NotEqual_StriStri',{'A':'data.Key'},B='')
    g.call('validate','self:ValidTransform');g.wire(('entry.Value','validate.Value'))
    g.call('pathvalid','self:ValidAssetPath');g.wire(('data.Mesh','pathvalid.Path'));branch(g,'pathsafe','pathvalid.Valid')
    meshpath=call(g,'meshpath',KSL+':MakeSoftObjectPath',{'PathString':'data.Mesh'})
    meshref=call(g,'meshref',KSL+':Conv_SoftObjPathToSoftObjRef',{'SoftObjectPath':meshpath})
    resolved=call(g,'resolvedmesh',KSL+':Conv_SoftObjectReferenceToObject',{'SoftObject':meshref})
    matching=call(g,'matching',KML+':EqualEqual_ObjectObject',{'A':resolved,'B':'entry.LoadedMesh'})
    minmode=call(g,'minmode',KML+':GreaterEqual_IntInt',{'A':'data.CollisionMode'},B=0)
    maxmode=call(g,'maxmode',KML+':LessEqual_IntInt',{'A':'data.CollisionMode'},B=2)
    g.call('materialsvalid','self:ValidMaterials');g.wire(('entry.Value','materialsvalid.Value'),('entry.LoadedMaterials','materialsvalid.LoadedMaterials'))
    branch(g,'guard',combine(g,'valid',[meshok,kind,key,matching,minmode,maxmode,'validate.Valid','materialsvalid.Valid']))
    g.get('mesh','Mesh')
    call(g,'mobility',SCENE+':SetMobility',{'self':'mesh.Mesh'},NewMobility='Movable')
    call(g,'setmesh',SMC+':SetStaticMesh',{'self':'mesh.Mesh','NewMesh':'entry.LoadedMesh'})
    g.call('transform','self:PreviewTransform');g.wire(('entry.Value','transform.Value'))
    # Reset old material overrides too. An empty slot uses the mesh's own material.
    count=call(g,'count',PRIMITIVE+':GetNumMaterials',{'self':'mesh.Mesh'})
    arr(g,'length','Length','entry.LoadedMaterials')
    largest=call(g,'slots',KML+':Max',{'A':count,'B':'length.ReturnValue'})
    g.get('i','local:Cursor')
    within=call(g,'within',KML+':Less_IntInt',{'A':'i.Cursor','B':largest})
    branch(g,'loop',within)
    available=call(g,'available',KML+':Less_IntInt',{'A':'i.Cursor','B':'length.ReturnValue'})
    branch(g,'hasmaterial',available)
    arr(g,'material','Get','entry.LoadedMaterials');g.wire(('i.Cursor','material.Index'))
    set_value(g,'remembermat','local:Override','material.Item')
    g.set('nomat','local:Override')
    g.get('override','local:Override')
    call(g,'setmaterial',PRIMITIVE+':SetMaterial',{'self':'mesh.Mesh','ElementIndex':'i.Cursor','Material':'override.Override'})
    nxt=call(g,'next',KML+':Add_IntInt',{'A':'i.Cursor'},B=1)
    set_value(g,'advance','local:Cursor',nxt)
    # Bounds from the asset, not the rotated world AABB: matches Lua's 50 cm rule.
    bounds=call(g,'bounds',MESH+':GetBounds',{'self':'entry.LoadedMesh'})
    call(g,'box',KML+':BreakBoxSphereBounds',{'InBoxSphereBounds':bounds})
    extent=call(g,'extent',KML+':Vector_GetAbsMax',{'A':'box.BoxExtent'})
    scale=call(g,'maxscale',KML+':Vector_GetAbsMax',{'A':'data.Scale'})
    scaled=call(g,'scaled',KML+':Multiply_DoubleDouble',{'A':extent,'B':scale})
    auto=call(g,'auto',KML+':Greater_DoubleDouble',{'A':scaled},B=25)
    explicit=call(g,'explicit',KML+':EqualEqual_IntInt',{'A':'data.CollisionMode'},B=1)
    automatic=call(g,'automatic',KML+':EqualEqual_IntInt',{'A':'data.CollisionMode'},B=0)
    solid=combine(g,'solid',[explicit,combine(g,'autosolid',[automatic,auto])],True)
    call(g,'profile',PRIMITIVE+':SetCollisionProfileName',{'self':'mesh.Mesh'},InCollisionProfileName='BlockAll',bUpdateOverlaps='true')
    branch(g,'solidbranch',solid)
    call(g,'pawnignore',PRIMITIVE+':SetCollisionResponseToChannel',{'self':'mesh.Mesh'},Channel='ECC_Pawn',NewResponse='ECR_Ignore')
    branch(g,'ghost','entry.Ghost')
    call(g,'nocollision',PRIMITIVE+':SetCollisionEnabled',{'self':'mesh.Mesh'},NewType='NoCollision')
    g.set('yes','local:OK','true')
    finish_bool(g)
    g.chain('entry','pathvalid','pathsafe','validate','materialsvalid','guard','mobility','setmesh','transform','loop','hasmaterial','remembermat','setmaterial','advance','loop')
    g.chain('pathsafe.else','result');g.chain('guard.else','result');g.chain('hasmaterial.else','nomat','setmaterial')
    g.chain('loop.else','profile','solidbranch','ghost','nocollision','yes','result')
    g.chain('solidbranch.else','pawnignore','ghost');g.chain('ghost.else','yes')
    return g.function('Configure',inputs=[v('Value','struct:'+ENTRY),v('LoadedMesh','object:'+MESH),v('LoadedMaterials','object:'+MATERIAL+'[]'),v('Ghost','bool')],
                      outputs=[v('Accepted','bool')],locals=[v('OK','bool','false'),v('Cursor','int','0'),v('Override','object:'+MATERIAL)])


def capture_record():
    g=Graph()
    g.get('ready','Ready')
    branch(g,'already','ready.Ready')
    g.get('oldtarget','Target')
    same=call(g,'sametarget',KML+':EqualEqual_ObjectObject',{'A':'oldtarget.Target','B':'entry.Object'})
    g.call('oldalive','self:IsAlive')
    set_value(g,'reuse','local:OK',combine(g,'reuseok',[same,'oldalive.Alive']))
    targetvalid=validity(g,'valid','entry.Object')
    branch(g,'guard',targetvalid)
    g.node('actor','cast',**{'class':ACTOR});g.wire(('entry.Object','actor.Object'))
    set_value(g,'actorref','Actor','actor.AsActor')
    root=call(g,'actorroot',ACTOR+':K2_GetRootComponent',{'self':'actor.AsActor'})
    set_value(g,'actorcomponent','Root',root)
    g.set('actorflag','IsActor','true')
    g.node('component','cast',**{'class':SCENE});g.wire(('entry.Object','component.Object'))
    set_value(g,'componentref','Root','component.AsScene Component')
    owner=call(g,'owner','/Script/Engine.ActorComponent:GetOwner',{'self':'component.AsScene Component'})
    set_value(g,'ownerref','Actor',owner)
    g.set('componentflag','IsActor','false')
    g.get('root','Root');g.get('actorget','Actor')
    branch(g,'rootguard',combine(g,'refs',[validity(g,'rootvalid','root.Root'),validity(g,'ownervalid','actorget.Actor')]))
    set_value(g,'target','Target','entry.Object')
    path=call(g,'path',KSL+':GetPathName',{'Object':'entry.Object'})
    set_value(g,'key','Key',path)
    set_value(g,'layoutkey','LayoutKey',path)
    for name,fn in [('Position','K2_GetComponentLocation'),('Rotation','K2_GetComponentRotation'),('Scale','K2_GetComponentScale')]:
        value=call(g,'read'+name,SCENE+':'+fn,{'self':'root.Root'})
        set_value(g,'save'+name,'Original'+name,value)
    g.get('mobility',SCENE+':Mobility');g.wire(('root.Root','mobility.self'))
    set_value(g,'savemobility','OriginalMobility','mobility.Mobility')
    g.get('isactor','IsActor');branch(g,'actorstate','isactor.IsActor')
    g.get('hidden',ACTOR+':bHidden');g.wire(('actorget.Actor','hidden.self'))
    set_value(g,'actorhidden','WasHidden','hidden.bHidden')
    collision=call(g,'actorcollision',ACTOR+':GetActorEnableCollision',{'self':'actorget.Actor'})
    set_value(g,'actorcollisionsave','OriginalActorCollision',collision)
    visible=call(g,'visible',SCENE+':IsVisible',{'self':'root.Root'})
    hidden=call(g,'notvisible',KML+':Not_PreBool',{'A':visible})
    set_value(g,'componenthidden','WasHidden',hidden)
    g.node('primitive','cast',**{'class':PRIMITIVE});g.wire(('root.Root','primitive.Object'))
    set_value(g,'primitiveref','Primitive','primitive.AsPrimitive Component')
    collision=call(g,'collision',PRIMITIVE+':GetCollisionEnabled',{'self':'primitive.AsPrimitive Component'})
    set_value(g,'savecollision','OriginalCollision',collision)
    g.set('readyset','Ready','true')
    g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','already','oldalive','reuse','result');g.chain('already.else','guard','actor','actorref','actorcomponent','actorflag','rootguard')
    g.chain('guard.else','result');g.chain('actor.CastFailed','component','componentref','ownerref','componentflag','rootguard')
    g.chain('component.CastFailed','result');g.chain('rootguard.else','result')
    g.chain('rootguard','target','key','layoutkey','savePosition','saveRotation','saveScale','savemobility','actorstate','actorhidden','actorcollisionsave','primitive','primitiveref','savecollision','readyset','yes','result')
    g.chain('actorstate.else','componenthidden','primitive');g.chain('primitive.CastFailed','readyset')
    return g.function('Capture',inputs=[v('Object','object:/Script/CoreUObject.Object')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def record_alive():
    g=Graph()
    for name in ['Ready','Root','Actor','Target','Key']:g.get(name.lower(),name)
    path=call(g,'path',KSL+':GetPathName',{'Object':'target.Target'})
    same=call(g,'same',STR+'EqualEqual_StrStr',{'A':path,'B':'key.Key'})
    alive=combine(g,'alive',['ready.Ready',validity(g,'rootvalid','root.Root'),validity(g,'actorvalid','actor.Actor'),validity(g,'targetvalid','target.Target'),same])
    g.wire((alive,'result.Alive'));g.chain('entry','result')
    return g.function('IsAlive',outputs=[v('Alive','bool')])


def record_transform():
    g=Graph()
    unpack(g,'data',ENTRY,'entry.Value')
    g.get('root','Root');g.get('moved','Moved')
    has=combine(g,'has',['data.HasPosition','data.HasRotation','data.HasScale'],True)
    desired=combine(g,'desired',['entry.Present',has])
    branch(g,'apply',desired)
    call(g,'movable',SCENE+':SetMobility',{'self':'root.Root'},NewMobility='Movable')
    for field,typ in [('Position','Vector'),('Rotation','Rotator'),('Scale','Vector')]:
        g.get('original'+field,'Original'+field)
        value=call(g,'choose'+field,KML+':Select'+typ,{'A':'data.'+field,'B':'original'+field+'.Original'+field,'bPickA':'data.Has'+field})
    call(g,'move',SCENE+':K2_SetWorldLocationAndRotation',{'self':'root.Root','NewLocation':'choosePosition.ReturnValue','NewRotation':'chooseRotation.ReturnValue'},bSweep='false',bTeleport='true')
    call(g,'scale',SCENE+':SetWorldScale3D',{'self':'root.Root','NewScale':'chooseScale.ReturnValue'})
    g.set('movedset','Moved','true')
    branch(g,'restore','moved.Moved')
    call(g,'restoremove',SCENE+':K2_SetWorldLocationAndRotation',{'self':'root.Root','NewLocation':'originalPosition.OriginalPosition','NewRotation':'originalRotation.OriginalRotation'},bSweep='false',bTeleport='true')
    call(g,'restorescale',SCENE+':SetWorldScale3D',{'self':'root.Root','NewScale':'originalScale.OriginalScale'})
    g.get('mobility','OriginalMobility')
    call(g,'restoremobility',SCENE+':SetMobility',{'self':'root.Root','NewMobility':'mobility.OriginalMobility'})
    g.set('movedclear','Moved','false')
    g.chain('entry','apply','movable','move','scale','movedset','result')
    g.chain('apply.else','restore','restoremove','restorescale','restoremobility','movedclear','result')
    g.chain('restore.else','result')
    return void_function(g,'ApplyTransform',inputs=[v('Value','struct:'+ENTRY),v('Present','bool')])


def record_visibility():
    g=Graph()
    for name in ['Root','Actor','Primitive','IsActor','DidHide','WasHidden','OriginalActorCollision','OriginalCollision']:g.get(name.lower(),name)
    branch(g,'hide','entry.Hidden')
    branch(g,'hidalready','didhide.DidHide')
    branch(g,'hideactor','isactor.IsActor')
    call(g,'hidea',ACTOR+':SetActorHiddenInGame',{'self':'actor.Actor'},bNewHidden='true')
    call(g,'disablea',ACTOR+':SetActorEnableCollision',{'self':'actor.Actor'},bNewActorEnableCollision='false')
    call(g,'hidec',SCENE+':SetVisibility',{'self':'root.Root'},bNewVisibility='false',bPropagateToChildren='false')
    branch(g,'primitivevalid',validity(g,'pvalid','primitive.Primitive'))
    call(g,'disablec',PRIMITIVE+':SetCollisionEnabled',{'self':'primitive.Primitive'},NewType='NoCollision')
    g.set('hiddenflag','DidHide','true')
    branch(g,'restore','didhide.DidHide')
    branch(g,'wasvisible','washidden.WasHidden')
    branch(g,'showactor','isactor.IsActor')
    call(g,'showa',ACTOR+':SetActorHiddenInGame',{'self':'actor.Actor'},bNewHidden='false')
    call(g,'enablea',ACTOR+':SetActorEnableCollision',{'self':'actor.Actor','bNewActorEnableCollision':'originalactorcollision.OriginalActorCollision'})
    call(g,'showc',SCENE+':SetVisibility',{'self':'root.Root'},bNewVisibility='true',bPropagateToChildren='false')
    branch(g,'restoreprimitive',validity(g,'rpvalid','primitive.Primitive'))
    call(g,'enablec',PRIMITIVE+':SetCollisionEnabled',{'self':'primitive.Primitive','NewType':'originalcollision.OriginalCollision'})
    g.set('clearhidden','DidHide','false')
    g.chain('entry','hide','hidalready','result');g.chain('hidalready.else','hideactor','hidea','disablea','hiddenflag','result')
    g.chain('hideactor.else','hidec','primitivevalid','disablec','hiddenflag');g.chain('primitivevalid.else','hiddenflag')
    branch(g,'componentwashidden','washidden.WasHidden')
    g.chain('hide.else','restore','showactor','wasvisible','enablea','clearhidden','result');g.chain('restore.else','result')
    g.chain('wasvisible.else','showa','enablea')
    g.chain('showactor.else','componentwashidden','restoreprimitive','enablec','clearhidden')
    g.chain('componentwashidden.else','showc','restoreprimitive');g.chain('restoreprimitive.else','clearhidden')
    return void_function(g,'ApplyVisibility',inputs=[v('Hidden','bool')])


def apply_record():
    g=Graph()
    g.call('alive','self:IsAlive')
    g.call('validate','self:ValidTransform');g.wire(('entry.Value','validate.Value'))
    absent=call(g,'absent',KML+':Not_PreBool',{'A':'entry.Present'})
    branch(g,'valid',combine(g,'allowed',['alive.Alive',combine(g,'dataok',[absent,'validate.Valid'],True)]))
    g.call('transform','self:ApplyTransform');g.wire(('entry.Value','transform.Value'),('entry.Present','transform.Present'))
    unpack(g,'data',ENTRY,'entry.Value')
    hidden=combine(g,'hidden',['entry.Present','data.Hidden'])
    g.call('visibility','self:ApplyVisibility');g.wire((hidden,'visibility.Hidden'))
    g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','alive','validate','valid','transform','visibility','yes','result');g.chain('valid.else','result')
    return g.function('Apply',inputs=[v('Value','struct:'+ENTRY),v('Present','bool')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def specs():
    yield '12_BP_DenPlacedProp',dict(kind='blueprint',path=PROP,parent=ACTOR,
        variables=[v('Current','struct:'+ENTRY)],
        components=[dict(name='Mesh',**{'class':SMC},props={'Mobility':'Movable','BodyInstance.CollisionEnabled':'NoCollision'})],
        functions=[valid_asset_path(),valid_transform(),valid_materials(),prop_transform(),configure_prop()])
    yield '13_BP_DenVanillaRecord',dict(kind='blueprint',path=RECORD,parent='/Script/CoreUObject.Object',
        variables=[v('Target','object:/Script/CoreUObject.Object'),v('Root','object:'+SCENE),v('Actor','object:'+ACTOR),v('Primitive','object:'+PRIMITIVE),
                   v('Key','string'),v('LayoutKey','string'),v('Ready','bool','false'),v('IsActor','bool','false'),v('WasHidden','bool','false'),
                   v('DidHide','bool','false'),v('Moved','bool','false'),v('OriginalPosition','vector'),v('OriginalRotation','rotator'),v('OriginalScale','vector'),
                   v('OriginalMobility','byte'),v('OriginalCollision','byte'),v('OriginalActorCollision','bool')],
        functions=[valid_transform(),capture_record(),record_alive(),record_transform(),record_visibility(),apply_record()])
    yield '14_BP_DenWorld',world_spec()


def refresh_actors():
    g=Graph()
    call(g,'actors',GS+':GetAllActorsOfClass',ActorClass=ACTOR)
    set_value(g,'remember','WorldActors','actors.OutActors')
    g.chain('entry','actors','remember')
    return g.function('RefreshActors')


def resolve_key():
    g=Graph()
    length=call(g,'length',STR+'Len',{'S':'entry.Key'})
    minimum=call(g,'minimum',KML+':Greater_IntInt',{'A':length},B=3)
    maximum=call(g,'maximum',KML+':LessEqual_IntInt',{'A':length},B=1023)
    starts=call(g,'starts',STR+'StartsWith',{'SourceString':'entry.Key'},InPrefix='/')
    branch(g,'pathsafe',combine(g,'safekey',[minimum,maximum,starts]))
    path=call(g,'path',KSL+':MakeSoftObjectPath',{'PathString':'entry.Key'})
    soft=call(g,'soft',KSL+':Conv_SoftObjPathToSoftObjRef',{'SoftObjectPath':path})
    loaded=call(g,'loaded',KSL+':Conv_SoftObjectReferenceToObject',{'SoftObject':soft})
    # Resolve only: never LoadAsset a world object, which could load an off-world level.
    set_value(g,'candidate','local:Candidate',loaded)
    g.get('candidateget','local:Candidate')
    valid=validity(g,'valid','candidateget.Candidate')
    actual=call(g,'actual',KSL+':GetPathName',{'Object':'candidateget.Candidate'})
    same=call(g,'same',STR+'EqualEqual_StrStr',{'A':actual,'B':'entry.Key'})
    branch(g,'guard',combine(g,'exact',[valid,same]))
    g.node('actor','cast',**{'class':ACTOR});g.wire(('candidateget.Candidate','actor.Object'))
    set_value(g,'actorref','local:CandidateOwner','actor.AsActor')
    g.node('component','cast',**{'class':SCENE});g.wire(('candidateget.Candidate','component.Object'))
    owner=call(g,'owner','/Script/Engine.ActorComponent:GetOwner',{'self':'component.AsScene Component'})
    set_value(g,'componentref','local:CandidateOwner',owner)
    g.get('actors','WorldActors');g.get('ownerget','local:CandidateOwner')
    arr(g,'contains','Contains','actors.WorldActors');g.wire(('ownerget.CandidateOwner','contains.ItemToFind'))
    branch(g,'inworld','contains.ReturnValue')
    set_value(g,'found','local:Resolved','candidateget.Candidate')
    g.get('out','local:Resolved');g.wire(('out.Resolved','result.Object'))
    g.chain('entry','pathsafe','candidate','guard','actor','actorref','inworld','found','result')
    g.chain('pathsafe.else','result');g.chain('guard.else','result');g.chain('actor.CastFailed','component','componentref','inworld')
    g.chain('component.CastFailed','result');g.chain('inworld.else','result')
    return g.function('ResolveKey',inputs=[v('Key','string')],outputs=[v('Object','object:/Script/CoreUObject.Object')],
        locals=[v('Candidate','object:/Script/CoreUObject.Object'),v('CandidateOwner','object:'+ACTOR),v('Resolved','object:/Script/CoreUObject.Object')])


def find_object(collection,klass,method):
    g=Graph()
    g.get('objects',collection);g.get('i','local:Cursor')
    arr(g,'length','Length','objects.'+collection)
    within=call(g,'within',KML+':Less_IntInt',{'A':'i.Cursor','B':'length.ReturnValue'})
    branch(g,'loop',within)
    arr(g,'item','Get','objects.'+collection);g.wire(('i.Cursor','item.Index'))
    branch(g,'valid',validity(g,'validity','item.Item'))
    if collection=='Records':
        g.get('key',klass+':LayoutKey');g.wire(('item.Item','key.self'))
        call(g,'alive',klass+':IsAlive',{'self':'item.Item'})
        wanted=call(g,'same',STR+'EqualEqual_StrStr',{'A':'key.LayoutKey','B':'entry.Key'})
        branch(g,'matches',combine(g,'matchok',[wanted,'alive.Alive']))
        g.chain('valid','alive','matches')
    else:
        g.get('current',klass+':Current');g.wire(('item.Item','current.self'))
        unpack(g,'data',ENTRY,'current.Current')
        wanted=call(g,'same',STR+'EqualEqual_StrStr',{'A':'data.Key','B':'entry.Key'})
        branch(g,'matches',wanted)
        g.chain('valid','matches')
    set_value(g,'remember','local:FoundIndex','i.Cursor')
    nxt=call(g,'next',KML+':Add_IntInt',{'A':'i.Cursor'},B=1)
    set_value(g,'advance','local:Cursor',nxt)
    g.get('out','local:FoundIndex');g.wire(('out.FoundIndex','result.Index'))
    g.chain('entry','loop','valid');g.chain('matches','remember','result')
    g.chain('loop.else','result');g.chain('valid.else','advance','loop');g.chain('matches.else','advance')
    return g.function(method,inputs=[v('Key','string')],outputs=[v('Index','int')],locals=[v('Cursor','int','0'),v('FoundIndex','int','-1')])


def set_vanilla():
    g=Graph()
    unpack(g,'data',ENTRY,'entry.Value')
    key=call(g,'key',STR+'NotEqual_StriStri',{'A':'entry.Key'},B='')
    kind=call(g,'kind',KML+':EqualEqual_IntInt',{'A':'data.Kind'},B=2)
    same=call(g,'same',STR+'EqualEqual_StrStr',{'A':'data.Key','B':'entry.Key'})
    absent=call(g,'absent',KML+':Not_PreBool',{'A':'entry.Present'})
    branch(g,'valid',combine(g,'validrequest',[key,combine(g,'validvalue',[absent,combine(g,'identity',[kind,same])],True)]))
    g.call('find','self:FindRecord');g.wire(('entry.Key','find.Key'))
    exists=call(g,'exists',KML+':GreaterEqual_IntInt',{'A':'find.Index'},B=0)
    branch(g,'found',exists)
    g.get('records','Records')
    arr(g,'record','Get','records.Records');g.wire(('find.Index','record.Index'))
    set_value(g,'remember','local:Binding','record.Item')
    branch(g,'present','entry.Present')
    g.call('resolve','self:ResolveKey');g.wire(('entry.Key','resolve.Key'))
    branch(g,'loaded',validity(g,'validobject','resolve.Object'))
    g.node('self','self')
    created=call(g,'create',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=RECORD)
    g.node('cast','cast',**{'class':RECORD});g.wire((created,'cast.Object'))
    set_value(g,'created','local:Binding','cast.AsBP Den Vanilla Record')
    g.get('binding','local:Binding')
    call(g,'capture',RECORD+':Capture',{'self':'binding.Binding','Object':'resolve.Object'})
    branch(g,'captured','capture.Accepted')
    arr(g,'add','Add','records.Records');g.wire(('binding.Binding','add.NewItem'))
    call(g,'apply',RECORD+':Apply',{'self':'binding.Binding','Value':'entry.Value','Present':'entry.Present'})
    branch(g,'applied','apply.Accepted')
    g.set('success','local:ResultStatus','1');g.set('dormant','local:ResultStatus','2')
    g.get('status','local:ResultStatus');g.wire(('status.ResultStatus','result.Status'))
    g.chain('entry','valid','find','found','remember','apply','applied','success','result')
    g.chain('valid.else','result');g.chain('found.else','present','resolve','loaded','create','cast','created','capture','captured','add','apply')
    g.chain('present.else','success');g.chain('loaded.else','dormant','result');g.chain('cast.CastFailed','result');g.chain('captured.else','result');g.chain('applied.else','result')
    return g.function('SetVanilla',inputs=[v('Key','string'),v('Value','struct:'+ENTRY),v('Present','bool')],outputs=[v('Status','int')],
        locals=[v('Binding','object:'+RECORD),v('ResultStatus','int','3')])


def set_placed():
    g=Graph()
    unpack(g,'data',ENTRY,'entry.Value')
    kind=call(g,'kind',KML+':EqualEqual_IntInt',{'A':'data.Kind'},B=0)
    key=call(g,'key',STR+'NotEqual_StriStri',{'A':'data.Key'},B='')
    branch(g,'guard',combine(g,'identity',[kind,key]))
    branch(g,'meshvalid',validity(g,'meshcheck','entry.LoadedMesh'))
    g.call('find','self:FindPlaced');g.wire(('data.Key','find.Key'))
    exists=call(g,'exists',KML+':GreaterEqual_IntInt',{'A':'find.Index'},B=0)
    branch(g,'existing',exists)
    g.get('placed','Placed')
    arr(g,'prop','Get','placed.Placed');g.wire(('find.Index','prop.Index'))
    set_value(g,'remember','local:Selected','prop.Item')
    g.node('self','self')
    identity=call(g,'spawntransform',KML+':MakeTransform',Location='0,0,0',Rotation='0,0,0',Scale='1,1,1')
    spawn=call(g,'spawn',GS+':BeginDeferredActorSpawnFromClass',{'Owner':'self.self','SpawnTransform':identity},ActorClass=PROP,CollisionHandlingOverride='AlwaysSpawn')
    # Spawn with the identity transform; Configure validates before applying values.
    finish=call(g,'finish',GS+':FinishSpawningActor',{'Actor':spawn,'SpawnTransform':identity})
    g.node('cast','cast',**{'class':PROP});g.wire((finish,'cast.Object'))
    set_value(g,'newprop','local:Selected','cast.AsBP Den Placed Prop')
    g.set('newflag','local:NewProp','true')
    g.get('selected','local:Selected');g.get('new','local:NewProp')
    call(g,'configure',PROP+':Configure',{'self':'selected.Selected','Value':'entry.Value','LoadedMesh':'entry.LoadedMesh','LoadedMaterials':'entry.LoadedMaterials','Ghost':'entry.Ghost'})
    branch(g,'configured','configure.Accepted')
    branch(g,'addnew','new.NewProp')
    arr(g,'append','Add','placed.Placed');g.wire(('selected.Selected','append.NewItem'))
    g.set('yes','local:ResultStatus','1')
    g.set('badmesh','local:ResultStatus','4')
    branch(g,'cleanup','new.NewProp')
    call(g,'destroy',ACTOR+':K2_DestroyActor',{'self':'selected.Selected'})
    g.set('clearref','local:Selected')
    g.get('status','local:ResultStatus')
    g.wire(('status.ResultStatus','result.Status'),('selected.Selected','result.Prop'))
    g.chain('entry','guard','meshvalid','find','existing','remember','configure','configured','addnew','append','yes','result')
    g.chain('guard.else','result');g.chain('meshvalid.else','badmesh','result');g.chain('existing.else','spawn','finish','cast','newprop','newflag','configure')
    g.chain('cast.CastFailed','result');g.chain('addnew.else','yes');g.chain('configured.else','cleanup','destroy','clearref','result');g.chain('cleanup.else','result')
    return g.function('SetPlaced',inputs=[v('Value','struct:'+ENTRY),v('LoadedMesh','object:'+MESH),v('LoadedMaterials','object:'+MATERIAL+'[]'),v('Ghost','bool')],
        outputs=[v('Prop','object:'+PROP),v('Status','int')],locals=[v('Selected','object:'+PROP),v('NewProp','bool','false'),v('ResultStatus','int','3')])


def remove_placed():
    g=Graph()
    g.call('find','self:FindPlaced');g.wire(('entry.Key','find.Key'))
    exists=call(g,'exists',KML+':GreaterEqual_IntInt',{'A':'find.Index'},B=0)
    branch(g,'found',exists)
    g.get('placed','Placed')
    arr(g,'item','Get','placed.Placed');g.wire(('find.Index','item.Index'))
    call(g,'destroy',ACTOR+':K2_DestroyActor',{'self':'item.Item'})
    arr(g,'remove','Remove','placed.Placed');g.wire(('find.Index','remove.IndexToRemove'))
    g.chain('entry','find','found','destroy','remove')
    return g.function('RemovePlaced',inputs=[v('Key','string')])


def clear_world():
    g=Graph()
    g.get('placed','Placed');g.get('records','Records');g.get('i','local:Cursor')
    arr(g,'plen','Length','placed.Placed')
    branch(g,'ploop',call(g,'pwithin',KML+':Less_IntInt',{'A':'i.Cursor','B':'plen.ReturnValue'}))
    arr(g,'p','Get','placed.Placed');g.wire(('i.Cursor','p.Index'))
    branch(g,'pvalid',validity(g,'pcheck','p.Item'))
    call(g,'destroy',ACTOR+':K2_DestroyActor',{'self':'p.Item'})
    nxt=call(g,'next',KML+':Add_IntInt',{'A':'i.Cursor'},B=1)
    set_value(g,'pnext','local:Cursor',nxt)
    g.set('reset','local:Cursor','0')
    arr(g,'rlen','Length','records.Records')
    branch(g,'rloop',call(g,'rwithin',KML+':Less_IntInt',{'A':'i.Cursor','B':'rlen.ReturnValue'}))
    arr(g,'r','Get','records.Records');g.wire(('i.Cursor','r.Index'))
    branch(g,'rvalid',validity(g,'rcheck','r.Item'))
    call(g,'restore',RECORD+':Apply',{'self':'r.Item'},Present='false')
    set_value(g,'rnext','local:Cursor',nxt)
    g.call('forget','self:Forget')
    g.chain('entry','ploop','pvalid','destroy','pnext','ploop');g.chain('pvalid.else','pnext')
    g.chain('ploop.else','reset','rloop','rvalid','restore','rnext','rloop');g.chain('rvalid.else','rnext')
    g.chain('rloop.else','forget')
    return g.function('Clear',locals=[v('Cursor','int','0')])


def forget_world():
    g=Graph()
    for name in ['Placed','Records','WorldActors']:
        g.get(name.lower(),name)
        arr(g,'clear'+name,'Clear',name.lower()+'.'+name)
    g.chain('entry','clearPlaced','clearRecords','clearWorldActors')
    return g.function('Forget')


def world_spec():
    g=Graph()
    g.node('begin','event',name='ReceiveBeginPlay');g.call('refresh','self:RefreshActors');g.chain('begin','refresh')
    # World teardown drops references; explicit discard/disable uses Clear while
    # the world is live. Never restore objects during another world's teardown.
    g.node('end','event',name='ReceiveEndPlay');g.call('forget','self:Forget');g.chain('end','forget')
    return dict(kind='blueprint',path=WORLD,parent=ACTOR,
        variables=[v('Placed','object:'+PROP+'[]'),v('Records','object:'+RECORD+'[]'),v('WorldActors','object:'+ACTOR+'[]')],graph=g.spec(),
        functions=[refresh_actors(),resolve_key(),find_object('Records',RECORD,'FindRecord'),find_object('Placed',PROP,'FindPlaced'),
                   bind_vanilla(),set_vanilla(),set_placed(),remove_placed(),clear_world(),forget_world()])


def bind_vanilla():
    """Bind a recovered layout identity without changing the object's real path."""
    g=Graph()
    nonempty=call(g,'keyok',STR+'NotEqual_StriStri',{'A':'entry.Key'},B='')
    branch(g,'valid',combine(g,'inputs',[nonempty,validity(g,'objectvalid','entry.Object')]))
    path=call(g,'path',KSL+':GetPathName',{'Object':'entry.Object'})
    g.call('resolve','self:ResolveKey');g.wire((path,'resolve.Key'))
    same=call(g,'same',KML+':EqualEqual_ObjectObject',{'A':'resolve.Object','B':'entry.Object'})
    branch(g,'inworld',combine(g,'owned',[same,validity(g,'resolvedvalid','resolve.Object')]))
    g.call('find','self:FindRecord');g.wire(('entry.Key','find.Key'))
    exists=call(g,'exists',KML+':GreaterEqual_IntInt',{'A':'find.Index'},B=0)
    branch(g,'existing',exists)
    g.get('records','Records');arr(g,'old','Get','records.Records');g.wire(('find.Index','old.Index'))
    g.get('target',RECORD+':Target');g.wire(('old.Item','target.self'))
    equal=call(g,'equal',KML+':EqualEqual_ObjectObject',{'A':'target.Target','B':'entry.Object'})
    set_value(g,'oldok','local:OK',equal)
    g.node('self','self')
    created=call(g,'create',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=RECORD)
    g.node('cast','cast',**{'class':RECORD});g.wire((created,'cast.Object'))
    call(g,'capture',RECORD+':Capture',{'self':'cast.AsBP Den Vanilla Record','Object':'entry.Object'})
    branch(g,'captured','capture.Accepted')
    set_value(g,'alias',RECORD+':LayoutKey','entry.Key');g.wire(('cast.AsBP Den Vanilla Record','alias.self'))
    arr(g,'append','Add','records.Records');g.wire(('cast.AsBP Den Vanilla Record','append.NewItem'))
    g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','valid','resolve','inworld','find','existing','oldok','result')
    for pin in ['valid.else','inworld.else','cast.CastFailed','captured.else']:g.chain(pin,'result')
    g.chain('existing.else','create','cast','capture','captured','alias','append','yes','result')
    return g.function('BindVanilla',inputs=[v('Key','string'),v('Object','object:/Script/CoreUObject.Object')],
                      outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])
