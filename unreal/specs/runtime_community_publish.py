"""Bounded composition values; connection credentials never enter this document."""
from graph import Graph, variable as v, KML
from runtime import LAYOUT, ENTRY, arr, unpack
from runtime_store import call, branch, combine, STR
from runtime_world import set_value, finish_bool, validity
from runtime_apply import get
from runtime_session import prop, method
from runtime_layout_ui import PRESETS
from runtime_catalog_ui import ITEM
from runtime_thumbnails import filename
from runtime_gizmo_controller import op

def serialize():
    g=Graph();branch(g,'document',validity(g,'doc','entry.Document'))
    rows=prop(g,'rows',LAYOUT,'Entries','entry.Document');arr(g,'count','Length',rows)
    branch(g,'countvalid',combine(g,'countchecks',[op(g,'min','Greater_IntInt','count.ReturnValue',B=0),op(g,'max','LessEqual_IntInt','count.ReturnValue',B=128)]))
    g.get('i','local:Cursor');g.get('json','local:Accumulator');branch(g,'more',op(g,'within','Less_IntInt','i.Cursor','count.ReturnValue'))
    arr(g,'part','Get',rows);g.wire(('i.Cursor','part.Index'));unpack(g,'data',ENTRY,'part.Item')
    g.call('mesh','self:ValidAssetPath');g.wire(('data.Mesh','mesh.Path'));branch(g,'supported','mesh.Valid')
    g.call('valid','self:ValidCompositionTransform');g.wire(('part.Item','valid.Value'));branch(g,'validpart','valid.Valid')
    comma=call(g,'comma',KML+':SelectString',{'bPickA':op(g,'first','EqualEqual_IntInt','i.Cursor',B=0)},A='',B=',')
    chunks=[comma,'{"Mesh":"','data.Mesh','","Position":[']
    for field,pins,fn in [('Position',['X','Y','Z'],'BreakVector'),('Rotation',['Pitch','Yaw','Roll'],'BreakRotator'),('Scale',['X','Y','Z'],'BreakVector')]:
        call(g,'break'+field,KML+':'+fn,{'InRot' if field=='Rotation' else 'InVec':'data.'+field})
        if field!='Position':chunks += ['],"'+field+'":[']
        for index,pin in enumerate(pins):
            if index:chunks += [',']
            chunks += [call(g,field+pin,STR+'Conv_DoubleToString',{'InDouble':'break'+field+'.'+pin})]
    chunks += ['],"CollisionMode":',call(g,'collision',STR+'Conv_IntToString',{'InInt':'data.CollisionMode'}),',"Materials":[']
    expression='json.Accumulator'
    for index,chunk in enumerate(chunks):
        args={'A':expression};defaults={}
        if chunk.endswith('.ReturnValue') or chunk=='data.Mesh':args['B']=chunk
        else:defaults['B']=chunk
        expression=call(g,'concat'+str(index),STR+'Concat_StrStr',args,**defaults)
    set_value(g,'append','local:Accumulator',expression)
    g.set('resetmaterial','local:PublishMaterialIndex','0');g.get('mi','local:PublishMaterialIndex');g.get('mjson','local:Accumulator');arr(g,'materialcount','Length','data.Materials')
    branch(g,'materialmore',op(g,'materialwithin','Less_IntInt','mi.PublishMaterialIndex','materialcount.ReturnValue'))
    arr(g,'material','Get','data.Materials');g.wire(('mi.PublishMaterialIndex','material.Index'));g.call('materialpath','self:ValidAssetPath');g.wire(('material.Item','materialpath.Path'))
    branch(g,'materialvalid',combine(g,'materialchecks',['materialpath.Valid',call(g,'empty',STR+'EqualEqual_StrStr',{'A':'material.Item'},B='')],True))
    mcomma=call(g,'mcomma',KML+':SelectString',{'bPickA':op(g,'mfirst','EqualEqual_IntInt','mi.PublishMaterialIndex',B=0)},A='',B=',')
    mexpr=call(g,'mopen',STR+'Concat_StrStr',{'A':call(g,'mseparator',STR+'Concat_StrStr',{'A':'mjson.Accumulator','B':mcomma})},B='"')
    mexpr=call(g,'mvalue',STR+'Concat_StrStr',{'A':mexpr,'B':'material.Item'});mexpr=call(g,'mclose',STR+'Concat_StrStr',{'A':mexpr},B='"')
    set_value(g,'materialappend','local:Accumulator',mexpr);set_value(g,'materialnext','local:PublishMaterialIndex',op(g,'materialadvance','Add_IntInt','mi.PublishMaterialIndex',B=1))
    set_value(g,'closepart','local:Accumulator',call(g,'partend',STR+'Concat_StrStr',{'A':'mjson.Accumulator'},B=']}'))
    set_value(g,'next','local:Cursor',op(g,'advance','Add_IntInt','i.Cursor',B=1))
    final=call(g,'finish',STR+'Concat_StrStr',{'A':'json.Accumulator'},B=']}}')
    g.wire((final,'result.JSON'));g.set('yes','local:OK','true');finish_bool(g,'Ready')
    g.chain('entry','document','countvalid','more','mesh','supported','valid','validpart','append','resetmaterial','materialmore','materialpath','materialvalid','materialappend','materialnext','materialmore');g.chain('materialmore.else','closepart','next','more');g.chain('more.else','yes','result')
    for pin in ['document.else','countvalid.else','supported.else','validpart.else','materialvalid.else']:g.chain(pin,'result')
    initial='{"format":"zcom-share","schema_version":1,"content_type":"composition","metadata":{"title":"Den Designer beta submission"},"payload":{"entries":['
    return g.function('BuildCommunitySubmission',inputs=[v('Document','object:'+LAYOUT)],outputs=[v('JSON','string'),v('Ready','bool')],locals=[v('Cursor','int','0'),v('PublishMaterialIndex','int','0'),v('Accumulator','string',initial),v('OK','bool','false')])


def publish():
    # Only send a reviewed immutable saved snapshot. Recheck library identity.
    from runtime_community_ui import read
    g=Graph();g.call('ready','self:CanEdit');branch(g,'available',combine(g,'availablecheck',[get(g,'UIOpen'),'ready.Ready']))
    g.call('ensure','self:EnsureCompositionService');g.call('current','self:CommunitySourceCurrent');branch(g,'fresh','current.Accepted')
    branch(g,'reviewed',combine(g,'reviewchecks',[call(g,'hasreview',STR+'NotEqual_StrStr',{'A':get(g,'CommunityUploadJSON')},B=''),call(g,'samerevision',STR+'EqualEqual_StrStr',{'A':get(g,'CommunityUploadLibraryID'),'B':get(g,'CommunitySourceLibraryID')})]))
    # Text is framed as four bounded printable ASCII lines; native validates all
    # lengths, code/revision shape and refuses credential-shaped metadata.
    expression=get(g,'CommunityUploadThumbnail')
    for i,value in enumerate([read(g,'PublishTitle'),read(g,'PublishDescription'),read(g,'PublishCode'),read(g,'PublishRevision'),get(g,'CommunityUploadJSON')]):
        expression=call(g,'newline'+str(i),STR+'Concat_StrStr',{'A':expression},B='\n')
        expression=call(g,'value'+str(i),STR+'Concat_StrStr',{'A':expression,'B':value})
    g.call('start','self:StartCommunityTransfer',Input='PUBLISH');g.wire((expression,'start.Payload'))
    g.set('message','CommunityMessage','Publishing reviewed saved composition over HTTPS… Cancel stops background work.');g.call('refresh','self:RefreshCommunityFeedback')
    g.set('unsupported','CommunityMessage','The saved library changed or no snapshot was reviewed. Choose a saved card and Review again. Your form values have been kept.')
    g.chain('entry','ready','available','ensure','current','fresh','reviewed','start','message','refresh');g.chain('fresh.else','unsupported','refresh');g.chain('reviewed.else','unsupported')
    return g.function('SubmitCommunityComposition')


def thumbnail_name():
    spec=filename();spec['name']='CommunityThumbnailName';return spec
