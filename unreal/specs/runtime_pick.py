"""Native selection classification and collision-fallback geometry.

Transient object references stay in Blueprint-owned objects. No asset loading or
layout writes occur here; accepted selections feed the session command layer.
"""
from graph import Graph, variable as v, KML, KSL, GS
from runtime import ROOT, ENTRY, arr, unpack, struct
from runtime_store import call, branch, combine, STR
from runtime_world import ACTOR, SCENE, SMC, PRIMITIVE, PROP, WORLD, RECORD, MESH, set_value, validity
from runtime_session import prop, method
from runtime_apply import get

PICKER=ROOT+'BP_DenPicker'
FACT=ROOT+'ST_DenPick'
OBJECT='/Script/CoreUObject.Object'
COMP='/Script/Engine.ActorComponent'
SCRIPTED=['_Gameplay.','_Cinematics.','/CIN_','Narrative','/Audio/','_Audio.','Lighting','/LGT_','SpaceTravel','Hyperspace']
STRUCTURE=['/HQ/Structure/'+p+'/' for p in ['Girder','Ceilings','Pipes','Supports','_GENERATED']]+['/SWAL_Fixtures/Ceiling','/Vehicles/Dropship/','/Structures/DocksUnderground/']
FLOORS=['/Floors/','/REP_Floors/','/UndergroundFloors/','/IndustrialFloors/','/SWAL_Fixtures/Floor']
WALLS=['/Walls/','/REP_Walls/','/UndergroundWalls/','/IndustrialWalls/','/SWAL_Fixtures/Wall']


def contains_any(g,name,value,patterns):
    return combine(g,name+'any',[call(g,name+str(i),STR+'Contains',{'SearchIn':value},Substring=p,bUseCase='true',bSearchFromEnd='false') for i,p in enumerate(patterns)],True)


def category_rule(name, folders):
    g=Graph();found=contains_any(g,'folder','entry.MeshPath',folders)
    g.wire((found,'result.Is'+name));g.chain('entry','result')
    return g.function('Is'+name,inputs=[v('MeshPath','string')],outputs=[v('Is'+name,'bool')])


def rules():
    g=Graph();g.get('reason','local:Failure');g.wire(('reason.Failure','result.Reason'))
    g.get('ok','local:AllowedResult');g.wire(('ok.AllowedResult','result.Allowed'))
    def reject(name,condition,message,previous):
        branch(g,name,condition);g.set(name+'text','local:Failure',message);g.chain(previous,name,name+'text','result');return name+'.else'
    floor=contains_any(g,'floor','entry.MeshPath',FLOORS)
    disabled=call(g,'disabled',KML+':Not_PreBool',{'A':'entry.SelectFloors'})
    previous=reject('floorblocked',combine(g,'flooroff',[floor,disabled]),'Floor selection is off. Turn Floors on in the toolbar.','entry')
    wall=contains_any(g,'wall','entry.MeshPath',WALLS)
    walls_disabled=call(g,'wallsdisabled',KML+':Not_PreBool',{'A':'entry.SelectWalls'})
    previous=reject('wallblocked',combine(g,'walloff',[wall,walls_disabled]),'Wall selection is off. Turn Walls on in the toolbar.',previous)
    branch(g,'placed','entry.Managed');g.set('yes','local:AllowedResult','true');g.chain(previous,'placed','yes','result');previous='placed.else'
    for name,pin,message in [('pawn','entry.Pawn','Characters cannot be edited.'),('foreign','entry.Foreign','Another mod added this; edit it there.'),('scripted',contains_any(g,'script','entry.LevelPath',SCRIPTED),'The game uses this for its story or gameplay.'),('interactive','entry.Interactive','Interactive objects cannot be edited.'),('instance','entry.Instanced','Instanced meshes cannot be edited yet.')]:
        previous=reject(name,pin,message,previous)
    large=call(g,'large',KML+':Greater_DoubleDouble',{'A':'entry.Size'},B=800)
    locked=call(g,'locked',KML+':Not_PreBool',{'A':'entry.EditStructure'})
    structure=combine(g,'structure',[contains_any(g,'structurepath','entry.MeshPath',STRUCTURE),large],True)
    # Category switches take precedence over both structural paths and large bounds.
    other=call(g,'othercategory',KML+':Not_PreBool',{'A':combine(g,'category',[floor,wall],True)})
    previous=reject('protected',combine(g,'protectedcheck',[locked,structure,other]),'Structure editing is off. Turn Structure on in the toolbar.',previous)
    g.chain(previous,'yes')
    return g.function('CheckRules',inputs=[v('MeshPath','string'),v('LevelPath','string'),v('Size','double'),*[v(n,'bool') for n in ['Managed','Pawn','Foreign','Interactive','Instanced','EditStructure','SelectFloors','SelectWalls']]],outputs=[v('Allowed','bool'),v('Reason','string')],locals=[v('AllowedResult','bool','false'),v('Failure','string')])


def selection_key():
    g=Graph();path=call(g,'path',KSL+':GetPathName',{'Object':'entry.Target'});set_value(g,'initial','local:Identity',path)
    records=prop(g,'records',WORLD,'Records','entry.Manager');arr(g,'len','Length',records);g.get('i','local:Cursor')
    branch(g,'loop',call(g,'within',KML+':Less_IntInt',{'A':'i.Cursor','B':'len.ReturnValue'}))
    arr(g,'record','Get',records);g.wire(('i.Cursor','record.Index'));branch(g,'valid',validity(g,'check','record.Item'))
    target=prop(g,'target',RECORD,'Target','record.Item');branch(g,'same',call(g,'equal',KML+':EqualEqual_ObjectObject',{'A':target,'B':'entry.Target'}))
    key=prop(g,'key',RECORD,'LayoutKey','record.Item');set_value(g,'alias','local:Identity',key)
    set_value(g,'next','local:Cursor',call(g,'increment',KML+':Add_IntInt',{'A':'i.Cursor'},B=1))
    g.get('value','local:Identity');g.wire(('value.Identity','result.Key'))
    g.chain('entry','initial','loop','valid','same','alias','result');g.chain('loop.else','result');g.chain('valid.else','next','loop');g.chain('same.else','next')
    return g.function('SelectionKey',inputs=[v('Manager','object:'+WORLD),v('Target','object:'+OBJECT)],outputs=[v('Key','string')],locals=[v('Identity','string'),v('Cursor','int','0')])


def classify():
    g=Graph();locals_=[v('Accepted','bool','false'),v('Failure','string','Only visible static-mesh props in this Den can be edited.'),v('PickedComponent','object:'+SMC),v('PickedTarget','object:'+OBJECT),v('PickedKind','int','2'),v('PickedKey','string'),v('PickedMesh','string'),v('PickedLabel','string'),v('IsManaged','bool','false'),v('IsPawn','bool','false'),v('IsInstanced','bool','false')]
    branch(g,'valid',combine(g,'validrefs',[validity(g,'componentvalid','entry.Component'),validity(g,'managervalid','entry.Manager')]))
    owner=call(g,'owner',COMP+':GetOwner',{'self':'entry.Component'});branch(g,'ownerok',validity(g,'ownercheck',owner))
    hidden=prop(g,'hidden',ACTOR,'bHidden',owner)
    visible=call(g,'visible',SCENE+':IsVisible',{'self':'entry.Component'})
    branch(g,'visiblecheck',combine(g,'visibleboth',[visible,call(g,'nothidden',KML+':Not_PreBool',{'A':hidden})]))
    g.node('pawn','cast',**{'class':'/Script/Engine.Pawn'});g.wire((owner,'pawn.Object'))
    g.set('pawnreason','local:Failure','Characters cannot be edited.')
    g.node('mesh','cast',**{'class':SMC});g.wire(('entry.Component','mesh.Object'))
    set_value(g,'component','local:PickedComponent','mesh.AsStatic Mesh Component')
    asset=prop(g,'asset',SMC,'StaticMesh','mesh.AsStatic Mesh Component');branch(g,'assetvalid',validity(g,'assetcheck',asset))
    assetpath=call(g,'assetpath',KSL+':GetPathName',{'Object':asset});set_value(g,'meshpath','local:PickedMesh',assetpath)
    label=call(g,'label',KSL+':GetObjectName',{'Object':asset});set_value(g,'labelsave','local:PickedLabel',label)
    g.node('placed','cast',**{'class':PROP});g.wire((owner,'placed.Object'))
    managed=prop(g,'managed',WORLD,'Placed','entry.Manager');arr(g,'containsplaced','Contains',managed);g.wire(('placed.AsBP Den Placed Prop','containsplaced.ItemToFind'))
    branch(g,'ours','containsplaced.ReturnValue');g.set('managedflag','local:IsManaged','true');g.set('placedkind','local:PickedKind','0')
    current=prop(g,'current',PROP,'Current','placed.AsBP Den Placed Prop');unpack(g,'currentvalue',ENTRY,current)
    set_value(g,'placedkey','local:PickedKey','currentvalue.Key');set_value(g,'placedtarget','local:PickedTarget',owner)
    actors=prop(g,'actors',WORLD,'WorldActors','entry.Manager');arr(g,'inworld','Contains',actors);g.wire((owner,'inworld.ItemToFind'));branch(g,'worldcheck','inworld.ReturnValue')
    g.node('instance','cast',**{'class':'/Script/Engine.InstancedStaticMeshComponent'});g.wire(('entry.Component','instance.Object'));g.set('instancedflag','local:IsInstanced','true')
    g.node('unit','sequence',outputs=1)
    g.node('staticactor','cast',**{'class':'/Script/Engine.StaticMeshActor'});g.wire((owner,'staticactor.Object'))
    root=call(g,'root',ACTOR+':K2_GetRootComponent',{'self':owner})
    branch(g,'isroot',call(g,'rootmatch',KML+':EqualEqual_ObjectObject',{'A':root,'B':'entry.Component'}))
    set_value(g,'actortarget','local:PickedTarget',owner);set_value(g,'comptarget','local:PickedTarget','entry.Component')
    g.get('target','local:PickedTarget');g.call('identity','self:SelectionKey');g.wire(('entry.Manager','identity.Manager'),('target.PickedTarget','identity.Target'));set_value(g,'savekey','local:PickedKey','identity.Key')
    componentpath=call(g,'componentpath',KSL+':GetPathName',{'Object':'entry.Component'})
    call(g,'level',STR+'Split',{'SourceString':componentpath},InStr=':PersistentLevel',SearchCase='CaseSensitive',SearchDir='FromStart')
    ownerpath=call(g,'ownerpath',KSL+':GetPathName',{'Object':owner})
    plain=call(g,'plain',KML+':EqualEqual_ClassClass',{'A':call(g,'class',GS+':GetObjectClass',{'Object':owner})},B=ACTOR)
    persistent=call(g,'persistent',STR+'Contains',{'SearchIn':ownerpath},Substring='/HUB_Root.HUB_Root:PersistentLevel.',bUseCase='true')
    interactive=call(g,'interactive',ACTOR+':GetComponentByClass',{'self':owner},ComponentClass='/Script/BitReactorGame.InteractableComponent')
    call(g,'bounds',KSL+':GetComponentBounds',{'Component':'entry.Component'})
    extent=call(g,'extent',KML+':Vector_GetAbsMax',{'A':'bounds.BoxExtent'});size=call(g,'size',KML+':Multiply_DoubleDouble',{'A':extent},B=2)
    g.get('managedflagget','local:IsManaged');g.get('instancedget','local:IsInstanced')
    g.call('rules','self:CheckRules');g.wire((assetpath,'rules.MeshPath'),('level.LeftS','rules.LevelPath'),(size,'rules.Size'),('managedflagget.IsManaged','rules.Managed'),('instancedget.IsInstanced','rules.Instanced'),(combine(g,'foreign',[plain,persistent]),'rules.Foreign'),(validity(g,'interactivevalid',interactive),'rules.Interactive'),('entry.EditStructure','rules.EditStructure'),('entry.SelectFloors','rules.SelectFloors'),('entry.SelectWalls','rules.SelectWalls'))
    set_value(g,'allowed','local:Accepted','rules.Allowed');set_value(g,'reason','local:Failure','rules.Reason')
    g.node('fact','make_struct',struct=FACT)
    for local,field in [('Accepted','Allowed'),('Failure','Reason'),('PickedComponent','Component'),('PickedTarget','Target'),('PickedKind','Kind'),('PickedKey','Key'),('PickedMesh','Mesh'),('PickedLabel','Label')]:
        g.get('out'+field,'local:'+local);g.wire(('out'+field+'.'+local,'fact.'+field))
    g.wire(('fact.ST_DenPick','result.Facts'))
    g.chain('entry','valid','ownerok','visiblecheck','pawn','pawnreason','result');g.chain('pawn.CastFailed','mesh','component','assetvalid','meshpath','labelsave','placed','ours','managedflag','placedkind','placedkey','placedtarget','rules','allowed','reason','result')
    g.chain('placed.CastFailed','worldcheck','instance','instancedflag','unit');g.chain('ours.else','worldcheck');g.chain('instance.CastFailed','unit');g.chain('unit.then_0','staticactor','isroot','actortarget','identity','savekey','rules');g.chain('staticactor.CastFailed','comptarget','identity');g.chain('isroot.else','comptarget')
    for pin in ['valid.else','ownerok.else','visiblecheck.else','mesh.CastFailed','assetvalid.else','worldcheck.else']:g.chain(pin,'result')
    return g.function('Classify',inputs=[v('Manager','object:'+WORLD),v('Component','object:'+PRIMITIVE),v('EditStructure','bool'),v('SelectFloors','bool'),v('SelectWalls','bool')],outputs=[v('Facts','struct:'+FACT)],locals=locals_)


def needs_bounds():
    g=Graph();branch(g,'componentvalid',validity(g,'componentcheck','entry.Component'))
    mesh=prop(g,'mesh',SMC,'StaticMesh','entry.Component');branch(g,'meshvalid',validity(g,'meshcheck',mesh))
    body=prop(g,'body',MESH,'BodySetup',mesh);branch(g,'hasbody',validity(g,'bodyvalid',body))
    flag=prop(g,'traceflag','/Script/PhysicsCore.BodySetupCore','CollisionTraceFlag',body)
    # CTF_UseSimpleAsComplex is 2; complex-only collision may legitimately
    # return a negative closest-point distance, and must keep its holes.
    branch(g,'simple',call(g,'simpleonly',KML+':EqualEqual_ByteByte',{'A':flag},B=2))
    position=call(g,'position',SCENE+':K2_GetComponentLocation',{'self':'entry.Component'})
    distance=call(g,'closest',PRIMITIVE+':GetClosestPointOnCollision',{'self':'entry.Component','Point':position},BoneName='None')
    branch(g,'missing',call(g,'negative',KML+':Less_DoubleDouble',{'A':distance},B=0))
    g.set('yes','local:UseBounds','true');g.get('value','local:UseBounds');g.wire(('value.UseBounds','result.Needed'))
    g.chain('entry','componentvalid','meshvalid','hasbody','simple','missing','yes','result');g.chain('hasbody.else','yes')
    for pin in ['componentvalid.else','meshvalid.else','simple.else','missing.else']:g.chain(pin,'result')
    return g.function('NeedsBounds',inputs=[v('Component','object:'+SMC)],outputs=[v('Needed','bool')],locals=[v('UseBounds','bool','false')])


def specs():
    from runtime_pick_query import variables,functions
    yield '18a_ST_DenPick',struct(FACT,[v('Allowed','bool'),v('Reason','string'),v('Component','object:'+SMC),v('Target','object:'+OBJECT),v('Kind','int','2'),v('Key','string'),v('Mesh','string'),v('Label','string')])
    yield '18b_BP_DenPicker',dict(kind='blueprint',path=PICKER,parent=OBJECT,variables=variables(),functions=[category_rule('Floor',FLOORS),category_rule('Wall',WALLS),rules(),selection_key(),classify(),needs_bounds(),ray_box(),component_box(),*functions()])


def ray_box():
    """Slab intersection; direction need not be normalized (t is preserved)."""
    g=Graph();offset=call(g,'offset',KML+':Subtract_VectorVector',{'A':'entry.Origin','B':'entry.Center'})
    for name,pin in [('p',offset),('d','entry.Direction'),('e','entry.Extent')]:call(g,name,KML+':BreakVector',{'InVec':pin})
    set_value(g,'limit','local:FarT','entry.Limit');previous='limit'
    for axis in ['X','Y','Z']:
        p='p.'+axis;q='d.'+axis;e='e.'+axis;name=axis.lower()
        absq=call(g,name+'absq',KML+':Abs',{'A':q})
        branch(g,name+'parallel',call(g,name+'parallelcheck',KML+':Less_DoubleDouble',{'A':absq},B=1e-8))
        absp=call(g,name+'absp',KML+':Abs',{'A':p})
        branch(g,name+'inside',call(g,name+'insidecheck',KML+':LessEqual_DoubleDouble',{'A':absp,'B':e}))
        negative=call(g,name+'negative',KML+':Multiply_DoubleDouble',{'A':e},B=-1)
        low=call(g,name+'low',KML+':Subtract_DoubleDouble',{'A':negative,'B':p});high=call(g,name+'high',KML+':Subtract_DoubleDouble',{'A':e,'B':p})
        a=call(g,name+'a',KML+':Divide_DoubleDouble',{'A':low,'B':q});b=call(g,name+'b',KML+':Divide_DoubleDouble',{'A':high,'B':q})
        lo=call(g,name+'min',KML+':FMin',{'A':a,'B':b});hi=call(g,name+'max',KML+':FMax',{'A':a,'B':b})
        g.get(name+'near','local:NearT');g.get(name+'far','local:FarT')
        near=call(g,name+'newnear',KML+':FMax',{'A':name+'near.NearT','B':lo});far=call(g,name+'newfar',KML+':FMin',{'A':name+'far.FarT','B':hi})
        set_value(g,name+'setnear','local:NearT',near);set_value(g,name+'setfar','local:FarT',far)
        branch(g,name+'overlap',call(g,name+'overlapcheck',KML+':LessEqual_DoubleDouble',{'A':name+'near.NearT','B':name+'far.FarT'}))
        g.node(name+'next','sequence',outputs=1)
        g.chain(previous,name+'parallel',name+'inside',name+'next');g.chain(name+'inside.else','result')
        g.chain(name+'parallel.else',name+'setnear',name+'setfar',name+'overlap',name+'next');g.chain(name+'overlap.else','result')
        previous=name+'next.then_0'
    g.get('near','local:NearT')
    front=call(g,'front',KML+':Greater_DoubleDouble',{'A':'near.NearT'},B=0)
    inrange=call(g,'inrange',KML+':LessEqual_DoubleDouble',{'A':'near.NearT','B':'entry.Limit'})
    branch(g,'hit',combine(g,'hitcheck',[front,inrange]));g.set('yes','local:Found','true')
    g.get('found','local:Found');g.wire(('found.Found','result.Hit'),('near.NearT','result.Distance'))
    g.chain('entry','limit');g.chain(previous,'hit','yes','result');g.chain('hit.else','result')
    return g.function('RayBox',inputs=[v('Origin','vector'),v('Direction','vector'),v('Center','vector'),v('Extent','vector'),v('Limit','double')],outputs=[v('Hit','bool'),v('Distance','double')],locals=[v('NearT','double','-1e20'),v('FarT','double'),v('Found','bool','false')])


def component_box():
    g=Graph();branch(g,'valid',validity(g,'validcomponent','entry.Component'))
    mesh=prop(g,'mesh',SMC,'StaticMesh','entry.Component');branch(g,'meshvalid',validity(g,'meshcheck',mesh))
    xf=call(g,'transform',SCENE+':K2_GetComponentToWorld',{'self':'entry.Component'})
    origin=call(g,'origin',KML+':InverseTransformLocation',{'T':xf,'Location':'entry.Origin'})
    endpoint=call(g,'endpoint',KML+':Add_VectorVector',{'A':'entry.Origin','B':'entry.Direction'})
    localend=call(g,'localend',KML+':InverseTransformLocation',{'T':xf,'Location':endpoint})
    direction=call(g,'direction',KML+':Subtract_VectorVector',{'A':localend,'B':origin})
    bounds=call(g,'bounds',MESH+':GetBounds',{'self':mesh});call(g,'box',KML+':BreakBoxSphereBounds',{'InBoxSphereBounds':bounds})
    g.call('ray','self:RayBox');g.wire((origin,'ray.Origin'),(direction,'ray.Direction'),('box.Origin','ray.Center'),('box.BoxExtent','ray.Extent'),('entry.Limit','ray.Limit'))
    set_value(g,'hit','local:Found','ray.Hit');set_value(g,'distance','local:HitDistance','ray.Distance')
    g.get('found','local:Found');g.get('dist','local:HitDistance');g.wire(('found.Found','result.Hit'),('dist.HitDistance','result.Distance'))
    g.chain('entry','valid','meshvalid','ray','hit','distance','result');g.chain('valid.else','result');g.chain('meshvalid.else','result')
    return g.function('ComponentBox',inputs=[v('Component','object:'+SMC),v('Origin','vector'),v('Direction','vector'),v('Limit','double')],outputs=[v('Hit','bool'),v('Distance','double')],locals=[v('Found','bool','false'),v('HitDistance','double')])
