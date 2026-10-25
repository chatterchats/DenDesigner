"""Real Blueprint cache keys, framing maths and queue ownership; no headless rendering."""
import math


def run(unreal,check):
    from runtime_thumbnails import STUDIO
    from runtime_thumbnail_queue import QUEUE
    from runtime_catalog import metadata
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    studio=actors.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class(STUDIO),unreal.Vector(0,0,-100000),unreal.Rotator(),transient=True)
    worker=actors.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class(QUEUE),unreal.Vector(),unreal.Rotator(),transient=True)
    get=lambda obj,name:obj.get_editor_property(name)
    def expected_filename(path):
        h=5381
        for b in path.encode():h=(h*33+b)%2**32
        name=path.rsplit('.',1)[-1]
        name=''.join(c if c.isascii() and (c.isalnum() or c in '_-') else '_' for c in name)
        return name+'_'+format(h,'08x')+'.png'
    try:
        data=metadata();paths=[data['items'][s['first']-1]['path'] for s in data['shelves']]
        paths+=['/Engine/BasicShapes/Cube.Cube','/Game/Path With Spaces/Asset-Name.Asset-Name','/Game/A/A.Name#bad']
        actual=[studio.call_method('CacheFileName',(p,)) for p in paths]
        check(actual==[expected_filename(p) for p in paths],'native cache filenames remain deterministic across every shelf and sanitized names')
        check(len(set(actual))==len(set(paths)),'sampled thumbnail filenames distinguish full asset paths')
        for bad in ['', '../outside', '/NoObject', '/Game/Mesh.Mesh:Component']:
            check(studio.call_method('CacheFileName',(bad,))=='','invalid thumbnail path cannot become a cache filename: '+bad)
        directory,name,full=studio.call_method('CachePath',(paths[0],))
        check(directory.replace('\\','/').endswith('/Saved/ZComDen/thumbs/') and name==expected_filename(paths[0]) and full==directory+name,
              'native thumbnail cache is confined to its separate Saved folder')
        view=(.75,-.55,.45);norm=lambda a:tuple(x/math.sqrt(sum(y*y for y in a)) for x in a)
        f=norm(tuple(-x for x in view));r=norm((-f[1],f[0],0));u=(r[1]*f[2]-r[2]*f[1],r[2]*f[0]-r[0]*f[2],r[0]*f[1]-r[1]*f[0]);dot=lambda a,b:sum(x*y for x,y in zip(a,b))
        good=True
        for e in [(0,0,0),(50,50,50),(500,1,.1),(.1,2,1000),(1,400,2),(20000,10000,1),(23.7,104.1,8.2)]:
            corners=[(x*e[0],y*e[1],z*e[2]) for x in [-1,1] for y in [-1,1] for z in [-1,1]]
            expected=max([1]+[max(abs(dot(c,r)),abs(dot(c,u)))/math.tan(math.radians(15))-dot(c,f) for c in corners])*1.08
            actual=studio.call_method('FrameDistance',(unreal.Vector(*e),))
            good &= abs(actual-expected)<max(1e-6,expected*1e-6)
        check(good,'native framing matches corner projection for cubes, flat, thin and very large meshes')
        bad,status=worker.call_method('Request',('../unsafe',));check(bad is None and status==2 and not list(get(worker,'PendingPaths')),'invalid request enqueues no work')
        path='/Game/DenNativeTests/ThumbnailProbe.UniqueA'
        for _ in range(2):texture,status=worker.call_method('Request',(path,))
        check(texture is None and status==0 and list(get(worker,'PendingPaths'))==[path] and get(worker,'Job') is None,
              'multiple consumers deduplicate one request without loading inside the request call')
        worker.call_method('BeginNext');job=get(worker,'Job')
        check(job is not None and get(worker,'Phase')==1 and not list(get(worker,'PendingPaths')),
              'worker starts one deferred asset request after a disk cache miss')
        texture=unreal.new_object(unreal.Texture2D)
        worker.call_method('FinishThumbnail',(texture,))
        result,status=worker.call_method('Request',(path,))
        check(result==texture and status==1 and not list(get(worker,'PendingPaths')) and get(worker,'Job') is None,
              'completed thumbnail is owned by the native cache and reused by every consumer')
        for i in range(96):worker.call_method('Request',('/Game/DenNativeTests/Queued.Item'+str(i),))
        check(len(get(worker,'CachePaths'))==96 and path not in list(get(worker,'CachePaths')) and len(get(worker,'PendingPaths'))==96,
              'cache evicts completed entries and bounds pending requests to 96')
        worker.call_method('Request',('/Game/DenNativeTests/Overflow.Item',))
        check(len(get(worker,'CachePaths'))==96 and len(get(worker,'PendingPaths'))==96,'full pending cache rejects additional work until capacity is available')
        worker.call_method('CancelPending');check(not list(get(worker,'CachePaths')) and not list(get(worker,'PendingPaths')) and get(worker,'Phase')==0,
              'query cancellation removes pending entries and their queue together')
        worker.call_method('Request',(path,));worker.call_method('BeginNext')
        # NextAt throttles the next job; cancellation is valid with or without a live job.
        job=get(worker,'Job');worker.call_method('CancelPending')
        check(get(worker,'Job') is None and (job is None or not unreal.SystemLibrary.is_valid(job)),
              'cancellation destroys a pending latent callback target')
        worker.call_method('ReleaseCaptureStudio');check(get(worker,'Studio') is None,'studio teardown releases its actor independently of the cache')
    finally:
        actors.destroy_actor(worker);actors.destroy_actor(studio)
