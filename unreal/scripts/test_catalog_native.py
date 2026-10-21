"""Catalog provider checks against the complete cooked dataset and independent literal-search reference."""
import json
import time


def run(unreal,repo,check):
    from runtime_catalog import CATALOG,metadata
    source=metadata();items=source['items'];count=len(items)
    klass=unreal.EditorAssetLibrary.load_blueprint_class(CATALOG)
    catalog=unreal.new_object(klass)
    get=lambda obj,name:obj.get_editor_property(name)
    check(catalog.call_method('FindPath',('/missing',))==-1,'uninitialized catalog lookup safely reports missing')
    catalog.call_method('Initialize');data=get(catalog,'Data')
    catalog.call_method('Initialize');check(get(catalog,'Data')==data,'catalog initialization reuses its native dataset')
    check(get(data,'Count')==count and get(data,'SourceHash')==source['source_hash'],'cooked catalog records full source count and provenance hash')
    mapping={'Paths':'path','Labels':'label','Details':'detail','SearchTexts':'search','ShelfIDs':'shelf','Solid':'collision'}
    for field,key in mapping.items():
        check(list(get(data,field))==[item[key] for item in items],'cooked catalog '+field+' matches every source row')
    sizes=get(data,'Dimensions')
    check(all((s.x,s.y,s.z)==tuple(row['size']) for s,row in zip(sizes,items)) and len(sizes)==count,'cooked catalog preserves every mesh dimension')
    check(list(get(data,'Groups'))==[c['key'] for c in source['collections']] and get(data,'Groups')[0]=='Den','catalog preserves collection ordering with Den first')
    for index in [0,count//2,count-1]:
        row=catalog.call_method('ReadItem',(index,))
        check(row[0] and row[1]==items[index]['path'] and row[2]==items[index]['label'] and row[3]==items[index]['detail'],'native ReadItem returns row '+str(index))
        check(catalog.call_method('FindPath',(items[index]['path'],))==index,'native path lookup finds row '+str(index))
    for index in [-1,count,count+100]:
        row=catalog.call_method('ReadItem',(index,));check(not row[0] and row[1]=='','out-of-range catalog read has no stale payload')
    check(catalog.call_method('FindPath',('/missing.mesh',))==-1,'unknown asset lookup reports missing')
    def settle():
        pumps=0;start=time.monotonic()
        while get(catalog,'Active'):
            catalog.call_method('Pump');pumps+=1
            if pumps>10000:raise AssertionError('catalog query did not complete')
        assert get(catalog,'Ready')
        return pumps,time.monotonic()-start
    queries=['chair','Medical Bed','REPUBLIC crate','/game/game/environments','[','a.b','chair\tmetal\n',items[100]['path'],'not_a_real_mesh_qxz','', ' \n\t ']
    expected=[]
    for query in queries:
        words=query.lower().split()
        ids=[i for i,row in enumerate(items) if words and all(word in row['search'] for word in words)]
        expected.append({'ids':ids[:300],'total':len(ids)})
    for query,reference in zip(queries,expected):
        catalog.call_method('Search',(query,));pumps,elapsed=settle()
        check(list(get(catalog,'Results'))==reference['ids'] and get(catalog,'MatchCount')==reference['total'],
              'native catalog search matches the reference for '+repr(query))
    catalog.call_method('Search',('/game',));catalog.call_method('Pump')
    check(get(catalog,'Active') and 0<get(catalog,'Cursor')<count,'one catalog Pump leaves a large query incremental')
    old_revision=get(catalog,'Revision');catalog.call_method('Search',('Medical Bed',))
    check(get(catalog,'Revision')!=old_revision and get(catalog,'MatchCount')==0 and len(get(catalog,'Results'))==0,'new query cancels partial results and changes generation')
    settle();check(list(get(catalog,'Results'))==expected[1]['ids'],'cancelled search cannot append stale matches')
    catalog.call_method('Search',('/game',));settle()
    check(len(get(catalog,'Results'))==300 and get(catalog,'MatchCount')>300,'search caps displayed matches while counting the complete dataset')
    catalog.call_method('Cancel');catalog.call_method('Step');catalog.call_method('Pump')
    check(not get(catalog,'Active') and not get(catalog,'Ready') and not get(catalog,'Results'),'cancelled catalog remains idle without results')
    all_shelves=True;wide=False
    for index,shelf in enumerate(source['shelves'],1):
        catalog.call_method('Browse',(index,));settle()
        result=list(get(catalog,'Results'));wanted=list(range(shelf['first']-1,shelf['first']-1+shelf['count']))
        all_shelves &= result==wanted and get(catalog,'MatchCount')==len(wanted)
        if len(wanted)>300:wide |= len(result)>300
    check(all_shelves,'all catalog shelves preserve complete contiguous source membership')
    check(wide,'shelf browsing is not truncated to the search result cap')
    for index in [0,len(source['shelves'])+1,-2]:
        catalog.call_method('Browse',(index,));settle();check(not get(catalog,'Results'),'invalid shelf is an empty completed query')
    for index in range(45):catalog.call_method('Remember',(index,))
    check(list(get(catalog,'Recent'))==list(range(44,4,-1)),'recent catalog items retain the newest forty')
    catalog.call_method('Remember',(18,));recent=[18]+[i for i in range(44,4,-1) if i!=18]
    catalog.call_method('Remember',(-1,));catalog.call_method('Remember',(count,))
    check(list(get(catalog,'Recent'))==recent,'recent items deduplicate and ignore invalid identities')
    catalog.call_method('Browse',(-1,));catalog.call_method('Remember',(100,));settle()
    check(list(get(catalog,'Results'))==recent,'recent browsing snapshots membership while new placement updates history')
