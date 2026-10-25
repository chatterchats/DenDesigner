"""Exercise the cooked store's Blueprint functions with real files in the kit only."""
import os
import uuid
from pathlib import Path


def run(unreal, root, layout, source, fixture, check):
    saved = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())).resolve()
    expected = Path(os.environ['DENDESIGNER_TEST_SAVED']).resolve()
    assert saved == expected, f'refusing storage tests outside kit Saved: {saved}'
    store = unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(root + 'BP_DenStore'))
    prefix = 'test_storage_' + uuid.uuid4().hex
    keys = [prefix + suffix for suffix in ['_home', '_campaign', '_broken', '_failure', '_future']]
    paths = []

    def slot(key, bank, draft=False):
        return store.call_method('BankSlot', (key, bank, draft))

    def path(key, bank, draft=False):
        name = slot(key, bank, draft)
        result = saved / 'SaveGames' / (name + '.sav')
        assert result.is_relative_to(saved / 'SaveGames/ZComDen/Native/v1')
        assert result.name.startswith(prefix)
        return result

    for key in keys:
        for draft, count in [(False,6),(True,2)]:
            paths.extend(path(key, bank, draft) for bank in range(count))

    def load(key, draft=False, before=0):
        return store.call_method('LoadLayout', (key,draft,before))

    def save(key, doc, draft=False, base_revision=0, base_id=''):
        return store.call_method('SaveLayout', (key,doc,draft,base_revision,base_id))

    def prop(obj, name):
        return obj.get_editor_property(name)

    def clone(doc):
        return store.call_method('CloneLayout', (doc,))

    def payloads(key, draft=False):
        return {p.name:p.read_bytes() for i in range(2 if draft else 6)
                if (p := path(key,i,draft)).is_file()}

    try:
        for key in ['', '../home', 'a/b', 'a\\b', 'home.json', 'home name', 'Étage', 'x:y', 'a\n', 'a'*97]:
            check(not store.call_method('ValidKey', (key,)), f'store rejects unsafe key {key!r}')
        check(all(store.call_method('ValidKey',(key,)) for key in ['home','campaign-BA3302BC4165EB931E86A39BFF208F71','preset_abc-123']), 'store accepts safe layout keys')
        check(slot('home',0) == 'ZComDen/Native/v1/home-layout-0' and slot('home',0,True) == 'ZComDen/Native/v1/home-draft-0', 'store slots are isolated under the mod namespace')
        none,status,bank = load(keys[0])
        check(none is None and status == 0 and bank == -1, 'missing layout is distinct from broken layout')
        check(load('../home')[1] == 5 and load(keys[0],before=-1)[1] == 5, 'invalid load requests cannot reach slot IO')
        check(save('../home',source)[1] == 5 and save(keys[0],None)[1] == 7, 'invalid save requests are rejected')
        doc=clone(source)
        before_source=(prop(doc,'Revision'),prop(doc,'StorageKey'),prop(doc,'ContentID'))
        ids=[]
        for n in range(1,8):
            fixture.call_method('SetDisplayName', (doc, f'Version {n}'))
            written,status=save(keys[0],doc)
            assert status == 1 and written is not None
            ids.append(prop(written,'ContentID'))
            check(prop(written,'Revision') == n and prop(written,'DisplayName') == f'Version {n}', f'layout generation {n} readback verified')
        check(len(set(ids)) == 7 and all(ids), 'each save gets a distinct content identity')
        check((prop(doc,'Revision'),prop(doc,'StorageKey'),prop(doc,'ContentID')) == before_source, 'saving leaves the working document metadata unchanged')
        current,status,bank=load(keys[0])
        check(status == 1 and bank == 0 and prop(current,'Revision') == 7, 'highest valid generation wins after rotation')
        check(prop(current,'EntryCount') == len(prop(source,'Entries')) and prop(current,'WriteCompleteID') == prop(current,'ContentID'), 'stored count and completion identity match payload')
        check(prop(current,'WrittenAt').isdigit() and int(prop(current,'WrittenAt')) > 0, 'written timestamp recorded in UTC epoch seconds')
        revisions=[]
        before=0
        for _ in range(7):
            previous,status,_ = load(keys[0],before=before)
            if previous is None:
                check(status == 0, 'no older backup reports absent')
                break
            before=prop(previous,'Revision')
            revisions.append(before)
        check(revisions == [7,6,5,4,3,2] and len(payloads(keys[0])) == 6, 'current layout plus exactly five prior generations retained')
        other,status=save(keys[1],doc)
        check(status == 1 and prop(other,'Revision') == 1 and prop(load(keys[0])[0],'Revision') == 7, 'independent campaign key leaves shared home untouched')

        # Drafts carry an explicit saved baseline identity, and never rotate home banks.
        home_bytes=payloads(keys[0])
        base_id=prop(current,'ContentID')
        check(save(keys[0],doc,True,7,'')[1] == 7, 'draft baseline needs its matching content identity')
        for n in [1,2]:
            draft,status=save(keys[0],doc,True,7,base_id)
            assert status == 1
            check(prop(draft,'IsDraft') and prop(draft,'Revision') == n and prop(draft,'DraftBaseRevision') == 7 and prop(draft,'DraftBaseID') == base_id, f'draft {n} has independent revision and exact baseline')
        check(payloads(keys[0]) == home_bytes and len(payloads(keys[0],True)) == 2, 'draft writes do not alter saved layouts or their backups')
        path(keys[0],1,True).write_bytes(b'')
        draft,status,_=load(keys[0],True)
        check(status == 2 and prop(draft,'Revision') == 1, 'interrupted draft write recovers prior complete draft')
        check(store.call_method('ClearDraft',(keys[0],)) and not payloads(keys[0],True) and payloads(keys[0]) == home_bytes, 'clearing drafts leaves all canonical backups intact')
        check(store.call_method('ClearDraft',(keys[0],)), 'clearing an absent draft succeeds')

        # A torn payload after its header can still instantiate a SaveGame. The
        # completion identity must be checked, not merely a non-null load result.
        latest=path(keys[0],0)
        good=latest.read_bytes()
        marker=good.find(b'WriteCompleteID\x00')
        entries=good.find(b'Entries\x00')
        check(marker > entries > 0, 'completion field is serialized after the entries payload')
        assert marker > entries > 0
        latest.write_bytes(good[:marker-4])
        recovered,status,bank=load(keys[0])
        check(status == 2 and prop(recovered,'Revision') == 6 and bank == 5, 'incomplete latest payload falls back to previous layout')
        replacement,status=save(keys[0],doc)
        check(status == 1 and prop(replacement,'Revision') == 7 and prop(replacement,'ContentID') not in ids, 'save after recovery uses fresh identity even when revision is reused')
        check(load(keys[0])[1] == 1, 'replacement restores a healthy rotation')

        # Every remaining file is checked for structural consistency and schema.
        forged=clone(replacement)
        fixture.call_method('SetEntryCount', (forged,9999))
        assert unreal.GameplayStatics.save_game_to_slot(forged,slot(keys[0],0),0)
        check(load(keys[0])[1] == 2 and prop(load(keys[0])[0],'Revision') == 6, 'entry-count mismatch is rejected')
        for i in range(6):
            path(keys[2],i).parent.mkdir(parents=True,exist_ok=True)
            path(keys[2],i).write_bytes(b'')
        broken_bytes=payloads(keys[2])
        check(load(keys[2])[1] == 3 and save(keys[2],doc)[1] == 3 and payloads(keys[2]) == broken_bytes, 'all-broken layout is reported and never silently overwritten')
        future,status=save(keys[4],doc)
        assert status == 1
        fixture.call_method('SetSchemaVersion', (future,2))
        assert unreal.GameplayStatics.save_game_to_slot(future,slot(keys[4],0),0)
        future_bytes=payloads(keys[4])
        check(load(keys[4])[1] == 4 and save(keys[4],doc)[1] == 4 and payloads(keys[4]) == future_bytes, 'newer schema blocks downgrade and overwrite')

        # Simulate an IO failure using a directory in place of the NEXT file.
        saved_doc,status=save(keys[3],doc)
        assert status == 1
        previous=payloads(keys[3])
        obstruction=path(keys[3],1)
        obstruction.mkdir()
        failed,status=save(keys[3],doc)
        check(failed is None and status == 6 and payloads(keys[3]) == previous, 'failed write leaves the current saved copy intact')
        obstruction.rmdir()
        check(prop(load(keys[3])[0],'Revision') == 1, 'current copy loads after write failure')
    finally:
        # Only UUID-prefixed fixture paths within the kit were ever registered.
        for p in paths:
            if p.is_dir():
                p.rmdir()
            elif p.exists():
                p.unlink()
