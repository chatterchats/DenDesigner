"""Fixed SaveGame mailbox for the optional standalone transport.

The pak uses engine SaveGame APIs only. Native code never receives a world
pointer. All incoming text is bounded and converted into ordinary local values.
"""
from graph import Graph, variable as v, GS, KML
from runtime import ROOT, arr
from runtime_store import call, branch, combine, STR
from runtime_world import set_value, finish_bool
from runtime_apply import get, clock
from runtime_session import prop
from runtime_gizmo_controller import op

WIRE=ROOT+'BP_DenCommunityWireSave'
REQUEST='ZComDen/Community/v1/request'
RESPONSE='ZComDen/Community/v1/response'


def split(g,name,source,delimiter):
    return call(g,name,STR+'ParseIntoArray',{'SourceString':source},Delimiter=delimiter,CullEmptyStrings='false')


def item(g,name,source,index):
    arr(g,name,'Get',source,Index=index);return name+'.Item'


def eq(g,name,a,b):return call(g,name,STR+'EqualEqual_StrStr',{'A':a},B=b)


def length(g,name,source,n):
    arr(g,name+'len','Length',source);return op(g,name,'EqualEqual_IntInt',name+'len.ReturnValue',B=n)


def bad(g,pins,message='Invalid Community response. Nothing was imported.'):
    g.call('fail','self:FailCommunityFetch',Message=message);g.wire((get(g,'CommunityToken'),'fail.Token'))
    for pin in pins:g.chain(pin,'fail')


def delete():
    g=Graph();call(g,'delete',GS+':DeleteGameInSlot',SlotName=REQUEST,UserIndex=0)
    arr(g,'release','Clear',get(g,'CommunityWireLines'));g.set('cursor','CommunityWireCursor','0')
    g.chain('entry','delete','release','cursor');return g.function('ReleaseCommunityMailbox')


def write():
    g=Graph();call(g,'create',GS+':CreateSaveGameObject',SaveGameClass=WIRE)
    g.node('cast','cast',**{'class':WIRE});g.wire(('create.ReturnValue','cast.Object'))
    for field,source in [('Token',get(g,'CommunityToken')),('Input',get(g,'CommunityRequest'))]:
        set_value(g,field,WIRE+':'+field,source);g.wire(('cast.AsBP Den Community Wire Save',field+'.self'))
    value=call(g,'outgoing',KML+':SelectString',{'A':get(g,'CommunityOutgoing'),'bPickA':call(g,'haspayload',STR+'NotEqual_StrStr',{'A':get(g,'CommunityOutgoing')},B='')},B='request')
    set_value(g,'wire',WIRE+':Wire',value);g.wire(('cast.AsBP Den Community Wire Save','wire.self'))
    call(g,'save',GS+':SaveGameToSlot',{'SaveGameObject':'cast.AsBP Den Community Wire Save'},SlotName=REQUEST,UserIndex=0)
    branch(g,'saved','save.ReturnValue');g.chain('entry','create','cast','Token','Input','wire','save','saved')
    bad(g,['cast.CastFailed','saved.else'],'Community request could not be saved. Nothing was imported.')
    return g.function('WriteCommunityRequest')


def load():
    g=Graph();branch(g,'pending',get(g,'CommunityPending'))
    branch(g,'due',op(g,'interval','GreaterEqual_DoubleDouble',op(g,'elapsed','Subtract_DoubleDouble',clock(g,'now'),get(g,'CommunityMailboxAt')),B=.2))
    set_value(g,'at','CommunityMailboxAt',clock(g,'atnow'))
    branch(g,'exists',call(g,'existscall',GS+':DoesSaveGameExist',SlotName=RESPONSE,UserIndex=0))
    call(g,'load',GS+':LoadGameFromSlot',SlotName=RESPONSE,UserIndex=0);g.node('cast','cast',**{'class':WIRE});g.wire(('load.ReturnValue','cast.Object'))
    token=prop(g,'token',WIRE,'Token','cast.AsBP Den Community Wire Save')
    branch(g,'current',call(g,'tokenmatch',STR+'EqualEqual_StrStr',{'A':token,'B':get(g,'CommunityToken')}))
    wire=prop(g,'wire',WIRE,'Wire','cast.AsBP Den Community Wire Save');textlen=call(g,'len',STR+'Len',{'S':wire})
    branch(g,'bounded',op(g,'cap','LessEqual_IntInt',textlen,B=4194304))
    # Strip only terminal line endings. Empty material slots stay present.
    clean=call(g,'clean',STR+'TrimTrailing',{'SourceString':wire})
    set_value(g,'lines','CommunityWireLines',split(g,'linesplit',clean,'\n'))
    g.call('begin','self:ReadCommunityPreamble');g.chain('entry','pending','due','at','existscall','exists','load','cast','current','bounded','lines','begin')
    bad(g,['bounded.else']);return g.function('LoadCommunityResponse')


def preamble():
    g=Graph();lines=get(g,'CommunityWireLines');arr(g,'count','Length',lines)
    branch(g,'size',combine(g,'bounds',[op(g,'min','GreaterEqual_IntInt','count.ReturnValue',B=3),op(g,'max','LessEqual_IntInt','count.ReturnValue',B=8455)]))
    expected=call(g,'expected',STR+'Concat_StrStr',{'B':get(g,'CommunityToken')},A='ZCOM-COMMUNITY\t1\t')
    branch(g,'header',call(g,'headercheck',STR+'EqualEqual_StrStr',{'A':item(g,'headerline',lines,0),'B':expected}))
    status=item(g,'status',lines,1);branch(g,'gallerymode',call(g,'galleryword',STR+'StartsWith',{'SourceString':status},InPrefix='gallery\t',SearchCase='CaseSensitive'));g.call('galleryread','self:ReadCommunityGallery');branch(g,'ok',eq(g,'okcheck',status,'ok'))
    progress=split(g,'progressparts',status,'\t');branch(g,'progress',combine(g,'progresscheck',[length(g,'progresssize',progress,2),eq(g,'progressword',item(g,'progressworditem',progress,0),'progress')]))
    from runtime_editor_host import text
    text(g,'progresslabel','CommunityPanel','Footer',value=item(g,'progressmessage',progress,1))
    error=split(g,'errorparts',status,'\t');branch(g,'error',combine(g,'errorcheck',[length(g,'errorsize',error,2),eq(g,'errorword',item(g,'errorworditem',error,0),'error')]))
    g.call('serviceerror','self:FailCommunityFetch');g.wire((get(g,'CommunityToken'),'serviceerror.Token'),(item(g,'errormessage',error,1),'serviceerror.Message'))
    branch(g,'successsize',op(g,'enough','GreaterEqual_IntInt','count.ReturnValue',B=8))
    checks=[];fields={}
    for name,index,word,n in [('name',2,'name',2),('report',3,'report',2),('anchor',4,'anchor',4),('parts',5,'count',2)]:
        fields[name]=split(g,name+'split',item(g,name+'line',lines,index),'\t')
        checks += [length(g,name+'size',fields[name],n),eq(g,name+'tag',item(g,name+'tagitem',fields[name],0),word)]
    branch(g,'fields',combine(g,'fieldchecks',checks));previous='fields'
    for axis,i in [('X',1),('Y',2),('Z',3)]:
        g.call(axis,'self:ParseTransformNumber');g.wire((item(g,axis+'text',fields['anchor'],i),axis+'.Text'));branch(g,axis+'valid',axis+'.Valid');g.chain(previous,axis,axis+'valid');previous=axis+'valid'
    number=item(g,'counttext',fields['parts'],1);g.call('partnumber','self:ParseTransformNumber');g.wire((number,'partnumber.Text'));branch(g,'numbervalid','partnumber.Valid')
    integer=call(g,'integer',STR+'Conv_StringToInt',{'InString':number});branch(g,'countvalid',op(g,'integral','EqualEqual_DoubleDouble',call(g,'asdouble',KML+':Conv_IntToDouble',{'InInt':integer}),'partnumber.Value'))
    g.call('begin','self:BeginCommunityImport');g.wire((get(g,'CommunityToken'),'begin.Token'),(item(g,'namevalue',fields['name'],1),'begin.Name'),(item(g,'reportvalue',fields['report'],1),'begin.Report'),(integer,'begin.Count'))
    anchor=call(g,'anchorvalue',KML+':MakeVector',{'X':'X.Value','Y':'Y.Value','Z':'Z.Value'});g.wire((anchor,'begin.Anchor'));branch(g,'began','begin.Accepted');g.set('cursor','CommunityWireCursor','6')
    g.chain(previous,'partnumber','numbervalid','countvalid','begin','began','cursor');g.chain('entry','size','header','gallerymode','galleryread');g.chain('gallerymode.else','ok','successsize','fields');g.chain('ok.else','progress','progresslabel');g.chain('progress.else','error','serviceerror')
    bad(g,['size.else','header.else','error.else','successsize.else','fields.else','Xvalid.else','Yvalid.else','Zvalid.else','numbervalid.else','countvalid.else','began.else'])
    return g.function('ReadCommunityPreamble')


def record():
    g=Graph();parts=split(g,'split','entry.Line','\t');tag=item(g,'tag',parts,0)
    branch(g,'part',eq(g,'partcheck',tag,'part'));branch(g,'partsize',length(g,'partsizecheck',parts,12));previous='partsize'
    for i in range(2,12):
        name='number'+str(i);g.call(name,'self:ParseTransformNumber');g.wire((item(g,'text'+str(i),parts,i),name+'.Text'));branch(g,name+'valid',name+'.Valid');g.chain(previous,name,name+'valid');previous=name+'valid'
    g.call('append','self:AppendCommunityPart');g.wire((get(g,'CommunityToken'),'append.Token'),(item(g,'mesh',parts,1),'append.Mesh'))
    for name,indices,fn in [('Position',[2,3,4],'MakeVector'),('Rotation',[5,6,7],'MakeRotator'),('Scale',[8,9,10],'MakeVector')]:
        pins=['Pitch','Yaw','Roll'] if name=='Rotation' else ['X','Y','Z']
        pin=call(g,name,KML+':'+fn,{p:'number'+str(i)+'.Value' for p,i in zip(pins,indices)});g.wire((pin,'append.'+name))
    collision=call(g,'collision',STR+'Conv_StringToInt',{'InString':item(g,'collisiontext',parts,11)})
    branch(g,'collisionvalid',op(g,'collisionintegral','EqualEqual_DoubleDouble',call(g,'collisiondouble',KML+':Conv_IntToDouble',{'InInt':collision}),'number11.Value'))
    g.wire((collision,'append.CollisionMode'));branch(g,'appended','append.Accepted');g.set('yes','local:OK','true');finish_bool(g)
    branch(g,'material',eq(g,'materialcheck',tag,'material'));branch(g,'materialsize',length(g,'materialsizecheck',parts,2))
    g.call('addmaterial','self:AppendCommunityMaterial');g.wire((get(g,'CommunityToken'),'addmaterial.Token'),(item(g,'materialpath',parts,1),'addmaterial.Path'));branch(g,'addedmaterial','addmaterial.Accepted')
    g.chain('entry','part','partsize');g.chain(previous,'collisionvalid','append','appended','yes','result');g.chain('part.else','material','materialsize','addmaterial','addedmaterial','yes')
    for pin in ['partsize.else',*[f'number{i}valid.else' for i in range(2,12)],'collisionvalid.else','appended.else','material.else','materialsize.else','addedmaterial.else']:g.chain(pin,'result')
    return g.function('ReadCommunityRecord',inputs=[v('Line','string')],outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def pump():
    g=Graph();branch(g,'pending',get(g,'CommunityPending'));branch(g,'started',op(g,'startedcheck','GreaterEqual_IntInt',get(g,'CommunityWireCursor'),B=6))
    g.get('budget','local:Budget');branch(g,'budgetcheck',op(g,'underbudget','Less_IntInt','budget.Budget',B=10))
    lines=get(g,'CommunityWireLines');arr(g,'count','Length',lines);branch(g,'within',op(g,'indexcheck','Less_IntInt',get(g,'CommunityWireCursor'),'count.ReturnValue'))
    arr(g,'line','Get',lines);g.wire((get(g,'CommunityWireCursor'),'line.Index'));branch(g,'end',eq(g,'endcheck','line.Item','end'))
    branch(g,'last',op(g,'lastcheck','EqualEqual_IntInt',op(g,'nextindex','Add_IntInt',get(g,'CommunityWireCursor'),B=1),'count.ReturnValue'))
    g.call('commit','self:CommitCommunityImport');g.wire((get(g,'CommunityToken'),'commit.Token'));branch(g,'committed','commit.Accepted');g.call('release','self:ReleaseCommunityMailbox')
    g.call('record','self:ReadCommunityRecord');g.wire(('line.Item','record.Line'));branch(g,'accepted','record.Accepted')
    set_value(g,'advance','CommunityWireCursor',op(g,'next','Add_IntInt',get(g,'CommunityWireCursor'),B=1));set_value(g,'spend','local:Budget',op(g,'budgetnext','Add_IntInt','budget.Budget',B=1))
    g.chain('entry','pending','started','budgetcheck','within','end','last','commit','committed','release')
    g.chain('end.else','record','accepted','advance','spend','budgetcheck')
    bad(g,['within.else','last.else','committed.else','accepted.else'],'Community import rejected (invalid values, duplicate name or library changed). Existing compositions were kept.')
    return g.function('PumpCommunityResponse',locals=[v('Budget','int','0')])


def poll():
    g=Graph();branch(g,'pending',get(g,'CommunityPending'));branch(g,'parsing',op(g,'cursorcheck','GreaterEqual_IntInt',get(g,'CommunityWireCursor'),B=6))
    g.call('load','self:LoadCommunityResponse');g.call('pump','self:PumpCommunityResponse');g.chain('entry','pending','parsing','pump');g.chain('parsing.else','load','pump')
    return g.function('PollCommunityMailbox')


def variables():return [v('CommunityWireLines','string[]'),v('CommunityWireCursor','int'),v('CommunityMailboxAt','double')]
def functions():return [delete(),write(),load(),preamble(),record(),pump(),poll()]
