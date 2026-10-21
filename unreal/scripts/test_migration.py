"""Load offline-written GVAS files through Unreal, in the kit's Saved only."""
import os
import json
import tempfile
import sys
import uuid
from pathlib import Path


def run(unreal, repo, root, fixture, check):
    sys.path.insert(0, str(repo / 'tools'))
    from den_save import Codec
    saved = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())).resolve()
    assert saved == Path(os.environ['DENDESIGNER_TEST_SAVED']).resolve()
    codec=Codec()
    key='test_import_'+uuid.uuid4().hex
    files=[]
    try:
        for filename, class_name, store_name, method in [
            ('layout.sav','BP_DenLayoutSave','BP_DenStore','LoadLayout'),
            ('presets.sav','BP_DenPresetLibrary','BP_DenPresetStore','LoadLibrary')]:
            cls,values=codec.decode((repo/'dist/gf-qa/migration-fixtures'/filename).read_bytes())
            values.update(StorageKey=key,Revision=1,ContentID='offline-import-test',WriteCompleteID='offline-import-test',
                          EntryCount=len(values['Entries']),WrittenAt='1792476000',IsDraft=False,DraftBaseRevision=0,DraftBaseID='')
            slot=f'ZComDen/Native/v1/{key}-layout-0'
            path=saved/'SaveGames'/(slot+'.sav')
            assert not path.exists()
            files.append(path)
            path.parent.mkdir(parents=True,exist_ok=True)
            encoded=codec.encode(cls,values)
            path.write_bytes(encoded)
            check(codec.decode(encoded)==(cls,values),'offline codec preserves all '+filename+' fields')
            store=unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(root+store_name))
            loaded,status,bank=store.call_method(method,(key,False,0))
            check(status==1 and loaded is not None and bank==0,'Unreal store accepts offline-written '+filename)
            assert status==1 and loaded is not None
            roundtrip=f'ZComDen/Tests/{key}'
            roundpath=saved/'SaveGames'/(roundtrip+'.sav')
            files.append(roundpath)
            check(unreal.GameplayStatics.save_game_to_slot(loaded,roundtrip,0),'Unreal reserializes imported '+filename)
            reread=codec.decode(roundpath.read_bytes())
            check(reread==(cls,values),'Unreal preserves every imported '+filename+' value, including defaults and nested arrays')
            path.unlink()
            roundpath.unlink()
        # Convert JSON through the user-facing staging utility, then load its
        # exact output bytes under isolated test slots (no key/header rewriting).
        from migrate_layouts import stage
        with tempfile.TemporaryDirectory(prefix='den-import-',dir=saved) as temp:
            source=Path(temp)/'source'
            source.mkdir()
            sample={'format':1,'game':'migration-test','placed':[
                {'id':'p0001','mesh':'/Game/Props/SM_Test.SM_Test','t':[17,18,19],
                 'r':[12,34,56],'s':[1,2,3],'solid':False,
                 'mats':['','/Game/Props/MI_Test.MI_Test']}],
                'stored':[{'id':'p0002','mesh':'/Game/Props/SM_Test.SM_Test','t':[-1,-2,-3]}],
                'vanilla':{'/Game/Hub.Hub:PersistentLevel.Test.Mesh':{'hidden':True,'r':[0,90,0]}}}
            (source/'home.json').write_text(json.dumps(sample))
            (source/'home.draft.json').write_text(json.dumps(dict(sample,draft_at='2026-10-20 01:00')))
            (source/'presets').mkdir()
            (source/'presets/Médecine.json').write_text(json.dumps(sample))
            output=Path(temp)/'staged'
            report=stage(source,output)
            check(len(report['saves'])==3,'JSON importer stages home, unknown-baseline draft and nested preset library')
            for name in report['saves']:
                data=(output/'SaveGames/ZComDen/Native/v1'/name).read_bytes()
                original=codec.decode(data)
                testslot=f'ZComDen/Tests/{key}'
                testpath=saved/'SaveGames'/(testslot+'.sav')
                files.append(testpath)
                testpath.parent.mkdir(parents=True,exist_ok=True)
                testpath.write_bytes(data)
                loaded=unreal.GameplayStatics.load_game_from_slot(testslot,0)
                check(loaded is not None,'Unreal loads exact staged JSON conversion: '+name)
                assert loaded is not None
                check(unreal.GameplayStatics.save_game_to_slot(loaded,testslot,0),'Unreal reserializes staged JSON conversion: '+name)
                check(codec.decode(testpath.read_bytes())==original,'JSON conversion survives Unreal round trip without lost fields: '+name)
                testpath.unlink()
    finally:
        for path in files:
            path.unlink(missing_ok=True)
