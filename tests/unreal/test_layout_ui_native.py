"""Native Layouts-panel event routing, preset transactions, scope and recovery."""
import uuid

def run(unreal,host,bus,fixture,get,field,field_name,check,settle,command,set_,saved):
    home_key=get(host,'SessionKey');home_doc=get(host,'BaselineDocument');home_status=get(host,'OpenedStatus')
    library_key=get(host,'PresetStorageKey');campaign=uuid.uuid4().hex.upper();campaign_key='campaign-'+campaign
    assert home_key.startswith('test_editor_') and library_key.startswith('test_editor_')
    storage=get(host,'Storage');home_status=storage.call_method('LoadLayout',(home_key,False,0))[1];root=saved/'SaveGames/ZComDen/Native/v1'
    def files(key):return {p:p.read_bytes() for p in root.glob(key+'-*.sav') if p.is_file()}
    home_before=files(home_key);library_before=files(library_key);campaign_before=files(campaign_key)
    assert not library_before and not campaign_before
    def emit(name,arg=''):
        bus.call_method('Emit',(2,name,arg,0.,unreal.Vector()));host.call_method('ProcessEditorEvents');host.call_method('PumpEditorMutations');settle()
    def refresh():host.call_method('RefreshLayoutPresets')
    def names():return list(get(host,'PresetNames'))
    def select(name):
        index=names().index(name);emit('preset',get(get(host,'PresetRows')[index],'Key'))
    def values():return list(get(get(host,'WorkingDocument'),'Entries'))
    def count():return len(values())
    def version():return get(get(host,'History'),'Version')
    def add(key):
        row=fixture.call_method('MakeEntry',(1,key,unreal.Vector(100,200,300)))
        row.set_editor_property(field_name('Mesh'),'/Engine/BasicShapes/Cube.Cube')
        row.set_editor_property(field_name('Materials'),['/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial'])
        assert host.call_method('CommitEdit',([fixture.call_method('MakeMutation',(row,True))],'Add stored test',''))
        settle();return row
    try:
        host.call_method('SetEditorPanel',('layouts',));set_(host,'ActiveCampaignID',campaign)
        check(names()==[] and get(get(host,'PresetService'),'LibraryKey')==library_key,'native Layouts panel uses an isolated empty preset library without creating files')
        row=add('preset_one');before=version();emit('save_preset','  Bed arrangement  ')
        check(names()==['Bed arrangement'] and get(host,'SelectedPreset')=='Bed arrangement' and version()==before,
              'preset creation trims the name, refreshes selection, and does not mark layout edits saved')
        assert names()==['Bed arrangement']
        one=get(get(host,'PresetService'),'LibraryKey');check(one==library_key and files(home_key)==home_before,'saving a preset never writes the current canonical layout')
        add('preset_two');emit('save_preset','Two props');check(names()==['Bed arrangement','Two props'],'preset listing sorts multiple saved snapshots')
        select('Bed arrangement');before_undo=len(get(get(host,'History'),'UndoSteps'));emit('load_preset')
        check(count()==1 and field(values()[0],'Key')=='preset_one' and list(field(values()[0],'Materials'))==list(field(row,'Materials')),
              'preset load replaces the working layout while preserving stored-prop metadata')
        check(len(get(get(host,'History'),'UndoSteps'))==before_undo+1,'whole preset replacement is one undoable transaction')
        command('undo');settle();check(count()==2,'undo preset load restores the complete prior layout')
        command('redo');settle();check(count()==1,'redo preset load restores its snapshot')
        before=version();emit('load_preset');check(version()==before,'loading an identical preset makes no empty history step')
        stale=get(get(host,'PresetRows')[0],'Key');refresh();emit('preset',stale)
        check(get(host,'SelectedPreset')=='Bed arrangement','stale preset card cannot change current selection')
        service=get(host,'PresetService');service.call_method('SavePreset',('External snapshot',get(host,'WorkingDocument'),''))
        before=version();emit('load_preset');check(version()==before and 'External snapshot' in names() and 'changed' in get(host,'LayoutMessage'),
              'external library update refreshes the list and refuses the stale action')
        select('Two props');emit('delete_preset');check(get(host,'ConfirmMode')==5 and 'Two props' in names(),'preset deletion waits for an explicit in-editor confirmation')
        emit('confirm_cancel');check(get(host,'ConfirmMode')==0 and 'Two props' in names(),'cancel deletion leaves both editor and library intact')
        emit('delete_preset');emit('confirm_save');check(get(host,'ConfirmMode')==0 and 'Two props' not in names(),'confirmed preset deletion refreshes the native list')
        lib,status,_=service.call_method('LoadLibrary',(library_key,False,0));previous,status,_=service.call_method('LoadLibrary',(library_key,False,get(lib,'Revision')))
        from runtime import ROOT
        check(any(field(p,'Name',ROOT+'ST_DenPresetValue')=='Two props' for p in get(previous,'Entries')),'deleted preset remains recoverable in the prior library bank')
        before_disk=files(library_key);emit('save_preset',' ');check(files(library_key)==before_disk and 'not saved' in get(host,'LayoutMessage'),'invalid preset name gives feedback and preserves every library file')
        # Stage a real recovery draft under the source scope, then move its current
        # working contents to a campaign copy. The source canonical is unchanged.
        host.call_method('FlushDraft');check(storage.call_method('LoadLayout',(home_key,True,0))[1]==1,'scope test has a real autosaved source draft')
        unexpected,us=storage.call_method('MakeCampaign',(campaign,get(host,'WorkingDocument')));assert us==1
        emit('scope');check(get(host,'SessionKey')==home_key and 'already exists' in get(host,'LayoutMessage'),'new external campaign layout is not overwritten by a stale Home session')
        for p in root.glob(campaign_key+'-*.sav'):p.unlink()
        expected_count=count();emit('scope');check(get(host,'SessionKey')==campaign_key and count()==expected_count and not get(host,'History').call_method('IsDirty'),
              'Create campaign layout adopts an independently saved copy and marks it clean')
        assert get(host,'SessionKey')==campaign_key
        check(files(home_key)==home_before and storage.call_method('LoadLayout',(home_key,True,0))[1]==0,
              'campaign creation preserves Home canonical bytes and removes only the transferred source draft')
        own_doc,own_status,_=storage.call_method('LoadLayout',(campaign_key,False,0))
        check(own_status==1 and get(own_doc,'Enabled') and get(own_doc,'CampaignID')==campaign,'campaign copy carries canonical campaign identity and remains enabled')
        add('campaign_unsaved');dirty_count=count();emit('scope');check(get(host,'ConfirmMode')==5 and get(host,'SessionKey')==campaign_key,'returning Home waits before dropping unsaved campaign edits')
        emit('confirm_cancel');check(count()==dirty_count and get(host,'SessionKey')==campaign_key,'cancelling scope switch retains unsaved campaign state')
        disabled=storage.call_method('CloneLayout',(home_doc,));fixture.call_method('SetEnabled',(disabled,False));_,ds=storage.call_method('SaveLayout',(home_key,disabled,False,0,''));assert ds==1
        emit('scope');emit('confirm_save');still_own,_,_=storage.call_method('LoadLayout',(campaign_key,False,0))
        check(get(host,'SessionKey')==campaign_key and get(still_own,'Enabled') and count()==dirty_count,'unusable Home destination cannot deactivate the campaign or discard its working edits')
        for p in root.glob(home_key+'-*.sav'):
            if p not in home_before:p.unlink()
        for p,data in home_before.items():p.write_bytes(data)
        # A draft belonging to the destination must be offered after switching,
        # never silently erased as part of source-draft cleanup.
        draft,ds=storage.call_method('SaveLayout',(home_key,own_doc,True,get(home_doc,'Revision'),get(home_doc,'ContentID')));assert ds==1
        emit('scope');emit('confirm_save')
        check(get(host,'SessionKey')==home_key and get(host,'RecoveryPending') and get(host,'ConfirmMode')==2,
              'returning Home preserves and explicitly offers its matching recovery draft')
        latest,status,_=storage.call_method('LoadLayout',(campaign_key,False,0));older,_,_=storage.call_method('LoadLayout',(campaign_key,False,get(latest,'Revision')))
        check(status==1 and not get(latest,'Enabled') and get(older,'Enabled') and len(get(older,'Entries'))==expected_count,
              'returning Home disables the saved campaign copy and preserves its previous enabled backup')
        check(files(home_key)!=home_before and count()==len(get(home_doc,'Entries')),'Home recovery is offered over its untouched canonical baseline')
        emit('confirm_save');check(not get(host,'RecoveryPending') and count()==expected_count and get(host,'History').call_method('IsDirty'),
              'explicit recovery adopts the Home draft as unsaved working data')
        assert host.call_method('DiscardCurrent');settle();check(files(home_key)==home_before,'discarding recovered preview leaves Home canonical files unchanged')
        # Scope controls cannot use arbitrary session keys or an unknown campaign.
        set_(host,'ActiveCampaignID','');before=get(host,'SessionKey');emit('scope')
        check(get(host,'SessionKey')==before and 'unavailable' in get(host,'LayoutMessage'),'unknown campaign identity produces feedback without creating a layout')
    finally:
        host.call_method('SetEditorConfirm',(0,));host.call_method('SetEditorPanel',('',))
        if get(host,'RecoveryPending'):host.call_method('DiscardRecovery')
        if get(host,'Editing'):host.call_method('CloseSession',(False,));settle()
        set_(host,'ActiveCampaignID','');assert host.call_method('OpenSession',(home_key,home_doc,home_status));settle()
        for key in [library_key,campaign_key]:
            for p in root.glob(key+'-*.sav'):p.unlink()
        # All test paths are under unique keys; restore any original source bank
        # bytes if a failed assertion interrupted a draft cleanup.
        for p in root.glob(home_key+'-*.sav'):
            if p not in home_before:p.unlink()
        for p,data in home_before.items():p.write_bytes(data)
    check(files(home_key)==home_before and not files(library_key) and not files(campaign_key),'native Layouts UI tests clean up only their isolated slots')
