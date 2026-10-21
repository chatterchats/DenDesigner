"""Native session integration: real Blueprint history, async world edits and SaveGame IO."""
import os
import uuid
from pathlib import Path


def run(unreal,root,fixture,field,field_name,check):
    saved=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())).resolve()
    assert saved==Path(os.environ['DENDESIGNER_TEST_SAVED']).resolve()
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    klass=unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenSession')
    store=unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenLayouts'))
    doc_class=unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenLayoutSave')
    mesh=unreal.load_asset('/Engine/BasicShapes/Cube')
    prefix='test_session_'+uuid.uuid4().hex
    keys=[prefix+'_'+n for n in ['main','failure','conflict','recovery','mismatch','bad-draft','teardown']]
    sessions=[]
    paths=[]
    def get(obj,name):return obj.get_editor_property(name)
    def accepted(value):return value[-1] if isinstance(value,tuple) else value
    def load(key,draft=False):return store.call_method('LoadLayout',(key,draft,0))
    def path(key,bank,draft=False):
        slot=store.call_method('BankSlot',(key,bank,draft));p=saved/'SaveGames'/(slot+'.sav')
        assert p.is_relative_to(saved/'SaveGames/ZComDen/Native/v1') and p.name.startswith(prefix)
        return p
    for key in keys:
        for draft,n in [(False,6),(True,2)]:paths.extend(path(key,i,draft) for i in range(n))
    def entry(key='p1',pos=(10,20,30),kind=0):
        row=fixture.call_method('MakeEntry',(kind,key,unreal.Vector(*pos)))
        for name,value in [('Mesh',mesh.get_path_name()),('Materials',[]),('HasFingerprint',False)]:row.set_editor_property(field_name(name),value)
        return row
    def mutation(row,present=True):return fixture.call_method('MakeMutation',(row,present))
    def document(rows):
        doc=unreal.GameplayStatics.create_save_game_object(doc_class)
        for row in rows:assert doc.call_method('WriteEntry',(row,True))
        return doc
    def write(key,doc,draft=False,baseline=None):
        return store.call_method('SaveLayout',(key,doc,draft,get(baseline,'Revision') if baseline else 0,get(baseline,'ContentID') if baseline else ''))
    def spawn():
        actor=actors.spawn_actor_from_class(klass,unreal.Vector(),unreal.Rotator(),transient=True);sessions.append(actor)
        fixture.call_method('SetApplyRetryInterval',(actor,0.0));fixture.call_method('SetApplyMaxRetries',(actor,0))
        return actor
    def open_(key):
        actor=spawn();doc,status,_=load(key)
        assert actor.call_method('OpenSession',(key,doc,status));drain(actor)
        return actor
    def drain(actor):
        for _ in range(200):
            if not get(actor,'Busy'):return
            actor.call_method('Pump')
            job=get(actor,'PendingJob')
            if job is not None and unreal.SystemLibrary.is_valid(job):
                job.call_method('ReceiveTick',(1/60,));unreal.ZComAuthoringLibrary.process_test_latent_actions(actor)
        raise AssertionError('session queue stuck in phase '+str(get(actor,'Phase')))
    def edit(actor,rows,label='Edit'):
        ok=accepted(actor.call_method('CommitEdit',(rows,label,'')))
        if ok:drain(actor)
        return ok
    def dirty(actor):return get(actor,'History').call_method('IsDirty')
    def xpos(doc):return round(field(get(doc,'Entries')[0],'Position').x,3)
    def worldx(actor):return round(get(actor,'Placed')[0].get_actor_location().x,3)
    def abandon(actor):
        fixture.call_method('SetSessionEditing',(actor,False))
        actor.call_method('CancelWork');actor.call_method('Clear');actors.destroy_actor(actor)
    def files(key,draft=False):return {p.name:p.read_bytes() for i in range(2 if draft else 6) if (p:=path(key,i,draft)).is_file()}
    try:
        main=open_(keys[0])
        check(not dirty(main) and get(main,'Editing') and not get(main,'RecoveryPending'),'new native session opens a clean empty working layout')
        check(not main.call_method('OpenSession',(keys[1],None,0)),'opening another layout cannot silently replace an active session')
        check(edit(main,[mutation(entry())]) and dirty(main) and worldx(main)==10,'session commit updates history, working data and the live prop')
        due=get(main,'DraftDue')
        check(edit(main,[mutation(entry(pos=(20,20,30)))]) and get(main,'DraftDue')==due,'continued editing does not postpone the pending autosave deadline')
        fixture.call_method('SetSessionDraftEnabled',(main,False))
        fixture.call_method('SetSessionDraftDue',(main,0.0));main.call_method('PollDraft')
        check(not main.call_method('FlushDraft') and not files(keys[0],True), 'disabled draft preference blocks polling and explicit flush while keeping edits')
        fixture.call_method('SetSessionDraftEnabled',(main,True))
        check(main.call_method('FlushDraft') and load(keys[0],True)[1]==1 and xpos(load(keys[0],True)[0])==20,'native session flush writes an isolated recovery draft')
        draft_bytes=files(keys[0],True)
        check(not main.call_method('DiscardRecovery') and files(keys[0],True)==draft_bytes,'recovery discard cannot erase the active session draft when no recovery choice is pending')
        check(main.call_method('FlushDraft') and files(keys[0],True)==draft_bytes,'unchanged session flush does not rotate identical drafts')
        check(main.call_method('SaveCurrent') and not dirty(main),'verified canonical save marks the history version clean')
        baseline=load(keys[0])[0]
        check(xpos(baseline)==20 and get(baseline,'IsDraft') is False and load(keys[0],True)[1]==0,'save writes the working layout and clears its recovery draft')
        check(edit(main,[mutation(entry(pos=(30,20,30)))]),'post-save edit accepted')
        fixture.call_method('SetSessionDraftDue',(main,0.0));main.call_method('PollDraft')
        check(load(keys[0],True)[1]==1 and xpos(load(keys[0],True)[0])==30,'scheduled draft polling persists dirty data')
        check(main.call_method('UndoEdit'),'session undo accepted');drain(main)
        check(worldx(main)==20 and xpos(get(main,'WorkingDocument'))==20 and not dirty(main),'undo updates the live prop and returns to the saved history boundary')
        main.call_method('FlushDraft')
        check(load(keys[0],True)[1]==0,'undo back to saved state removes an obsolete draft')
        check(main.call_method('RedoEdit'),'session redo accepted');drain(main)
        check(worldx(main)==30 and dirty(main),'redo restores the changed data and world state')
        # Repeated-key changes must reverse in reverse order, matching History.
        check(edit(main,[mutation(entry(pos=(40,20,30))),mutation(entry(pos=(50,20,30)))]),'multi-mutation edit commits as one history step')
        assert main.call_method('UndoEdit');drain(main)
        check(worldx(main)==30 and xpos(get(main,'WorkingDocument'))==30,'session undo reverses repeated-identity mutations in reverse order')
        assert main.call_method('RedoEdit');drain(main)
        check(worldx(main)==50,'session redo preserves forward mutation order')
        assert edit(main,[mutation(entry(pos=(50,20,30)),False),mutation(entry(pos=(50,20,30),kind=1))]),'store edit failed'
        check(len(get(main,'Placed'))==0 and field(get(get(main,'WorkingDocument'),'Entries')[0],'Kind')==1,'session stores a placed prop without discarding its data')
        assert main.call_method('UndoEdit');drain(main)
        check(worldx(main)==50,'undo of store restores the placed prop')
        invalid=entry();invalid.set_editor_property(field_name('Key'),'')
        prior_entries=str(get(get(main,'WorkingDocument'),'Entries'));prior_steps=len(get(get(main,'History'),'UndoSteps'))
        check(not edit(main,[mutation(invalid)]) and not get(main,'Busy') and len(get(get(main,'History'),'UndoSteps'))==prior_steps and str(get(get(main,'WorkingDocument'),'Entries'))==prior_entries,'invalid history batch cancels queued world work and leaves the working document unchanged')
        assert accepted(main.call_method('CommitEdit',([mutation(entry(pos=(60,20,30)))],'Pending','')))
        check(not main.call_method('SaveCurrent') and not main.call_method('UndoEdit'),'save and history commands are refused while world application is pending')
        check(main.call_method('CloseSession',(False,)) and not get(main,'Editing'),'discard can close and cancel in-flight work');drain(main)
        check(worldx(main)==20 and xpos(get(main,'WorkingDocument'))==20 and load(keys[0],True)[1]==0,'discard restores the saved baseline and clears drafts')
        abandon(main)

        failure=open_(keys[1]);assert edit(failure,[mutation(entry(pos=(100,0,0)))])
        blocked=path(keys[1],0);blocked.parent.mkdir(parents=True,exist_ok=True);blocked.mkdir()
        check(not failure.call_method('CloseSession',(True,)) and get(failure,'LastStatus')==6 and get(failure,'Editing') and dirty(failure),'failed save keeps the editor open and retains unsaved work')
        blocked.rmdir();check(failure.call_method('SaveCurrent'),'save succeeds after the file obstruction is removed')
        assert edit(failure,[mutation(entry(pos=(101,0,0)))])
        draft_block=path(keys[1],0,True);draft_block.mkdir()
        check(not failure.call_method('FlushDraft') and get(failure,'LastDraftStatus')==6 and get(failure,'DraftPending'),'draft write failure remains pending with an explicit failure status')
        due=get(failure,'DraftDue');failure.call_method('PollDraft')
        check(get(failure,'DraftDue')==due,'failed autosave waits for its retry deadline instead of writing every frame')
        draft_block.rmdir();fixture.call_method('SetSessionDraftDue',(failure,0.0));failure.call_method('PollDraft')
        check(not get(failure,'DraftPending') and xpos(load(keys[1],True)[0])==101,'draft retry succeeds after the obstruction is removed')
        abandon(failure)

        conflict=open_(keys[2]);assert edit(conflict,[mutation(entry(pos=(200,0,0)))]) and conflict.call_method('SaveCurrent')
        assert edit(conflict,[mutation(entry(pos=(201,0,0)))])
        assert write(keys[2],document([entry(pos=(299,0,0))]))[1]==1
        external=files(keys[2])
        check(not conflict.call_method('SaveCurrent') and get(conflict,'LastStatus')==8 and files(keys[2])==external and dirty(conflict),'external canonical changes refuse overwrite and preserve both disk and working layouts')
        abandon(conflict)

        recovery=open_(keys[3]);assert edit(recovery,[mutation(entry(pos=(300,0,0)))]) and recovery.call_method('SaveCurrent')
        assert edit(recovery,[mutation(entry(pos=(301,0,0)))]) and recovery.call_method('FlushDraft')
        abandon(recovery)
        recovery=open_(keys[3])
        check(get(recovery,'RecoveryPending') and get(recovery,'RecoveryMatchesBase') and worldx(recovery)==300,'reopening offers a matching draft without applying it automatically')
        check(not edit(recovery,[mutation(entry(pos=(399,0,0)))]) and not recovery.call_method('CloseSession',(False,)),'unresolved recovery cannot be silently replaced by an edit or discard-close')
        check(recovery.call_method('RecoverDraft',(False,)),'explicit recovery accepts a matching baseline');drain(recovery)
        check(worldx(recovery)==301 and dirty(recovery) and xpos(load(keys[3])[0])==300,'recovered draft is dirty working data and does not overwrite the canonical layout')
        check(recovery.call_method('DiscardCurrent'),'recovered session can discard back to its saved baseline');drain(recovery)
        check(worldx(recovery)==300 and load(keys[3],True)[1]==0,'discard after recovery restores the pre-crash canonical baseline')
        abandon(recovery)

        canonical,status=write(keys[4],document([entry(pos=(400,0,0))]));assert status==1
        assert write(keys[4],document([entry(pos=(401,0,0))]),True)[1]==1
        mismatch=open_(keys[4])
        check(get(mismatch,'RecoveryPending') and not get(mismatch,'RecoveryMatchesBase'),'legacy draft with unknown baseline is visibly distinct from a matching draft')
        check(not mismatch.call_method('RecoverDraft',(False,)) and get(mismatch,'LastStatus')==10 and worldx(mismatch)==400,'mismatched or unknown draft baseline requires explicit acceptance')
        check(mismatch.call_method('RecoverDraft',(True,)),'explicit mismatch acceptance restores the draft');drain(mismatch)
        check(worldx(mismatch)==401 and dirty(mismatch),'accepted legacy recovery is unsaved working data')
        assert mismatch.call_method('FlushDraft');abandon(mismatch)
        mismatch=open_(keys[4]);check(mismatch.call_method('DiscardRecovery') and not get(mismatch,'RecoveryPending') and worldx(mismatch)==400 and load(keys[4],True)[1]==0,'explicitly discarding recovery preserves the canonical layout')
        abandon(mismatch)

        badpath=path(keys[5],0,True);badpath.parent.mkdir(parents=True,exist_ok=True);badpath.write_bytes(b'broken fixture')
        bad=open_(keys[5]);check(get(bad,'RecoveryPending') and get(bad,'LastDraftStatus')==3 and not edit(bad,[mutation(entry())]),'corrupt recovery data is surfaced before edits can replace it')
        check(bad.call_method('DiscardRecovery') and load(keys[5],True)[1]==0,'explicit recovery discard can remove corrupt draft banks')
        abandon(bad)

        teardown=open_(keys[6]);assert edit(teardown,[mutation(entry(pos=(500,0,0)))])
        live_props=list(get(teardown,'Placed'))
        teardown.call_method('ReceiveEndPlay',(unreal.EndPlayReason.LEVEL_TRANSITION,))
        check(not get(teardown,'Editing') and not get(teardown,'Busy') and len(get(teardown,'Placed'))==0 and load(keys[6],True)[1]==1 and xpos(load(keys[6],True)[0])==500,'level teardown flushes unsaved data, cancels work and releases world bindings')
        check(not edit(teardown,[mutation(entry(pos=(599,0,0)))]),'a torn-down session cannot accept another editor command')
        # A real world transition destroys all level actors. This commandlet
        # invokes only the lifecycle event, so clean those world actors explicitly.
        for actor in live_props:
            if unreal.SystemLibrary.is_valid(actor):actors.destroy_actor(actor)
        abandon(teardown)
    finally:
        for actor in reversed(sessions):
            if unreal.SystemLibrary.is_valid(actor):abandon(actor)
        for p in paths:
            if p.is_dir():p.rmdir()
            elif p.exists():p.unlink()
