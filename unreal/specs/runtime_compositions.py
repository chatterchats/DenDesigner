"""Value-only composition capture and bounded multi-selection, independent of layouts."""
import copy
from graph import Graph, variable as v, KML, KSL, GS
from runtime import ROOT, ENTRY, LAYOUT, arr, unpack, struct
from runtime_store import call, branch, combine, STR
from runtime_world import SCENE, PRIMITIVE, set_value, validity, finish_bool, valid_transform
from runtime_apply import get, clear
from runtime_session import prop, method
from runtime_pick import FACT, PICKER
from runtime_transform import copy_entry, POSE
from runtime_gizmo_controller import op, neg

PICK=ROOT+'ST_DenCompositionPick'
LIMIT=128


def types():
    yield '18c_ST_DenCompositionPick',struct(PICK,[v('Facts','struct:'+FACT),v('HadDepth','bool'),v('Stencil','int')])


def restore():
    g=Graph();unpack(g,'part',PICK,'entry.Part');unpack(g,'facts',FACT,'part.Facts')
    branch(g,'valid',validity(g,'alive','facts.Component'))
    call(g,'depth',PRIMITIVE+':SetRenderCustomDepth',{'self':'facts.Component','bValue':'part.HadDepth'})
    call(g,'stencil',PRIMITIVE+':SetCustomDepthStencilValue',{'self':'facts.Component','Value':'part.Stencil'})
    g.chain('entry','valid','depth','stencil');return g.function('RestoreCompositionOutline',inputs=[v('Part','struct:'+PICK)])


def clear_parts():
    g=Graph();g.get('i','local:Cursor');arr(g,'count','Length',get(g,'CompositionParts'));branch(g,'more',op(g,'within','Less_IntInt','i.Cursor','count.ReturnValue'))
    arr(g,'part','Get',get(g,'CompositionParts'));g.wire(('i.Cursor','part.Index'));g.call('restore','self:RestoreCompositionOutline');g.wire(('part.Item','restore.Part'))
    set_value(g,'next','local:Cursor',op(g,'advance','Add_IntInt','i.Cursor',B=1));clear(g,'clear','CompositionParts');g.set('stop','CompositionSelecting','false');g.call('labels','self:RefreshCompositionFeedback')
    g.chain('entry','more','restore','next','more');g.chain('more.else','clear','stop','labels');return g.function('ClearCompositionSelection',locals=[v('Cursor','int','0')])


def toggle_part():
    g=Graph();unpack(g,'facts',FACT,'entry.Facts');g.call('ready','self:CanEdit')
    branch(g,'active',combine(g,'available',[get(g,'CompositionSelecting'),get(g,'UIOpen'),'ready.Ready']))
    branch(g,'allowed',combine(g,'allowedcheck',['facts.Allowed',validity(g,'alive','facts.Component')]))
    arr(g,'count','Length',get(g,'CompositionParts'));g.get('i','local:Cursor');branch(g,'more',op(g,'within','Less_IntInt','i.Cursor','count.ReturnValue'))
    arr(g,'part','Get',get(g,'CompositionParts'));g.wire(('i.Cursor','part.Index'));unpack(g,'partdata',PICK,'part.Item');unpack(g,'prior',FACT,'partdata.Facts')
    branch(g,'same',combine(g,'sameidentity',[op(g,'samekind','EqualEqual_IntInt','prior.Kind','facts.Kind'),call(g,'samekey',STR+'EqualEqual_StrStr',{'A':'prior.Key','B':'facts.Key'})]))
    g.call('restore','self:RestoreCompositionOutline');g.wire(('part.Item','restore.Part'));arr(g,'remove','Remove',get(g,'CompositionParts'));g.wire(('i.Cursor','remove.IndexToRemove'))
    set_value(g,'next','local:Cursor',op(g,'advance','Add_IntInt','i.Cursor',B=1));branch(g,'room',op(g,'bounded','Less_IntInt','count.ReturnValue',B=LIMIT))
    g.node('record','make_struct',struct=PICK);g.wire(('entry.Facts','record.Facts'),(prop(g,'olddepth',PRIMITIVE,'bRenderCustomDepth','facts.Component'),'record.HadDepth'),(prop(g,'oldstencil',PRIMITIVE,'CustomDepthStencilValue','facts.Component'),'record.Stencil'))
    arr(g,'add','Add',get(g,'CompositionParts'));g.wire(('record.ST_DenCompositionPick','add.NewItem'))
    call(g,'stencil',PRIMITIVE+':SetCustomDepthStencilValue',{'self':'facts.Component'},Value=32);call(g,'depth',PRIMITIVE+':SetRenderCustomDepth',{'self':'facts.Component'},bValue='true')
    g.set('ok','CompositionMessage','Click parts to add or remove them, then name and save the composition.')
    g.set('full','CompositionMessage',f'A composition can contain at most {LIMIT} parts.')
    set_value(g,'reason','CompositionMessage','facts.Reason');g.call('labels','self:RefreshCompositionFeedback')
    g.chain('entry','ready','active','allowed','more','same','restore','remove','ok','labels');g.chain('same.else','next','more');g.chain('more.else','room','add','stencil','depth','ok');g.chain('room.else','full','labels');g.chain('allowed.else','reason','labels')
    return g.function('ToggleCompositionPart',inputs=[v('Facts','struct:'+FACT)],locals=[v('Cursor','int','0')])


def toggle_select():
    g=Graph();g.call('ready','self:CanEdit');branch(g,'allowed',combine(g,'available',['ready.Ready',get(g,'UIOpen')]))
    g.call('cancel','self:CancelPlacement');g.call('preview','self:CancelCompositionPreview');g.call('clear','self:ClearSelection');g.call('press','self:ClearSurfacePress')
    set_value(g,'toggle','CompositionSelecting',neg(g,'inverse',get(g,'CompositionSelecting')))
    g.set('message','CompositionMessage','Click props to add or remove them. Saving keeps the originals in place.');g.call('labels','self:RefreshCompositionFeedback');g.call('focus','self:FocusEditorViewport')
    g.chain('entry','ready','allowed','cancel','preview','clear','press','toggle','message','labels','focus');return g.function('ToggleCompositionSelection')


def materials():
    from runtime_copy import materials as original
    value=copy.deepcopy(original());value['name']='ReadComponentMaterials';value['inputs']=[v('Component','object:'+PRIMITIVE)]
    graph=value;graph['nodes']=[n for n in graph['nodes'] if n['id'] not in ['facts','getSelected']]
    graph['links']=[[a.replace('facts.Component','entry.Component'),b] for a,b in graph['links'] if b!='facts.ST_DenPick']
    return value


def snapshot():
    g=Graph();g.node('self','self');unpack(g,'prior',FACT,'entry.Facts')
    method(g,'check',PICKER,'Classify',get(g,'Picker'),{'Manager':'self.self','Component':'prior.Component','EditStructure':get(g,'StructureEnabled'),'SelectFloors':get(g,'FloorsEnabled'),'SelectWalls':get(g,'WallsEnabled')})
    unpack(g,'facts',FACT,'check.Facts');branch(g,'valid',combine(g,'same',['facts.Allowed',op(g,'samekind','EqualEqual_IntInt','facts.Kind','prior.Kind'),call(g,'samekey',STR+'EqualEqual_StrStr',{'A':'facts.Key','B':'prior.Key'})]))
    g.call('materials','self:ReadComponentMaterials');g.wire(('facts.Component','materials.Component'));branch(g,'materialvalid','materials.Ready')
    method(g,'read',LAYOUT,'ReadEntry',get(g,'WorkingDocument'),{'Kind':'facts.Kind','Key':'facts.Key'});unpack(g,'old',ENTRY,'read.Value')
    g.node('value','make_struct',struct=ENTRY,defaults={'Kind':'0','Key':'part','HasPosition':'true','HasRotation':'true','HasScale':'true'})
    g.wire(('facts.Mesh','value.Mesh'),('materials.Paths','value.Materials'),('old.CollisionMode','value.CollisionMode'))
    for name,_,fn in POSE:g.wire((call(g,name,SCENE+':'+fn,{'self':'facts.Component'}),'value.'+name))
    g.call('transform','self:ValidCompositionTransform');g.wire(('value.ST_DenEntry','transform.Value'));branch(g,'transformvalid','transform.Valid')
    set_value(g,'copy','local:Result','value.ST_DenEntry');g.get('valueout','local:Result');g.wire(('valueout.Result','result.Value'))
    call(g,'bounds',KSL+':GetComponentBounds',{'Component':'facts.Component'});g.wire(('bounds.Origin','result.Center'),('bounds.BoxExtent','result.Extent'))
    g.set('yes','local:OK','true');finish_bool(g,'Ready')
    g.chain('entry','check','valid','materials','materialvalid','read','transform','transformvalid','copy','yes','result')
    for pin in ['valid.else','materialvalid.else','transformvalid.else']:g.chain(pin,'result')
    return g.function('SnapshotCompositionPart',inputs=[v('Facts','struct:'+FACT)],outputs=[v('Ready','bool'),v('Value','struct:'+ENTRY),v('Center','vector'),v('Extent','vector')],locals=[v('Result','struct:'+ENTRY),v('OK','bool','false')])


def capture():
    g=Graph();arr(g,'count','Length',get(g,'CompositionParts'));branch(g,'bounded',combine(g,'size',[op(g,'min','Greater_IntInt','count.ReturnValue',B=0),op(g,'max','LessEqual_IntInt','count.ReturnValue',B=LIMIT)]))
    g.get('i','local:Cursor');g.get('rows','local:Values');branch(g,'more',op(g,'within','Less_IntInt','i.Cursor','count.ReturnValue'))
    arr(g,'part','Get',get(g,'CompositionParts'));g.wire(('i.Cursor','part.Index'));unpack(g,'partdata',PICK,'part.Item');g.call('snapshot','self:SnapshotCompositionPart');g.wire(('partdata.Facts','snapshot.Facts'));branch(g,'valid','snapshot.Ready')
    key=call(g,'key',STR+'Conv_IntToString',{'InInt':'i.Cursor'});value=copy_entry(g,'named','snapshot.Value',{'Key':key});arr(g,'append','Add','rows.Values');g.wire((value,'append.NewItem'))
    low=op(g,'low','Subtract_VectorVector','snapshot.Center','snapshot.Extent');high=op(g,'high','Add_VectorVector','snapshot.Center','snapshot.Extent')
    for name,pin in [('low',low),('high',high)]:call(g,name+'parts',KML+':BreakVector',{'InVec':pin})
    previous='append'
    for axis in ['X','Y','Z']:
        g.get('min'+axis,'local:Min'+axis);g.get('max'+axis,'local:Max'+axis)
        set_value(g,'setmin'+axis,'local:Min'+axis,op(g,'minvalue'+axis,'FMin','min'+axis+'.Min'+axis,'lowparts.'+axis));set_value(g,'setmax'+axis,'local:Max'+axis,op(g,'maxvalue'+axis,'FMax','max'+axis+'.Max'+axis,'highparts.'+axis));g.chain(previous,'setmin'+axis,'setmax'+axis);previous='setmax'+axis
    set_value(g,'next','local:Cursor',op(g,'advance','Add_IntInt','i.Cursor',B=1));g.chain(previous,'next','more')
    anchor=call(g,'anchor',KML+':MakeVector',{'X':op(g,'cx','Multiply_DoubleDouble',op(g,'sx','Add_DoubleDouble','minX.MinX','maxX.MaxX'),B=.5),'Y':op(g,'cy','Multiply_DoubleDouble',op(g,'sy','Add_DoubleDouble','minY.MinY','maxY.MaxY'),B=.5),'Z':'minZ.MinZ'})
    set_value(g,'keepanchor','local:Anchor',anchor);g.set('reset','local:Cursor','0');g.get('anchorout','local:Anchor');branch(g,'normalizing',op(g,'normalwithin','Less_IntInt','i.Cursor','count.ReturnValue'))
    arr(g,'world','Get','rows.Values');g.wire(('i.Cursor','world.Index'));unpack(g,'worlddata',ENTRY,'world.Item');localvalue=copy_entry(g,'local','world.Item',{'Position':op(g,'relative','Subtract_VectorVector','worlddata.Position','anchorout.Anchor')})
    arr(g,'replace','Set','rows.Values',bSizeToFit='false');g.wire(('i.Cursor','replace.Index'),(localvalue,'replace.Item'));set_value(g,'nextlocal','local:Cursor',op(g,'advance2','Add_IntInt','i.Cursor',B=1))
    call(g,'create',GS+':CreateSaveGameObject',SaveGameClass=LAYOUT);g.node('cast','cast',**{'class':LAYOUT});g.wire(('create.ReturnValue','cast.Object'))
    set_value(g,'entries',LAYOUT+':Entries','rows.Values');g.wire(('cast.AsBP Den Layout Save','entries.self'));g.wire(('cast.AsBP Den Layout Save','result.Document'))
    g.set('yes','local:OK','true');finish_bool(g,'Ready')
    g.chain('entry','bounded','more','snapshot','valid','append');g.chain('more.else','keepanchor','reset','normalizing','replace','nextlocal','normalizing');g.chain('normalizing.else','create','cast','entries','yes','result')
    for pin in ['bounded.else','valid.else','cast.CastFailed']:g.chain(pin,'result')
    return g.function('CaptureComposition',outputs=[v('Ready','bool'),v('Document','object:'+LAYOUT)],locals=[v('Cursor','int','0'),v('Values','struct:'+ENTRY+'[]'),v('Anchor','vector'),v('OK','bool','false')]+[v(prefix+axis,'double','1e20' if prefix=='Min' else '-1e20') for prefix in ['Min','Max'] for axis in ['X','Y','Z']])


def variables():return [v('CompositionParts','struct:'+PICK+'[]'),v('CompositionSelecting','bool')]
def functions():
    valid=valid_transform();valid['name']='ValidCompositionTransform'
    return [restore(),clear_parts(),toggle_part(),toggle_select(),materials(),snapshot(),capture(),valid]
