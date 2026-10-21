"""Native editor access to isolated preferences and persistent catalog recents."""
from graph import Graph, variable as v, GS, KML
from runtime_preferences import DOCUMENT
from runtime_preference_service import SERVICE
from runtime import arr
from runtime_store import call, branch
from runtime_world import validity, set_value
from runtime_apply import get
from runtime_session import method
from runtime_catalog import CATALOG


def ensure():
    g=Graph();g.node('self','self');branch(g,'exists',validity(g,'alive',get(g,'PreferenceService')))
    obj=call(g,'create',GS+':SpawnObject',{'Outer':'self.self'},ObjectClass=SERVICE)
    g.node('cast','cast',**{'class':SERVICE});g.wire((obj,'cast.Object'));set_value(g,'keep','PreferenceService','cast.AsBP Den Preferences')
    set_value(g,'key',SERVICE+':PreferencesKey',get(g,'PreferencesStorageKey'));g.wire((get(g,'PreferenceService'),'key.self'))
    g.chain('entry','exists','key');g.chain('exists.else','create','cast','keep','key')
    return g.function('EnsurePreferenceService')


def read():
    g=Graph();g.call('ensure','self:EnsurePreferenceService');branch(g,'valid',validity(g,'alive',get(g,'PreferenceService')))
    method(g,'open',SERVICE,'OpenPreferences',get(g,'PreferenceService'))
    set_value(g,'status','PreferencesStatus','open.Status');set_value(g,'document','PreferencesDocument','open.Document')
    g.chain('entry','ensure','valid','open','status','document');return g.function('ReadEditorPreferences')


def restore_recents():
    g=Graph();branch(g,'catalog',validity(g,'provider',get(g,'CatalogProvider')));g.call('read','self:ReadEditorPreferences')
    branch(g,'valid',validity(g,'document',get(g,'PreferencesDocument')))
    method(g,'recent',DOCUMENT,'RecentMeshes',get(g,'PreferencesDocument'));arr(g,'count','Length','recent.Paths')
    g.set('start','local:Cursor');g.wire((call(g,'last',KML+':Subtract_IntInt',{'A':'count.ReturnValue'},B=1),'start.Cursor'))
    g.get('i','local:Cursor');branch(g,'loop',call(g,'within',KML+':GreaterEqual_IntInt',{'A':'i.Cursor'},B=0))
    arr(g,'path','Get','recent.Paths');g.wire(('i.Cursor','path.Index'))
    method(g,'find',CATALOG,'FindPath',get(g,'CatalogProvider'),{'Path':'path.Item'})
    # Remember itself checks the index. Removed catalog assets remain in the
    # stored history but cannot cause loads or invalid runtime catalog indices.
    method(g,'remember',CATALOG,'Remember',get(g,'CatalogProvider'),{'Index':'find.Index'})
    g.set('next','local:Cursor');g.wire((call(g,'decrement',KML+':Subtract_IntInt',{'A':'i.Cursor'},B=1),'next.Cursor'))
    g.chain('entry','catalog','read','valid','recent','start','loop','find','remember','next','loop')
    return g.function('RestoreCatalogRecents',locals=[v('Cursor','int','0')])


def save_recent():
    g=Graph();g.call('ensure','self:EnsurePreferenceService');branch(g,'valid',validity(g,'alive',get(g,'PreferenceService')))
    method(g,'save',SERVICE,'RememberRecent',get(g,'PreferenceService'),{'Path':get(g,'PlacementPath')})
    set_value(g,'status','PreferencesStatus','save.Status');branch(g,'document',validity(g,'doc','save.Document'))
    set_value(g,'copy','PreferencesDocument','save.Document');g.chain('entry','ensure','valid','save','status','document','copy')
    return g.function('SavePlacementRecent')


def variables():
    return [v('PreferencesStorageKey','string','preferences'),v('PreferenceService','object:'+SERVICE),
            v('PreferencesDocument','object:'+DOCUMENT),v('PreferencesStatus','int'),v('LastUIPreferencesStatus','int','-1')]


def functions():return [ensure(),read(),restore_recents(),save_recent()]
