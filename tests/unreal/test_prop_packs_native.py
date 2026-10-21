"""Exercise actual pack import graphs: budget, isolation, bad manifests, stable paths and search."""

def run(unreal,check):
    import json
    from runtime_prop_packs import PACK, FIELDS
    from runtime_catalog import array_text
    def setprop(obj,key,value):
        if key in FIELDS:
            value=array_text([(x.x,x.y,x.z) for x in value] if FIELDS[key]=="vector" else value,FIELDS[key])
        else:value=str(value)
        error=unreal.ZComAuthoringLibrary.set_property_from_text(obj,key,value)
        assert not error,error
    from runtime_catalog import CATALOG,metadata
    get=lambda o,n:o.get_editor_property(n)
    data_class=unreal.EditorAssetLibrary.load_blueprint_class(CATALOG)
    pack_class=unreal.EditorAssetLibrary.load_blueprint_class(PACK)
    base=len(metadata()['items'])
    keep=[]
    def pack(ident='qa_furniture',n=2):
        obj=unreal.new_object(pack_class);keep.append(obj)
        for k,value in {'PackID':ident,'Title':'QA furnishings','Author':'Example maker','Version':'1.0',
            'Paths':[f'/QAProps/{ident}/Mesh{i}.Mesh{i}' for i in range(n)],
            'Labels':[f'Chair {i}' for i in range(n)],'Details':['Custom prop']*n,
            'Dimensions':[unreal.Vector(10,20,30)]*n,'Solid':[True]*n,'SearchTexts':['velvet furniture']*n}.items():setprop(obj,k,value)
        return obj
    def catalog():
        obj=unreal.new_object(data_class);keep.append(obj);obj.call_method('Initialize');return obj
    def load(c,packs):
        c.call_method('QueuePropPacks',(packs,));pumps=0
        while get(c,'PacksLoading'):
            c.call_method('PumpPropPacks');pumps+=1
            if pumps>10000:raise AssertionError('pack import stuck')
        return get(c,'Data')
    def results(c,text=None,shelf=None):
        c.call_method('Search',(text,)) if text is not None else c.call_method('Browse',(shelf,))
        for _ in range(10000):
            c.call_method('Pump')
            if not get(c,'Active'):return list(get(c,'Results'))
        raise AssertionError('query stuck')
    c=catalog();a=pack(n=40)
    original=list(get(get(c,'Data'),'Paths'))
    c.call_method('QueuePropPacks',([a],));c.call_method('PumpPropPacks')
    check(get(c,'PacksLoading') and base<=get(get(c,'Data'),'Count')<=base+7,'pack import respects its eight-step batch instead of loading every asset at once')
    while get(c,'PacksLoading'):c.call_method('PumpPropPacks')
    d=get(c,'Data')
    check(get(d,'Count')==base+40 and list(get(d,'Paths'))[:base]==original,'pack import appends without changing shipped row identities')
    check(get(d,'Groups')[-1]=='Prop packs' and get(d,'ShelfLabels')[-1]=='QA furnishings' and get(d,'ShelfCounts')[-1]==40 and get(d,'GroupCounts')[-1]==40,'pack owns a shelf in the shared Prop packs collection')
    check(results(c,text='example maker velvet')==list(range(base,base+40)),'author and tags participate in global tokenized search')
    check(results(c,shelf=len(get(d,'ShelfLabels')))==list(range(base,base+40)),'pack shelf contains all its contiguous rows')
    first=get(a,'Paths')[0]
    check(c.call_method('FindPath',(first,))==base and c.call_method('ReadItem',(base,))[1]==first,'pack entry keeps the original full asset path for placement and saved layouts')
    c.call_method('Remember',(base,));check(results(c,shelf=-1)==[base],'pack assets participate in recent props')
    load(c,[a]);check(get(d,'Count')==base+40,'repeated registration is idempotent')
    c2=catalog();b=pack('other',1);load(c2,[b,a])
    check(c2.call_method('FindPath',(first,))==base+1,'path identity survives different provider ordering')
    check(get(get(c2,'Data'),'Count')==base+41 and get(get(catalog(),'Data'),'Count')==base,'catalog instances never mutate shared class defaults')
    c3=catalog();load(c3,[a,pack('QA_FURNITURE')]);check(get(get(c3,'Data'),'Count')==base and len(get(c3,'PackIssues'))==2,'case-insensitive duplicate pack IDs reject both providers independent of order')
    for field,value in [('SchemaVersion',2),('PackID','../bad'),('Title',''),('Labels',['wrong length']),('Paths',[])]:
        bad=pack();setprop(bad,field,value);c4=catalog();load(c4,[bad])
        check(get(get(c4,'Data'),'Count')==base and bool(get(c4,'PackIssues')),'invalid manifest rejected without partial shelves: '+field)
    bad=pack(n=4);setprop(bad,'Paths',[original[0],'/NoObject','/QA/Bad.Bad:Part','/QA/Good.Good'])
    c5=catalog();d5=load(c5,[bad]);check(get(d5,'Count')==base+1 and get(d5,'Paths')[-1]=='/QA/Good.Good' and get(d5,'ShelfCounts')[-1]==1,'duplicate vanilla paths and invalid paths are skipped while good rows survive')
    bad=pack(n=1);setprop(bad,'Dimensions',[unreal.Vector(-1,2,3)]);c6=catalog();load(c6,[bad])
    check(get(get(c6,'Data'),'Count')==base and 'Prop packs' not in list(get(get(c6,'Data'),'Groups')),'all-invalid rows create no empty collection or shelf')
    c7=catalog();load(c7,[pack('large',2049)]);check(get(get(c7,'Data'),'Count')==base,'oversized manifest rejected before importing rows')
    c8=catalog();load(c8,[a]*33);check(not get(c8,'PacksLoading') and get(get(c8,'Data'),'Count')==base and bool(get(c8,'PackIssues')),'provider cap bounds discovery work')
    c9=catalog();load(c9,[None]);check(not get(c9,'PacksLoading') and get(get(c9,'Data'),'Count')==base,'destroyed or null provider is skipped safely')
    check(catalog().call_method('FindPath',(first,))==-1,'removing a pack removes its catalog rows without changing any stored layout')
