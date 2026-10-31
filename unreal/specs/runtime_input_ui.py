"""Editor-owned mapping lifecycle and application of validated preferences."""
from graph import Graph,variable as v,GS,KML
from runtime_store import call,branch,combine,STR
from runtime_world import validity,set_value,finish_bool
from runtime_apply import get
from runtime_session import method
from runtime_preferences import DOCUMENT,NUMBERS
from runtime_input_mappings import BUILDER,IMC
from runtime_editor_assets import RIG
from runtime_editor_host import SUBINTERFACE
from runtime_thumbnail_queue import QUEUE


def prepare():
    g=Graph();g.node('self','self');branch(g,'exists',validity(g,'buildervalid',get(g,'InputMappingBuilder')))
    call(g,'create',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=BUILDER);g.node('cast','cast',**{'class':BUILDER});g.wire(('create.ReturnValue','cast.Object'))
    set_value(g,'keep','InputMappingBuilder','cast.AsBP Den Input Mappings')
    method(g,'build',BUILDER,'BuildEditorContext',get(g,'InputMappingBuilder'),{'Document':get(g,'PreferencesDocument')})
    g.wire(('build.Context','result.Context'),('build.Accepted','result.Accepted'),('build.UsedDefaults','result.UsedDefaults'))
    g.chain('entry','exists','build','result');g.chain('exists.else','create','cast','keep','build');g.chain('cast.CastFailed','result')
    return g.function('PrepareEditorMappings',outputs=[v('Context','object:'+IMC),v('Accepted','bool'),v('UsedDefaults','bool')])


def release():
    g=Graph();branch(g,'valid',combine(g,'owned',[validity(g,'subsystem',get(g,'InputSubsystem')),validity(g,'mapping',get(g,'EditorMappingContext'))]))
    call(g,'remove',SUBINTERFACE+':RemoveMappingContext',{'self':get(g,'InputSubsystem'),'MappingContext':get(g,'EditorMappingContext')},Options='(bForceImmediately=True)')
    g.set('clear','EditorMappingContext');g.chain('entry','valid','remove','clear');g.chain('valid.else','clear')
    return g.function('ReleaseEditorMappings')


def install():
    g=Graph();branch(g,'valid',combine(g,'ready',[validity(g,'subsystem',get(g,'InputSubsystem')),validity(g,'rig',get(g,'EditorRig'))]))
    g.call('build','self:PrepareEditorMappings');branch(g,'accepted','build.Accepted')
    g.call('looking','self:SetLooking',Held='false');g.call('drag','self:EndSelectionDrag',Commit='false');g.call('release','self:ReleaseEditorMappings')
    set_value(g,'remember','EditorMappingContext','build.Context');set_value(g,'fallback','BindingsDefaulted','build.UsedDefaults')
    g.set('fast',RIG+':bFast','false');g.wire((get(g,'EditorRig'),'fast.self'))
    g.set('alt',RIG+':bAlt','false');g.wire((get(g,'EditorRig'),'alt.self'))
    call(g,'add',SUBINTERFACE+':AddMappingContext',{'self':get(g,'InputSubsystem'),'MappingContext':get(g,'EditorMappingContext')},Priority=1000000,Options='(bIgnoreAllPressedKeysUntilRelease=True,bForceImmediately=True)')
    g.call('help','self:RefreshEditorHelp');g.set('yes','local:OK','true');finish_bool(g)
    g.chain('entry','valid','build','accepted','looking','drag','release','remember','fallback','fast','alt','add','help','yes','result')
    for pin in ['valid.else','accepted.else']:g.chain(pin,'result')
    return g.function('InstallEditorMappings',outputs=[v('Accepted','bool')],locals=[v('OK','bool','false')])


def apply_preferences():
    g=Graph();branch(g,'valid',validity(g,'doc',get(g,'PreferencesDocument')));previous='valid'
    for key,field in [('unlock_structure','StructureEnabled'),('select_floors','FloorsEnabled'),('select_walls','WallsEnabled'),('autosave','DraftEnabled'),('thumbnails','ThumbnailsEnabled'),
                      ('neighbour_snap','SnapEnabled'),('snap_guides','SnapGuidesEnabled'),('rail_labels','RailLabels')]:
        method(g,key,DOCUMENT,'ReadPreference',get(g,'PreferencesDocument'),Key=key)
        set_value(g,key+'apply',field,call(g,key+'value',STR+'EqualEqual_StrStr',{'A':key+'.Value'},B='true'))
        g.chain(previous,key,key+'apply');previous=key+'apply'
    for key,field,index,choices in [('snap','GridStep','GridIndex',['0','5','10','25','50']),('reach','ReachCm','ReachIndex',['1000','2000','4000','10000'])]:
        method(g,key,DOCUMENT,'ReadPreference',get(g,'PreferencesDocument'),Key=key)
        set_value(g,key+'apply',field,call(g,key+'value',STR+'Conv_StringToDouble',{'InString':key+'.Value'}));g.chain(previous,key,key+'apply');previous=key+'apply'
        g.node(key+'done','sequence',outputs=1)
        for i,value in enumerate(choices):
            ident=key+str(i);branch(g,ident,call(g,ident+'same',STR+'EqualEqual_StrStr',{'A':key+'.Value'},B=value))
            g.set(ident+'index',index,str(i));g.chain(previous,ident,ident+'index',key+'done');previous=ident+'.else'
        g.chain(previous,key+'done');previous=key+'done.then_0'
    method(g,'rotationpivot',DOCUMENT,'ReadPreference',get(g,'PreferencesDocument'),Key='rotation_pivot')
    set_value(g,'rotationpivotapply','RotationPivot','rotationpivot.Value')
    g.chain(previous,'rotationpivot','rotationpivotapply');previous='rotationpivotapply'
    method(g,'mode',DOCUMENT,'ReadPreference',get(g,'PreferencesDocument'),Key='gimbal');g.chain(previous,'mode');previous='mode';g.node('modedone','sequence',outputs=1)
    for i,value in enumerate(['off','move','rotate','scale']):
        ident='mode'+str(i);branch(g,ident,call(g,ident+'same',STR+'EqualEqual_StrStr',{'A':'mode.Value'},B=value));g.set(ident+'apply','GizmoMode',str(i))
        g.chain(previous,ident,ident+'apply','modedone');previous=ident+'.else'
    g.chain(previous,'modedone');previous='modedone.then_0'
    branch(g,'rig',validity(g,'rigvalid',get(g,'EditorRig')));g.chain(previous,'rig');previous='rig'
    method(g,'openingkey',DOCUMENT,'ReadPreference',get(g,'PreferencesDocument'),Key='toggle_key')
    method(g,'openingconfigure',RIG,'ConfigureOpeningKey',get(g,'EditorRig'),{'Name':'openingkey.Value'})
    g.chain(previous,'openingkey','openingconfigure');previous='openingconfigure'
    method(g,'snapdistance',DOCUMENT,'ReadPreference',get(g,'PreferencesDocument'),Key='snap_distance')
    g.call('snapdistanceparse','self:ParseTransformNumber');g.wire(('snapdistance.Value','snapdistanceparse.Text'))
    set_value(g,'snapdistanceapply','SnapDistance','snapdistanceparse.Value')
    g.chain(previous,'snapdistance','snapdistanceparse','snapdistanceapply');previous='snapdistanceapply'
    for key,field in [('fly_speed','Speed'),('fast_multiplier','FastMultiplier'),('look_speed','LookRate')]:
        method(g,key,DOCUMENT,'ReadPreference',get(g,'PreferencesDocument'),Key=key)
        g.call(key+'parse','self:ParseTransformNumber');g.wire((key+'.Value',key+'parse.Text'))
        set_value(g,key+'apply',RIG+':'+field,key+'parse.Value');g.wire((get(g,'EditorRig'),key+'apply.self'))
        g.chain(previous,key,key+'parse',key+'apply');previous=key+'apply'
    branch(g,'worker',validity(g,'workerexists',get(g,'ThumbnailWorker')));g.chain(previous,'worker');g.chain('rig.else','worker')
    set_value(g,'workerflag',QUEUE+':Enabled',get(g,'ThumbnailsEnabled'));g.wire((get(g,'ThumbnailWorker'),'workerflag.self'))
    branch(g,'drafts',get(g,'DraftEnabled'));g.set('clear','DraftPending','false');g.call('schedule','self:ScheduleDraft')
    g.chain('worker','workerflag','drafts','schedule');g.chain('worker.else','drafts');g.chain('drafts.else','clear');g.chain('entry','valid')
    return g.function('ApplyEditorPreferences')


def variables():return [v('InputMappingBuilder','object:'+BUILDER),v('EditorMappingContext','object:'+IMC),v('BindingsDefaulted','bool','false'),v('ThumbnailsEnabled','bool','true')]
def functions():return [prepare(),release(),install(),apply_preferences()]
