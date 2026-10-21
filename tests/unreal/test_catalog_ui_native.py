"""Exercise catalog presentation objects and native event routing without Slate."""
def run(unreal,host,bus,get,check):
    from runtime_catalog import metadata
    from runtime_catalog_ui import DEFAULT_SHELF
    source=metadata();items=source['items']
    version=get(get(host,'History'),'Version')
    def event(name,arg=''):
        bus.call_method('Emit',(2,name,arg,0.,unreal.Vector()))
        host.call_method('ProcessEditorEvents')
    def rows():return list(get(host,'CatalogItems'))
    def shelves():return list(get(host,'CatalogShelves'))
    def settle():
        max_batch=0
        for _ in range(3000):
            before=len(rows());host.call_method('PollCatalogUI');max_batch=max(max_batch,len(rows())-before)
            provider=get(host,'CatalogProvider')
            if get(provider,'Ready') and not get(host,'CatalogRendering') and get(host,'CatalogRenderRevision')==get(provider,'Revision'):
                check(max_batch<=8,'catalog presentation respects its eight-item batch limit')
                return
        raise AssertionError('catalog UI did not finish')
    event('catalog');settle();provider=get(host,'CatalogProvider')
    selected_shelf=source['shelves'][DEFAULT_SHELF-1]
    first=selected_shelf['first']-1
    check(len(rows())==selected_shelf['count'] and get(rows()[0],'Title')==items[first]['label'],
          'first catalog opening browses the Den collection and its first shelf')
    check(get(shelves()[0],'Key')=='recent' and get(shelves()[1],'Key')=='collections'
          and len(shelves())==2+sum(s['collection']=='Den' for s in source['shelves']),
          'Den navigation contains recent, back and every Den shelf')
    revision=get(provider,'Revision')
    check(all(get(row,'EditorBus')==bus and get(row,'Key')==f'{revision}:{first+i}'
              and get(row,'AssetPath')==items[first+i]['path'] and get(row,'Preview')=='Preview unavailable' and get(row,'Detail')==items[first+i]['detail'] for i,row in enumerate(rows())),
          'native item objects carry fonts/input bus, revision identity, path and dimensions')
    event('search','Medical Bed');settle()
    expected=[e for e in items if all(w in e['search'] for w in ['medical','bed'])]
    check([get(row,'AssetPath') for row in rows()]==[e['path'] for e in expected],
          'native search event populates matching item objects')
    event('shelf','collections')
    check(len(shelves())==1+len(source['collections']) and get(shelves()[1],'Title').startswith('Den'),
          'all-collections navigation is grouped with Den first')
    group=next(i for i,c in enumerate(source['collections']) if c['key']=='Bespin')
    event('shelf','group:'+str(group));settle()
    first_bespin=next(i for i,s in enumerate(source['shelves'],1) if s['collection']=='Bespin')
    check(get(host,'CatalogGroup')==group and get(host,'CatalogShelf')==first_bespin and get(host,'CatalogQuery')=='',
          'collection selection clears search and browses its first shelf')
    event('shelf',str(DEFAULT_SHELF));settle()
    check(len(rows())==selected_shelf['count'],'numeric shelf events select the requested complete shelf')
    revision=get(provider,'Revision')
    for invalid in ['nonsense','01','group:x','group:-1','group:99999','99999']:
        event('shelf',invalid)
    check(get(provider,'Revision')==revision and get(host,'CatalogShelf')==DEFAULT_SHELF,
          'malformed navigation keys cannot change query or shelf')
    event('search','/game')
    while get(provider,'Active'):provider.call_method('Pump')
    host.call_method('PollCatalogUI');oldrows=rows()
    check(0<len(oldrows)<=8 and get(host,'CatalogRendering'),'large result sets begin incremental presentation')
    oldkey=get(oldrows[0],'Key');event('search','Medical Bed')
    check(not rows() and not get(host,'CatalogRendering'),'new query immediately releases stale presentation items')
    settle();check(oldkey.split(':')[0]!=str(get(provider,'Revision')) and [get(row,'AssetPath') for row in rows()]==[e['path'] for e in expected],
                   'replaced result batches cannot append stale cards')
    provider.call_method('Remember',(100,));event('shelf','recent');settle()
    check(len(rows())==1 and get(rows()[0],'AssetPath')==items[100]['path'],'recent navigation shows the remembered prop')
    event('search','Medical Bed');settle();event('catalog')
    check(get(host,'ActivePanel')=='' and not rows() and not get(provider,'Active'),
          'closing catalog cancels work and releases its item list')
    revision=get(provider,'Revision');event('search','stale hidden text')
    check(get(provider,'Revision')==revision and get(host,'CatalogQuery')=='Medical Bed',
          'late events from a hidden catalog cannot replace the retained query')
    event('catalog');settle()
    check([get(row,'AssetPath') for row in rows()]==[e['path'] for e in expected],'reopening catalog resumes its retained search')
    service=get(host,'PreferenceService')
    check(service.call_method('RememberRecent',(items[100]['path'],))[1]==1 and
          service.call_method('RememberRecent',(items[200]['path'],))[1]==1 and
          service.call_method('RememberRecent',('/Game/Unavailable.Missing',))[1]==1,
          'catalog recents persist through the native preferences service')
    event('catalog');host.call_method('ReleaseCatalog')
    check(get(host,'CatalogProvider') is None and not shelves() and not rows(),'catalog teardown releases provider and presentation objects')
    host.call_method('EnsureCatalog')
    fresh=get(host,'CatalogProvider')
    check(fresh!=provider and list(get(fresh,'Recent'))==[200,100],
          'fresh catalog restores saved paths in order and safely skips unavailable assets')
    host.call_method('ReleaseCatalog')
    check(get(get(host,'History'),'Version')==version,'catalog navigation never changes layout history')
