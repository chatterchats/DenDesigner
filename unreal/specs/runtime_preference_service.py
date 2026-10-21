"""Transactional preference operations for the standalone editor/coordinator.

Read defaults on missing/damaged data, but never overwrite an unreadable or
newer-schema store. Every mutation reopens the latest disk snapshot so a recents
update cannot clobber a settings change from another service instance.
"""
from graph import Graph, variable as v, GS, KML
from runtime_preferences import ROOT, DOCUMENT, STORE, DEFAULTS, output
from runtime import arr, unpack
from runtime_store import call, branch, STR

SERVICE=ROOT+'BP_DenPreferences'
CAST='AsBP Den Preferences Save'


def open_preferences():
    g=Graph();g.get('key','PreferencesKey');g.call('load','self:LoadPreferences',Draft='false',BeforeRevision=0);g.wire(('key.PreferencesKey','load.Key'))
    g.set('status','local:ResultStatus');g.wire(('load.Status','status.ResultStatus'))
    valid=call(g,'valid','/Script/Engine.KismetSystemLibrary:IsValid',{'Object':'load.Document'});branch(g,'loaded',valid)
    g.set('document','local:ResultDocument');g.wire(('load.Document','document.ResultDocument'))
    call(g,'create',GS+':CreateSaveGameObject',SaveGameClass=DOCUMENT);g.node('cast','cast',**{'class':DOCUMENT});g.wire(('create.ReturnValue','cast.Object'))
    g.set('fresh','local:ResultDocument');g.wire(('cast.'+CAST,'fresh.ResultDocument'));g.set('failed','local:ResultStatus','7')
    g.chain('entry','load','status','loaded','document','result');g.chain('loaded.else','create','cast','fresh','result');g.chain('cast.CastFailed','failed','result')
    return g.function('OpenPreferences',outputs=[v('Document','object:'+DOCUMENT),v('Status','int')],
                      locals=[output(g,'Document','object:'+DOCUMENT),output(g,'Status','int','7')])


def change(mode):
    g=Graph();g.call('open','self:OpenPreferences');g.set('status','local:ResultStatus');g.wire(('open.Status','status.ResultStatus'))
    branch(g,'writable',call(g,'healthy',KML+':LessEqual_IntInt',{'A':'open.Status'},B=2))
    g.set('document','local:ResultDocument');g.wire(('open.Document','document.ResultDocument'))
    if mode=='Setting':
        call(g,'mutate',DOCUMENT+':WritePreference',{'self':'open.Document','Key':'entry.Key','Value':'entry.Value'})
        branch(g,'accepted','mutate.Accepted');branch(g,'changed','mutate.Changed')
        g.chain('document','mutate','accepted','changed','save');g.chain('accepted.else','invalid','result');g.chain('changed.else','unchanged','result')
        inputs=[v('Key','string'),v('Value','string')];name='ChangePreference'
    else:
        call(g,'recent',DOCUMENT+':RecentMeshes',{'self':'open.Document'});arr(g,'length','Length','recent.Paths')
        branch(g,'has',call(g,'nonempty',KML+':Greater_IntInt',{'A':'length.ReturnValue'},B=0))
        arr(g,'first','Get','recent.Paths',Index=0);branch(g,'same',call(g,'equal',STR+'EqualEqual_StrStr',{'A':'entry.Path','B':'first.Item'}))
        call(g,'mutate',DOCUMENT+':RememberMesh',{'self':'open.Document','Path':'entry.Path'});branch(g,'accepted','mutate.Accepted')
        g.chain('document','recent','has','same','unchanged','result');g.chain('has.else','mutate','accepted','save');g.chain('same.else','mutate');g.chain('accepted.else','invalid','result')
        inputs=[v('Path','string')];name='RememberRecent'
    g.get('key','PreferencesKey');g.call('save','self:SavePreferences',Draft='false',BaseRevision=0,BaseID='');g.wire(('key.PreferencesKey','save.Key'),('open.Document','save.Document'))
    g.set('savedstatus','local:ResultStatus');g.wire(('save.Status','savedstatus.ResultStatus'))
    g.set('saved','local:ResultDocument');g.wire(('save.SavedDocument','saved.ResultDocument'))
    g.set('changedresult','local:ResultChanged');g.wire((call(g,'success',KML+':EqualEqual_IntInt',{'A':'save.Status'},B=1),'changedresult.ResultChanged'))
    g.set('invalid','local:ResultStatus','7');g.set('unchanged','local:ResultStatus','1')
    g.chain('entry','open','status','writable','document');g.chain('writable.else','result');g.chain('save','savedstatus','saved','changedresult','result')
    return g.function(name,inputs=inputs,outputs=[v('Document','object:'+DOCUMENT),v('Status','int'),v('Changed','bool')],
                      locals=[output(g,'Document','object:'+DOCUMENT),output(g,'Status','int','7'),output(g,'Changed','bool','false')])


def reset_settings():
    from runtime_preferences import ROW
    g=Graph();g.call('open','self:OpenPreferences');g.set('status','local:ResultStatus');g.wire(('open.Status','status.ResultStatus'))
    branch(g,'writable',call(g,'healthy',KML+':LessEqual_IntInt',{'A':'open.Status'},B=2))
    g.get('rows',DOCUMENT+':Entries');g.wire(('open.Document','rows.self'));g.get('i','local:Cursor')
    arr(g,'length','Length','rows.Entries');branch(g,'loop',call(g,'within',KML+':Less_IntInt',{'A':'i.Cursor','B':'length.ReturnValue'}))
    arr(g,'row','Get','rows.Entries');g.wire(('i.Cursor','row.Index'));unpack(g,'fields',ROW,'row.Item')
    from runtime_preferences import enum
    branch(g,'setting',enum(g,'settingkey','fields.Key',list(DEFAULTS)))
    arr(g,'remove','Remove','rows.Entries');g.wire(('i.Cursor','remove.IndexToRemove'));g.set('changed','local:ResultChanged','true')
    g.set('next','local:Cursor');g.wire((call(g,'add',KML+':Add_IntInt',{'A':'i.Cursor'},B=1),'next.Cursor'))
    branch(g,'dirty','outChanged.ResultChanged');g.set('document','local:ResultDocument');g.wire(('open.Document','document.ResultDocument'))
    g.get('key','PreferencesKey');g.call('save','self:SavePreferences',Draft='false',BaseRevision=0,BaseID='');g.wire(('key.PreferencesKey','save.Key'),('open.Document','save.Document'))
    g.set('savedstatus','local:ResultStatus');g.wire(('save.Status','savedstatus.ResultStatus'))
    g.set('saved','local:ResultDocument');g.wire(('save.SavedDocument','saved.ResultDocument'))
    g.set('success','local:ResultChanged');g.wire((call(g,'ok',KML+':EqualEqual_IntInt',{'A':'save.Status'},B=1),'success.ResultChanged'))
    g.set('unchanged','local:ResultStatus','1')
    g.chain('entry','open','status','writable','loop','setting','remove','changed','loop');g.chain('setting.else','next','loop')
    g.chain('loop.else','document','dirty','save','savedstatus','saved','success','result');g.chain('dirty.else','unchanged','result');g.chain('writable.else','result')
    return g.function('ResetSettings',outputs=[v('Document','object:'+DOCUMENT),v('Status','int'),v('Changed','bool')],
                      locals=[v('Cursor','int','0'),output(g,'Document','object:'+DOCUMENT),output(g,'Status','int','7'),output(g,'Changed','bool','false')])


def spec():
    return dict(kind='blueprint',path=SERVICE,parent=STORE,variables=[v('PreferencesKey','string','preferences')],
                functions=[open_preferences(),change('Setting'),change('Recent'),reset_settings()])
