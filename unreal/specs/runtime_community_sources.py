"""Community's read-only local source selectors have independent revisions/selections."""
from graph import Graph,variable as v
from runtime import LAYOUT
from runtime_store import call,branch,STR
from runtime_apply import get
from runtime_world import validity
from runtime_editor_host import text,widget
from runtime_catalog_ui import ITEM
from runtime_layout_ui import PRESETS
import runtime_composition_library as compositions
import runtime_layout_ui as presets

MAP={'WBP_DenCompositions':'WBP_DenHolonet','CompositionsPanel':'CommunityPanel','RefreshCompositionLibrary':'RefreshCommunitySources','RefreshCompositionFeedback':'RefreshCommunityFeedback','ReadCompositionCard':'ReadCommunitySourceCard','SelectCompositionCard':'SelectCommunitySourceCard','CompositionLibraryCurrent':'CommunitySourceCurrent','SelectedComposition':'CommunitySourceName','CompositionNames':'CommunitySourceNames','CompositionRows':'CommunitySourceRows','CompositionListStatus':'CommunitySourceListStatus','CompositionListRevision':'CommunitySourceListRevision','CompositionLibraryID':'CommunitySourceLibraryID','CompositionMessage':'CommunityMessage'}

def adapt(value):
    if isinstance(value,list):return [adapt(x) for x in value]
    if isinstance(value,dict):return {adapt(k):adapt(x) for k,x in value.items()}
    if not isinstance(value,str):return value
    if value== 'Compositions':return 'CommunitySources'
    if value=='compositions':return 'community'
    for old,new in MAP.items():value=value.replace(old,new)
    return value.replace(':Compositions',':CommunitySources').replace('.Compositions','.CommunitySources')


def feedback():
    g=Graph();branch(g,'valid',validity(g,'panel',get(g,'CommunityPanel')))
    text(g,'footer','CommunityPanel','Footer',value=get(g,'CommunityMessage'))
    from graph import KML
    label=call(g,'label',KML+':SelectString',{'bPickA':get(g,'CommunityRemember')},A='Remember on this PC: On',B='Remember on this PC: Off')
    text(g,'remember','CommunityPanel','RememberCommunityLabel',value=label)
    # Title bar: "Connected as <name>" or "Not connected".
    from runtime_community_ui import connected
    who=call(g,'who',STR+'Replace',{'SourceString':get(g,'CommunityProfile')},From=' - Remembered connection.',To='',SearchCase='CaseSensitive')
    text(g,'pill','CommunityPanel','ConnectionLabel',value=call(g,'pilltext',KML+':SelectString',{'A':who,'bPickA':connected(g)},B='Not connected'))
    g.call('share','self:RefreshHolonetShare')
    g.chain('entry','valid','footer','remember','pill','share');return g.function('RefreshCommunityFeedback')


def changed():
    g=Graph();branch(g,'active',call(g,'match',STR+'EqualEqual_StrStr',{'A':get(g,'ActivePanel')},B='community'))
    g.call('sources','self:RefreshCommunitySources');g.call('area','self:SetCommunityArea');g.wire((get(g,'CommunityArea'),'area.Area'))
    g.call('refresh','self:RefreshCommunityFeedback');g.call('gallery','self:EnsureCommunityGallery');branch(g,'profile',call(g,'profileempty',STR+'EqualEqual_StrStr',{'A':get(g,'CommunityProfile')},B=''));g.call('connection','self:StartCommunityFetch',Input='CONNECT')
    g.call('cancel','self:CancelCommunityFetch');g.call('thumbs','self:CancelThumbnailRequests')
    g.chain('entry','active','sources','area','refresh','profile','connection');g.chain('profile.else','gallery');g.chain('active.else','cancel','thumbs');return g.function('CommunityPanelChanged')


def variables():return [v('CommunitySourceNames','string[]'),v('CommunitySourceRows','object:'+ITEM+'[]'),v('CommunitySourceName','string'),v('CommunitySourceListStatus','int'),v('CommunitySourceListRevision','int'),v('CommunitySourceLibraryID','string')]
def functions():return [adapt(compositions.refresh()),adapt(compositions.adapt(presets.read_key())),adapt(compositions.adapt(presets.select())),adapt(compositions.adapt(presets.library_current())),feedback(),changed()]
