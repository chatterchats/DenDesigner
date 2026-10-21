"""Native duplicate/focus commands and selection after asynchronous creation."""
from graph import Graph, variable as v, KML, KSL
from runtime import ENTRY, MUTATION, LAYOUT, arr, unpack
from runtime_store import call, branch, combine, STR
from runtime_world import ACTOR, PRIMITIVE, PROP, set_value, validity, finish_bool
from runtime_apply import get
from runtime_session import prop, method
from runtime_pick import FACT, PICKER
from runtime_transform import copy_entry
from runtime_gizmo_controller import op, neg
from runtime_assets import valid_asset_path


def focus():
    g=Graph();g.call('ready','self:CanEdit');unpack(g,'facts',FACT,get(g,'Selected'))
    branch(g,'valid',combine(g,'available',['ready.Ready',get(g,'UIOpen'),get(g,'HasSelection'),neg(g,'idle',get(g,'DragActive')),validity(g,'rig',get(g,'EditorRig')),validity(g,'component','facts.Component')]))
    call(g,'bounds',KSL+':GetComponentBounds',{'Component':'facts.Component'})
    radius=op(g,'radius','VSize','bounds.BoxExtent');distance=op(g,'distance','FMax',op(g,'margin','Multiply_DoubleDouble',radius,B=2.5),B=150)
    forward=call(g,'forward',ACTOR+':GetActorForwardVector',{'self':get(g,'EditorRig')})
    at=op(g,'at','Subtract_VectorVector','bounds.Origin',op(g,'offset','Multiply_VectorFloat',forward,distance))
    call(g,'move',ACTOR+':K2_SetActorLocation',{'self':get(g,'EditorRig'),'NewLocation':at},bSweep='false',bTeleport='true')
    g.call('press','self:ClearSurfacePress');g.chain('entry','ready','valid','press','move');return g.function('FocusSelection')


def fresh_key():
    g=Graph();branch(g,'doc',validity(g,'valid',get(g,'WorkingDocument')))
    guid=call(g,'guid','/Script/Engine.KismetGuidLibrary:NewGuid');identity=call(g,'identity','/Script/Engine.KismetGuidLibrary:Conv_GuidToString',{'InGuid':guid})
    key=call(g,'prefix',STR+'Concat_StrStr',{'B':identity},A='p_');set_value(g,'capture','local:Candidate',key);g.get('candidate','local:Candidate')
    for name,kind in [('placed',0),('stored',1)]:method(g,name,LAYOUT,'FindEntry',get(g,'WorkingDocument'),{'Key':'candidate.Candidate'},Kind=kind)
    free=combine(g,'free',[op(g,n+'free','Less_IntInt',n+'.Index',B=0) for n in ['placed','stored']]);branch(g,'unused',free)
    set_value(g,'found','local:ResultKey','candidate.Candidate');g.get('output','local:ResultKey');g.wire(('output.ResultKey','result.Key'))
    g.get('attempts','local:Attempts');set_value(g,'advance','local:Attempts',op(g,'attemptnext','Add_IntInt','attempts.Attempts',B=1));branch(g,'retry',op(g,'limit','Less_IntInt','attempts.Attempts',B=8))
    g.chain('entry','doc','capture','placed','stored','unused','found','result');g.chain('unused.else','advance','retry','capture');g.chain('retry.else','result');g.chain('doc.else','result')
    return g.function('NewPlacedKey',outputs=[v('Key','string')],locals=[v('Candidate','string'),v('ResultKey','string'),v('Attempts','int','0')])


def materials():
    g=Graph();unpack(g,'facts',FACT,get(g,'Selected'));branch(g,'component',validity(g,'valid','facts.Component'))
    count=call(g,'count',PRIMITIVE+':GetNumMaterials',{'self':'facts.Component'});branch(g,'bounded',op(g,'limit','LessEqual_IntInt',count,B=256))
    g.get('index','local:Cursor');branch(g,'more',op(g,'remaining','Less_IntInt','index.Cursor',count))
    material=call(g,'material',PRIMITIVE+':GetMaterial',{'self':'facts.Component','ElementIndex':'index.Cursor'});branch(g,'validmaterial',validity(g,'materialvalid',material))
    path=call(g,'path',KSL+':GetPathName',{'Object':material});g.call('validate','self:ValidAssetPath');g.wire((path,'validate.Path'))
    transient=call(g,'transient',STR+'StartsWith',{'SourceString':path},InPrefix='/Engine/Transient')
    branch(g,'stable',combine(g,'stablepath',['validate.Valid',neg(g,'nottransient',transient)]))
    g.get('values','local:MaterialPaths');arr(g,'append','Add','values.MaterialPaths');g.wire((path,'append.NewItem'));arr(g,'empty','Add','values.MaterialPaths')
    set_value(g,'next','local:Cursor',op(g,'increment','Add_IntInt','index.Cursor',B=1));g.set('yes','local:OK','true');finish_bool(g,'Ready');g.wire(('values.MaterialPaths','result.Paths'))
    g.chain('entry','component','bounded','more','validmaterial','validate','stable','append','next','more');g.chain('validmaterial.else','empty','next');g.chain('stable.else','empty');g.chain('more.else','yes','result');g.chain('component.else','result');g.chain('bounded.else','result')
    return g.function('ReadCopyMaterials',outputs=[v('Ready','bool'),v('Paths','string[]')],locals=[v('Cursor','int','0'),v('MaterialPaths','string[]'),v('OK','bool','false')])


def duplicate():
    g=Graph();g.call('ready','self:CanEdit');branch(g,'available',combine(g,'availablecheck',['ready.Ready',get(g,'UIOpen'),neg(g,'idle',get(g,'DragActive')),validity(g,'rigvalid',get(g,'EditorRig'))]))
    g.call('read','self:ReadSelectionState');branch(g,'selected','read.Ready');unpack(g,'facts',FACT,get(g,'Selected'));unpack(g,'base',ENTRY,'read.Value')
    g.call('key','self:NewPlacedKey');branch(g,'keyvalid',call(g,'nonempty',STR+'NotEqual_StrStr',{'A':'key.Key'},B=''))
    branch(g,'native',op(g,'isnative','EqualEqual_IntInt','facts.Kind',B=2))
    g.call('materials','self:ReadCopyMaterials');branch(g,'materialsready','materials.Ready');set_value(g,'nativepaths','local:CopyMaterials','materials.Paths')
    set_value(g,'placedpaths','local:CopyMaterials','base.Materials');g.get('paths','local:CopyMaterials')
    call(g,'bounds',KSL+':GetComponentBounds',{'Component':'facts.Component'});call(g,'extent',KML+':BreakVector',{'InVec':'bounds.BoxExtent'})
    gap=op(g,'gap','Add_DoubleDouble',op(g,'diameter','Multiply_DoubleDouble',op(g,'width','FMax','extent.X','extent.Y'),B=2),B=10)
    rot=call(g,'rot',ACTOR+':K2_GetActorRotation',{'self':get(g,'EditorRig')});call(g,'rotation',KML+':BreakRotator',{'InRot':rot})
    right=call(g,'right',KML+':RotateAngleAxis',{'AngleDeg':'rotation.Yaw'},InVect='0,1,0',Axis='0,0,1')
    position=op(g,'position','Add_VectorVector','read.Position',op(g,'offset','Multiply_VectorFloat',right,gap))
    source=call(g,'source',KML+':SelectString',{'A':'facts.Key','B':'base.Source','bPickA':'isnative.ReturnValue'})
    value=copy_entry(g,'copy','read.Value',{'Key':'key.Key','Mesh':'facts.Mesh','Position':position,'Rotation':'read.Rotation','Scale':'read.Scale','Materials':'paths.CopyMaterials','Source':source},defaults={'Kind':'0','Hidden':'false','HasPosition':'true','HasRotation':'true','HasScale':'true'})
    g.node('mutation','make_struct',struct=MUTATION,defaults={'Present':'true'});g.wire((value,'mutation.Value'));g.get('mutations','local:CopyMutations');arr(g,'append','Add','mutations.CopyMutations');g.wire(('mutation.ST_DenMutation','append.NewItem'))
    g.call('commit','self:CommitEdit',Label='Copy');g.wire(('mutations.CopyMutations','commit.Mutations'));branch(g,'accepted','commit.Accepted')
    set_value(g,'pending','PendingCopyKey','key.Key');set_value(g,'sourcekey','CopySourceKey','facts.Key');set_value(g,'sourcekind','CopySourceKind','facts.Kind')
    g.set('clear','SelectionMessage','');g.set('failure','SelectionMessage','This prop could not be copied. Its material list is too large.')
    g.chain('entry','ready','available','read','selected','key','keyvalid','native','materials','materialsready','nativepaths','append','commit','accepted','pending','sourcekey','sourcekind','clear');g.chain('native.else','placedpaths','append');g.chain('materialsready.else','failure')
    return g.function('DuplicateSelection',locals=[v('CopyMaterials','string[]'),v('CopyMutations','struct:'+MUTATION+'[]')])


def select_copy():
    g=Graph();g.node('self','self');branch(g,'pending',call(g,'haspending',STR+'NotEqual_StrStr',{'A':get(g,'PendingCopyKey')},B=''))
    unpack(g,'source',FACT,get(g,'Selected'))
    samekey=call(g,'samekey',STR+'EqualEqual_StrStr',{'A':'source.Key','B':get(g,'CopySourceKey')});samekind=op(g,'samekind','EqualEqual_IntInt','source.Kind',get(g,'CopySourceKind'))
    source_matches=combine(g,'source_matches',[get(g,'HasSelection'),samekey,samekind])
    placement_matches=combine(g,'placement_matches',[op(g,'placement_kind','EqualEqual_IntInt',get(g,'CopySourceKind'),B=-1),neg(g,'no_selection',get(g,'HasSelection'))])
    branch(g,'context',combine(g,'contextcheck',[get(g,'UIOpen'),combine(g,'source_context',[source_matches,placement_matches],True),validity(g,'pickervalid',get(g,'Picker'))]));g.call('ready','self:CanEdit');branch(g,'readycheck','ready.Ready')
    g.call('find','self:FindPlaced');g.wire((get(g,'PendingCopyKey'),'find.Key'));branch(g,'found',op(g,'exists','GreaterEqual_IntInt','find.Index',B=0))
    arr(g,'actor','Get',get(g,'Placed'));g.wire(('find.Index','actor.Index'));branch(g,'alive',validity(g,'actorvalid','actor.Item'))
    component=prop(g,'component',PROP,'Mesh','actor.Item');method(g,'classify',PICKER,'Classify',get(g,'Picker'),{'Manager':'self.self','Component':component,'EditStructure':get(g,'StructureEnabled'),'SelectFloors':get(g,'FloorsEnabled'),'SelectWalls':get(g,'WallsEnabled')})
    # Cache before AcceptSelection updates any transient state.
    set_value(g,'cache','local:CopyFacts','classify.Facts');g.get('facts','local:CopyFacts');g.call('accept','self:AcceptSelection');g.wire(('facts.CopyFacts','accept.Facts'))
    g.set('clear','PendingCopyKey','');g.set('clearidentity','CopySourceKey','')
    g.chain('entry','pending','context','ready','readycheck','find','found','alive','classify','cache','accept','clear','clearidentity')
    for pin in ['context.else','found.else','alive.else']:g.chain(pin,'clear')
    return g.function('PollCopiedSelection',locals=[v('CopyFacts','struct:'+FACT)])


def variables():return [v('PendingCopyKey','string'),v('CopySourceKey','string'),v('CopySourceKind','int')]
def functions():return [valid_asset_path(),focus(),fresh_key(),materials(),duplicate(),select_copy()]
