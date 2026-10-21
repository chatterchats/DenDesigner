"""Cooked gizmo geometry with native ProceduralMeshComponent rendering.

The controller supplies an asynchronously loaded material. BuildStep creates one
section per tick, never loads assets and never touches layout state.
"""
import json
from pathlib import Path
from graph import Graph, variable as v, KML
from runtime import ROOT
from runtime_store import call, branch, combine
from runtime_world import ACTOR, MATERIAL, set_value, validity, finish_bool, vector_valid
from runtime_apply import get, bump

VISUAL=ROOT+'BP_DenGizmoVisual'
PMC='/Script/ProceduralMeshComponent.ProceduralMeshComponent'
MESH_COMPONENT='/Script/Engine.MeshComponent'
OVERLAY='/Engine/EditorMaterials/WidgetVertexColorMaterial.WidgetVertexColorMaterial'
MODES={'move':1,'rotate':2,'scale':3}
KINDS={'axis':1,'plane':2,'ring':3,'uniform':4}


def geometry():
    return json.loads((Path(__file__).resolve().parents[1]/'data/gizmo_geometry.json').read_text())


def tuple_text(values):
    return '('+','.join(values)+')'


def vector_text(value):
    return '('+','.join(f'{axis}={value[axis]:.9g}' for axis in ['X','Y','Z'])+')'


def variables(data):
    out=[v('GizmoMaterial','object:'+MATERIAL),v('BuildRequested','bool'),v('Ready','bool'),
         v('SectionCursor','int'),v('LastMode','int','-1'),v('LastHoverKind','int','-1'),v('LastHoverAxis','int','-1')]
    for i,handle in enumerate(data['handles']):
        section=handle['section'];name='Shape'+str(i)
        out += [v(name+'Vertices','vector[]',tuple_text([vector_text(p) for p in section['v']])),
                v(name+'Triangles','int[]',tuple_text([str(x) for x in section['t']]))]
        rgb=data['uniform'] if handle['kind']=='uniform' else data['colors'][handle['axis']-1]
        alpha=data['plane_alpha'] if handle['kind']=='plane' else data['alpha']
        for suffix,color in [('Normal',rgb),('Hover',data['hover'])]:
            value='('+','.join(f'{channel}={component:.9g}' for channel,component in zip('RGBA',[*color,alpha]))+')'
            out.append(v(name+suffix,'color[]',tuple_text([value]*len(section['v']))))
    return out


def begin_build():
    g=Graph();unused=call(g,'unused',KML+':Not_PreBool',{'A':get(g,'BuildRequested')})
    branch(g,'valid',combine(g,'validrequest',[unused,validity(g,'materialvalid','entry.Material')]))
    set_value(g,'material','GizmoMaterial','entry.Material');g.set('request','BuildRequested','true')
    call(g,'hide',ACTOR+':SetActorHiddenInGame',bNewHidden='true')
    call(g,'collision','/Script/Engine.PrimitiveComponent:SetCollisionEnabled',{'self':get(g,'Mesh')},NewType='NoCollision')
    call(g,'tick',ACTOR+':SetActorTickEnabled',bEnabled='true')
    g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','valid','material','request','hide','collision','tick','yes','result');g.chain('valid.else','result')
    return g.function('BeginBuild',inputs=[v('Material','object:'+MATERIAL)],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def build_step(data):
    g=Graph();notready=call(g,'notready',KML+':Not_PreBool',{'A':get(g,'Ready')})
    branch(g,'build',combine(g,'building',[get(g,'BuildRequested'),notready,validity(g,'materialvalid',get(g,'GizmoMaterial'))]))
    previous='build';count=len(data['handles'])*2
    for index in range(count):
        name='section'+str(index);shape='Shape'+str(index//2);hover=index%2==1
        branch(g,name,call(g,name+'matches',KML+':EqualEqual_IntInt',{'A':get(g,'SectionCursor')},B=index))
        call(g,name+'create',PMC+':CreateMeshSection_LinearColor',
             {'self':get(g,'Mesh'),'Vertices':get(g,shape+'Vertices'),'Triangles':get(g,shape+'Triangles'),
              'VertexColors':get(g,shape+('Hover' if hover else 'Normal'))},
             SectionIndex=index,bCreateCollision='false',bSRGBConversion='false')
        call(g,name+'material',MESH_COMPONENT+':SetMaterial',{'self':get(g,'Mesh'),'Material':get(g,'GizmoMaterial')},ElementIndex=index)
        call(g,name+'hide',PMC+':SetMeshSectionVisible',{'self':get(g,'Mesh')},SectionIndex=index,bNewVisibility='false')
        g.chain(previous,name,name+'create',name+'material',name+'hide','advance');previous=name+'.else'
    bump(g,'advance','SectionCursor')
    branch(g,'finished',call(g,'done',KML+':GreaterEqual_IntInt',{'A':get(g,'SectionCursor')},B=count))
    g.set('ready','Ready','true');call(g,'stop',ACTOR+':SetActorTickEnabled',bEnabled='false')
    g.chain('entry','build');g.chain('advance','finished','ready','stop')
    return g.function('BuildStep')


def hide():
    g=Graph();call(g,'hide',ACTOR+':SetActorHiddenInGame',bNewHidden='true');g.chain('entry','hide')
    return g.function('HideVisual')


def show(data):
    g=Graph();checks=[get(g,'Ready'),call(g,'modeMin',KML+':GreaterEqual_IntInt',{'A':'entry.Mode'},B=1),
        call(g,'modeMax',KML+':LessEqual_IntInt',{'A':'entry.Mode'},B=3),
        call(g,'sizeMin',KML+':Greater_DoubleDouble',{'A':'entry.Size'},B=0),
        call(g,'sizeMax',KML+':LessEqual_DoubleDouble',{'A':'entry.Size'},B=1e7),
        vector_valid(g,'center','entry.Center')]
    branch(g,'valid',combine(g,'validpose',checks));g.call('hide','self:HideVisual')
    scale=call(g,'scale',KML+':Divide_DoubleDouble',{'A':'entry.Size'},B=100)
    xyz=call(g,'xyz',KML+':MakeVector',{axis:scale for axis in ['X','Y','Z']})
    local=call(g,'local',KML+':EqualEqual_IntInt',{'A':'entry.Mode'},B=3)
    rotation=call(g,'rotation',KML+':SelectRotator',{'A':'entry.Rotation','bPickA':local},B='0,0,0')
    xf=call(g,'transform',KML+':MakeTransform',{'Location':'entry.Center','Rotation':rotation,'Scale':xyz})
    call(g,'pose',ACTOR+':K2_SetActorTransform',{'NewTransform':xf},bSweep='false',bTeleport='true')
    call(g,'unhide',ACTOR+':SetActorHiddenInGame',bNewHidden='false')
    changed=[call(g,'changed'+field,KML+':NotEqual_IntInt',{'A':'entry.'+field,'B':get(g,'Last'+field)})
             for field in ['Mode','HoverKind','HoverAxis']]
    branch(g,'changed',combine(g,'changedflags',changed,True));previous='changed'
    for i,handle in enumerate(data['handles']):
        name='shape'+str(i)
        mode=call(g,name+'mode',KML+':EqualEqual_IntInt',{'A':'entry.Mode'},B=MODES[handle['mode']])
        kind=call(g,name+'kind',KML+':EqualEqual_IntInt',{'A':'entry.HoverKind'},B=KINDS[handle['kind']])
        axis=call(g,name+'axis',KML+':EqualEqual_IntInt',{'A':'entry.HoverAxis'},B=handle.get('axis',0))
        hover=combine(g,name+'hover',[kind,axis])
        normal=call(g,name+'normal',KML+':Not_PreBool',{'A':hover})
        for k,condition in enumerate([normal,hover]):
            call(g,name+'show'+str(k),PMC+':SetMeshSectionVisible',
                 {'self':get(g,'Mesh'),'bNewVisibility':combine(g,name+'visible'+str(k),[mode,condition])},SectionIndex=i*2+k)
            g.chain(previous,name+'show'+str(k));previous=name+'show'+str(k)
    for field in ['Mode','HoverKind','HoverAxis']:
        set_value(g,'remember'+field,'Last'+field,'entry.'+field);g.chain(previous,'remember'+field);previous='remember'+field
    g.chain('entry','valid','pose','unhide','changed');g.chain('valid.else','hide')
    return g.function('ShowPose',inputs=[v('Center','vector'),v('Rotation','rotator'),v('Size','double'),v('Mode','int'),v('HoverKind','int'),v('HoverAxis','int')])


def spec():
    data=geometry();g=Graph();g.node('tick','event',name='ReceiveTick');g.call('build','self:BuildStep');g.chain('tick','build')
    return dict(kind='blueprint',path=VISUAL,parent=ACTOR,
        defaults={'PrimaryActorTick.bCanEverTick':'true','PrimaryActorTick.bStartWithTickEnabled':'false','bHidden':'true'},
        components=[dict(name='Mesh',**{'class':PMC},props={'Mobility':'Movable','BodyInstance.CollisionEnabled':'NoCollision','CastShadow':'false','bReceivesDecals':'false'})],
        variables=variables(data),graph=g.spec(),functions=[begin_build(),build_step(data),hide(),show(data)])
