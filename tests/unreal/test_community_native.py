"""Kit VM checks for the standalone SaveGame mailbox and local composition flow.

No HTTP request, external companion, game installation or campaign save is used.
Incoming files are real engine SaveGames; the authored Blueprint parser imports
ordinary values into the same isolated library used by the composition fixture.
"""
from pathlib import Path
import os


def run(unreal, host, document, get, field, check, saved, finish_preview, settle, command):
    from runtime import ROOT
    from runtime_community_mailbox import REQUEST, RESPONSE

    saved = Path(saved).resolve()
    actual_saved = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())).resolve()
    assert saved == actual_saved, 'Community tests only use the current kit Saved directory'
    mailbox = [saved / 'SaveGames' / (slot + '.sav') for slot in (REQUEST, RESPONSE)]
    assert all(path.is_relative_to(saved / 'SaveGames/ZComDen/Community/v1') for path in mailbox)
    backups = {path: path.read_bytes() if path.exists() else None for path in mailbox}
    wire_class = unreal.EditorAssetLibrary.load_blueprint_class(ROOT + 'BP_DenCommunityWireSave')
    assert wire_class is not None, 'Community wire class must be authored before testing'
    parts = list(get(document, 'Entries'))
    anchor = get(document, 'CompositionAnchor')
    baseline = list(get(get(host, 'WorkingDocument'), 'Entries'))
    service = get(host, 'CompositionService')
    names_before = list(service.call_method('ListPresets')[0])
    name = 'Community VM sample'
    assert name not in names_before, 'Fixture name must not replace an existing composition'
    placed = False
    native_name = None

    def setprop(obj, key, value):
        error = unreal.ZComAuthoringLibrary.set_property_from_text(obj, key, str(value))
        assert not error, error

    def numbers(value, rotation=False):
        attrs = ('pitch', 'yaw', 'roll') if rotation else ('x', 'y', 'z')
        return [format(float(getattr(value, attr)), '.17g') for attr in attrs]

    def record(part):
        values = ['part', field(part, 'Mesh')]
        values += numbers(field(part, 'Position'))
        values += numbers(field(part, 'Rotation'), True)
        values += numbers(field(part, 'Scale'))
        values += [str(field(part, 'CollisionMode'))]
        return '\t'.join(values)

    def wire(token, rows=None, title=name, version='1', extra=None):
        records = ['ZCOM-COMMUNITY\t' + version + '\t' + token, 'ok', 'name\t' + title,
                   'report\tGame meshes; no prop packs', 'anchor\t' + '\t'.join(numbers(anchor)),
                   'count\t' + str(len(parts))]
        if rows is None:
            for part in parts:
                records.append(record(part))
                records += ['material\t' + path for path in field(part, 'Materials')]
        else:
            records += rows
        records += ['end']
        if extra is not None:
            records.append(extra)
        return '\n'.join(records)

    def start():
        host.call_method('StartCommunityFetch', ('DenDesignerTest01',))
        token = get(host, 'CommunityToken')
        check(get(host, 'CommunityPending') and len(token) == 32, 'Community request creates a fresh bounded correlation token')
        request = unreal.GameplayStatics.load_game_from_slot(REQUEST, 0)
        check(request is not None and get(request, 'Token') == token and get(request, 'Input') == 'DenDesignerTest01',
              'pak request is serialized through the real engine SaveGame API')
        return token

    def deliver(token, text):
        response = unreal.GameplayStatics.create_save_game_object(wire_class)
        setprop(response, 'Token', token)
        setprop(response, 'Input', '')
        setprop(response, 'Wire', text)
        assert get(response, 'Wire') == text, 'Native test setter must preserve tabs and newlines exactly'
        assert unreal.GameplayStatics.save_game_to_slot(response, RESPONSE, 0)
        setprop(host, 'CommunityMailboxAt', -1e9)

    def pump():
        for _ in range(100):
            host.call_method('PollCommunityMailbox')
            if not get(host, 'CommunityPending'):
                return
        raise AssertionError('Community mailbox did not finish within its finite test budget')

    def library_names():
        return list(service.call_method('ListPresets')[0])

    def unchanged(label, expected=None):
        check(library_names() == (names_before if expected is None else expected), label)
        check(list(get(get(host, 'WorkingDocument'), 'Entries')) == baseline,
              'Community validation and import never mutate the working layout')

    def same_parts(left, right):
        fields = ['Kind', 'Mesh', 'Rotation', 'Scale', 'HasPosition', 'HasRotation', 'HasScale',
                  'Hidden', 'CollisionMode', 'Source', 'HasFingerprint', 'FingerprintMesh', 'FingerprintPosition']
        if len(left) != len(right):
            return False
        return all(all(field(a, key) == field(b, key) for key in fields)
                   and (field(a, 'Position') - field(b, 'Position')).length() < .0001
                   and list(field(a, 'Materials')) == list(field(b, 'Materials'))
                   for a, b in zip(left, right))

    try:
        host.call_method('SetEditorPanel', ('community',))
        host.call_method('CancelCommunityFetch')
        for invalid in ['', 'café', 'code with spaces', 'x'*257, 'zcu_'+'a'*64]:
            host.call_method('StartCommunityFetch', (invalid,))
            check(not get(host, 'CommunityPending') and not mailbox[0].exists(), 'invalid Community input is rejected before native serialization')
        normalized, valid = host.call_method('NormalizeCommunityInput', ('  https://share.zcom.app/comp/DenDesignerTest01  ',))
        check(valid and normalized == 'https://share.zcom.app/comp/DenDesignerTest01', 'pasted Community links trim surrounding whitespace')
        # Synthetic key only. Connection state never enters a composition or
        # campaign save, and the masked field is cleared before transport.
        previous_panel=get(host,'CommunityPanel')
        if previous_panel is None:
            from runtime_editor_assets import UIROOT
            world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
            widgets=unreal.get_default_object(unreal.load_class(None,'/Script/UMG.WidgetBlueprintLibrary'))
            panel=widgets.call_method('Create',(world,unreal.EditorAssetLibrary.load_blueprint_class(UIROOT+'WBP_DenCommunity'),None))
            setprop(host,'CommunityPanel',panel.get_path_name())
        keybox=get(get(host,'CommunityPanel'),'CommunityKey')
        check(get(keybox,'IsPassword'),'in-game Community key entry is masked')
        fake_key='zcu_'+'a'*64
        for remember in [False,True]:
            setprop(host,'CommunityRemember',str(remember))
            keybox.call_method('SetText',(fake_key,))
            host.call_method('ConnectCommunity')
            request=unreal.GameplayStatics.load_game_from_slot(REQUEST,0)
            check(request is not None and get(request,'Input')=='AUTH'
                  and get(request,'Wire')==('1' if remember else '0')+'\t'+fake_key,
                  'Connect carries explicit opt-in state with a bounded synthetic credential')
            check(str(keybox.call_method('GetText'))=='' and get(host,'CommunityOutgoing')=='',
                  'Connect clears the key widget and outgoing credential property immediately')
            check(fake_key not in get(host,'CommunityMessage'),
                  'connection feedback never displays the upload key')
            host.call_method('CancelCommunityFetch')
        keybox.call_method('SetText',('invalid-key',))
        host.call_method('ConnectCommunity')
        check(not get(host,'CommunityPending') and not mailbox[0].exists()
              and str(keybox.call_method('GetText'))=='',
              'invalid keys are cleared without writing a credential request')
        keybox.call_method('SetText',('',))
        host.call_method('ConnectCommunity')
        request=unreal.GameplayStatics.load_game_from_slot(REQUEST,0)
        check(get(request,'Input')=='CONNECT' and get(request,'Wire')=='request',
              'blank Connect restores a remembered connection without another key paste')
        host.call_method('CancelCommunityFetch')
        host.call_method('ForgetCommunity')
        request=unreal.GameplayStatics.load_game_from_slot(REQUEST,0)
        check(not get(host,'CommunityRemember') and get(request,'Input')=='FORGET'
              and get(request,'Wire')=='request',
              'Forget clears the in-game preference and explicitly requests native credential removal')
        host.call_method('CancelCommunityFetch')
        unchanged('connection controls do not change library or working Den')
        # Retain this real widget for upload area VM tests below.

        # Distinct destinations and separate source selection state.
        check(get(host,'CompositionsPanel') != get(host,'CommunityPanel'), 'local Compositions and online Community have distinct widget instances')
        host.call_method('SetCommunityArea',('browse',))
        host.call_method('RefreshCommunityGallery')
        request=unreal.GameplayStatics.load_game_from_slot(REQUEST,0)
        evidence=Path(__file__).resolve().parents[2]/'dist/verification/community/catalog-request.sav'
        evidence.parent.mkdir(parents=True,exist_ok=True);evidence.write_bytes(mailbox[0].read_bytes())
        check(get(request,'Input')=='CATALOG/0','Browse requests the actual public catalogue rather than a code-entry substitute')
        host.call_method('CancelCommunityFetch')
        host.call_method('StartCommunityTransfer',('PREVIEW/DenDesignerTest01','0'))
        (evidence.parent/'public-preview-request.sav').write_bytes(mailbox[0].read_bytes())
        host.call_method('CancelCommunityFetch')
        before_selection=get(host,'SelectedComposition')
        token='1'*32
        setprop(host,'CommunityToken',token);setprop(host,'CommunityPending','true')
        deliver(token,'ZCOM-COMMUNITY\t1\t'+token+'\ngallery\t0\t1\t1\nlisting\tPublicTest01\tPublic arrangement\tPublic description\tActual creator\t1\t3\tUnknown dependencies: 1\nend')
        host.call_method('PollCommunityMailbox')
        check(len(get(host,'CommunityBrowseRows'))==1 and not get(host,'CommunityPending'),'public catalogue populates native cards and completes its request')
        public_row=list(get(host,'CommunityBrowseRows'))[0]
        host.call_method('SelectCommunityListing',(get(public_row,'Key'),))
        check(get(host,'CommunityBrowseSelected')==0 and get(host,'SelectedComposition')==before_selection,'public browsing selection does not change local composition selection')
        host.call_method('SetCommunityArea',('upload',))
        check(get(host,'CommunityBrowseSelected')==0,'upload navigation retains independent public selection')
        host.call_method('CancelCommunityFetch')

        actual_gallery=os.environ.get('DENDESIGNER_NATIVE_GALLERY')
        actual_preview=os.environ.get('DENDESIGNER_NATIVE_PREVIEW')
        if actual_gallery and actual_preview:
            host.call_method('SetCommunityArea',('browse',))
            before_live=library_names()
            host.call_method('StartCommunityTransfer',('CATALOG/0',' '))
            mailbox[1].write_bytes(Path(actual_gallery).read_bytes())
            received=unreal.GameplayStatics.load_game_from_slot(RESPONSE,0)
            setprop(host,'CommunityToken',get(received,'Token'));setprop(host,'CommunityMailboxAt',-1e9)
            host.call_method('PollCommunityMailbox')
            codes=list(get(host,'CommunityBrowseCodes'))
            live_code=os.environ['DENDESIGNER_NATIVE_PREVIEW_CODE']
            check(live_code in codes and len(codes)>0,'actual live service catalogue deserializes into in-game public cards')
            live_index=codes.index(live_code)
            live_revision=list(get(host,'CommunityBrowseRevisions'))[live_index]
            host.call_method('StartCommunityTransfer',('PREVIEW/'+live_code,str(live_revision)))
            setprop(host,'CommunityPreviewIndex',live_index)
            mailbox[1].write_bytes(Path(actual_preview).read_bytes())
            received=unreal.GameplayStatics.load_game_from_slot(RESPONSE,0)
            setprop(host,'CommunityToken',get(received,'Token'));setprop(host,'CommunityMailboxAt',-1e9);pump()
            live_row=list(get(host,'CommunityBrowseRows'))[live_index]
            check(get(live_row,'ThumbnailDocument') is not None and library_names()==before_live,'actual pinned native preview reaches the local renderer without importing into the library')
            # Restore the isolated synthetic row for independent form tests.
            host.call_method('StartCommunityTransfer',('CATALOG/0',' '));t=get(host,'CommunityToken')
            # Refresh clears old rows before the controlled response is delivered.
            host.call_method('RefreshCommunityGallery');t=get(host,'CommunityToken')
            deliver(t,'ZCOM-COMMUNITY\t1\t'+t+'\ngallery\t0\t1\t1\nlisting\tPublicTest01\tPublic arrangement\tPublic description\tActual creator\t1\t3\tUnknown dependencies: 1\nend')
            host.call_method('PollCommunityMailbox');host.call_method('CancelCommunityFetch')
            row=list(get(host,'CommunityBrowseRows'))[0];host.call_method('SelectCommunityListing',(get(row,'Key'),))
            host.call_method('SetCommunityArea',('upload',))

        # Exercise actual VM serialization without networking or a real secret.
        import json
        from runtime import LAYOUT
        def field_name(key):
            from runtime import ENTRY, specs
            spec=next(spec for _,spec in specs() if spec["path"]==ENTRY)
            entry=next(f for f in spec["fields"] if f["name"]==key)
            return key+"_0_"+entry["guid"].replace("-","").upper()
        publish_doc = unreal.GameplayStatics.create_save_game_object(unreal.EditorAssetLibrary.load_blueprint_class(LAYOUT))
        row = parts[0].copy()
        for key, value in {'Mesh':'/Game/Game/Environments/Strategy/HQ/Props/Control/Control_Monitor_A.Control_Monitor_A',
                           'Position':unreal.Vector(1.25,-2.5,3),'Rotation':unreal.Rotator(10,20,30),'Scale':unreal.Vector(1,2,3),'CollisionMode':1}.items():
            row.set_editor_property(field_name(key),value)
        publish_doc.call_method('WriteEntry',(row,True))
        outgoing, ready = host.call_method('BuildCommunitySubmission',(publish_doc,))
        check(ready,'publishing serializer accepts bounded saved values')
        encoded = json.loads(outgoing)
        check(encoded['payload']['entries'][0]['Position']==[1.25,-2.5,3] and encoded['payload']['entries'][0]['Materials']==list(field(row,'Materials')),
              'publishing serializer preserves numeric transforms and every material override')
        check('author' not in encoded['metadata'] and 'zcu_' not in outgoing,'outgoing document has no client attribution or credential')
        host.call_method('StartCommunityTransfer',('PUBLISH',outgoing))
        outgoing_save=unreal.GameplayStatics.load_game_from_slot(REQUEST,0)
        check(get(outgoing_save,'Input')=='PUBLISH' and get(outgoing_save,'Wire')==outgoing,'real engine mailbox carries only outgoing composition values')
        host.call_method('CancelCommunityFetch')
        token = start()
        deliver('0' * 32, wire('0' * 32))
        host.call_method('PollCommunityMailbox')
        check(get(host, 'CommunityPending') and get(host, 'CommunityToken') == token,
              'stale response token is ignored without cancelling the current request')
        unchanged('stale mailbox responses do not import a composition')
        host.call_method('CancelCommunityFetch')
        deliver(token, wire(token))
        host.call_method('PollCommunityMailbox')
        check(not get(host, 'CommunityPending') and not mailbox[0].exists(),
              'cancellation removes the request and ignores a late matching response')
        unchanged('late responses after cancellation leave the local library unchanged')

        # Enough records to exceed one tick budget; cancel before any save.
        token = start()
        staged = [record(parts[0])] + ['material\t'] * 12 + [record(parts[1])]
        deliver(token, wire(token, staged))
        host.call_method('PollCommunityMailbox')
        check(get(host, 'CommunityPending') and get(host, 'CommunityWireCursor') == 16,
              'mailbox stages at most ten records in one poll')
        check(len(get(get(host, 'CommunityDocument'), 'Entries')) == 1,
              'bounded staging retains only the completed prefix until the next poll')
        host.call_method('CancelCommunityFetch')
        unchanged('cancelling a partially parsed response writes no library entry')

        token = start()
        setprop(host, 'CommunityStarted', -1e9)
        host.call_method('PollCommunityFetch')
        check(not get(host, 'CommunityPending') and 'timed out' in get(host, 'CommunityMessage'),
              'pak deadline cancels offline or absent companion requests')
        unchanged('timeout keeps the local library intact')

        token = start()
        deliver(token, wire(token))
        setprop(host, 'CommunityStarted', -1e9)
        host.call_method('PollCommunityFetch')
        check(not get(host, 'CommunityPending'), 'deadline is checked before a late complete response can import')
        unchanged('a complete response after the deadline never commits')

        first = record(parts[0]).split('\t')
        cases = [('unsupported wire schema', lambda t: wire(t, version='2')),
                 ('malformed record', lambda t: wire(t, ['part\tmissing-fields'])),
                 ('too many material slots', lambda t: wire(t, [record(parts[0])] + ['material\t'] * 65 + [record(parts[1])])),
                 ('extra content after terminator', lambda t: wire(t, extra='unexpected'))]
        for label, index, replacement in [('nonfinite position', 2, 'NaN'), ('out of range position', 2, '10000001'),
                                           ('negative scale', 8, '-1'), ('unsupported collision', 11, '3'),
                                           ('fractional collision', 11, '1.5'), ('executable-like mesh path', 1, 'https://evil.invalid/a.lua')]:
            values = first.copy(); values[index] = replacement
            line = '\t'.join(values)
            cases.append((label, lambda t, line=line: wire(t, [line, record(parts[1])])) )
        for label, make in cases:
            token = start()
            deliver(token, make(token))
            pump()
            check(not get(host, 'CommunityPending'), 'Community parser rejects ' + label)
            unchanged('rejected ' + label + ' never partially saves a composition')

        token = start()
        deliver(token, wire(token))
        pump()
        loaded, status = service.call_method('LoadPreset', (name,))
        check(status == 1 and loaded is not None, 'validated mailbox values enter the ordinary local composition library')
        assert loaded is not None
        check(same_parts(list(get(loaded, 'Entries')), parts),
              'Community import preserves every transform, collision value and ordered material slot')
        check(get(loaded, 'HasCompositionAnchor') and (get(loaded, 'CompositionAnchor') - anchor).length() < .0001,
              'Community import preserves the portable anchor through local library serialization')
        check(name in library_names() and 'no prop packs' in get(host, 'CommunityMessage'),
              'successful import selects its local card and reports dependencies')
        check(not mailbox[0].exists(), 'completed import releases the standalone transport request')
        unchanged('successful import adds one named composition only', names_before + [name])

        # Saved-card publication uses the selected snapshot and its exact cache
        # identity; it must not capture whichever world parts happen to be selected.
        host.call_method('SetCommunityArea',('upload',))
        host.call_method('RefreshCommunitySources')
        setprop(host,'CommunitySourceName',name)
        host.call_method('ReviewCommunityComposition')
        panel=get(host,'CommunityPanel')
        get(panel,'PublishTitle').call_method('SetText',('VM saved composition',))
        get(panel,'PublishDescription').call_method('SetText',('Retained after errors',))
        reviewed=get(host,'CommunityUploadJSON')
        host.call_method('SetCommunityArea',('account',))
        host.call_method('SetCommunityArea',('browse',))
        check(get(host,'CommunityUploadJSON')==reviewed and str(get(panel,'PublishTitle').call_method('GetText'))=='VM saved composition',
              'area switching keeps reviewed upload snapshot and metadata independent of browsing')
        host.call_method('SetCommunityArea',('upload',))
        host.call_method('SubmitCommunityComposition')
        selected_request=unreal.GameplayStatics.load_game_from_slot(REQUEST,0)
        check(selected_request is not None and get(selected_request,'Input')=='PUBLISH',
              'publishing the selected saved card creates an outgoing value request')
        evidence=Path(__file__).resolve().parents[2]/'dist/verification/community/inpanel-publish.sav'
        evidence.parent.mkdir(parents=True,exist_ok=True);evidence.write_bytes(mailbox[0].read_bytes())
        thumb_name,title,description,code,revision,published_json=get(selected_request,'Wire').split('\n',5)
        check(title=='VM saved composition' and description=='Retained after errors' and code==revision=='','UMG metadata reaches the transport without a native desktop form')
        import re
        check(re.fullmatch(r'Composition_[a-f0-9]{8}\.png',thumb_name) is not None,
              'saved-card publication reuses the restricted local thumbnail basename')
        selected_values=json.loads(published_json)['payload']['entries']
        check(len(selected_values)==len(parts) and selected_values[0]['Mesh']==field(parts[0],'Mesh')
              and selected_values[0]['Materials']==list(field(parts[0],'Materials')),
              'saved-card publication preserves the selected library document and material order')
        host.call_method('CancelCommunityFetch')
        unchanged('cancelling saved-card publication preserves library and working Den',names_before+[name])
        # A public preview is only a cached document, not a local-library write.
        before_preview=list(library_names());local_before=get(host,'SelectedComposition')
        setprop(host,'CommunityPreviewIndex',0)
        host.call_method('StartCommunityTransfer',('PREVIEW/PublicTest01','3'))
        preview_token=get(host,'CommunityToken');deliver(preview_token,wire(preview_token,title='Public preview'))
        pump()
        check(library_names()==before_preview and get(host,'SelectedComposition')==local_before,
              'public local preview capture does not save or select a local composition')
        check(get(list(get(host,'CommunityBrowseRows'))[0],'ThumbnailDocument') is not None,
              'public card receives a validated document for bounded local thumbnail rendering')
        # Preserve the local source and reviewed form while navigating public data.
        check(get(host,'CommunitySourceName')==name and get(host,'CommunityUploadJSON')==reviewed,
              'public preview does not change the local upload source or reviewed snapshot')

        host.call_method('DownloadCommunityListing')
        download_request=unreal.GameplayStatics.load_game_from_slot(REQUEST,0)
        check(get(download_request,'Input')=='DOWNLOAD/PublicTest01' and get(download_request,'Wire')=='3',
              'Download pins the selected public revision and is separate from preview')
        downloaded_name='Community browser download'
        download_token=get(host,'CommunityToken');deliver(download_token,wire(download_token,title=downloaded_name));pump()
        check(downloaded_name in library_names() and len(library_names())==len(before_preview)+1,
              'public Download adds the validated composition to the existing local library')
        check(list(get(get(host,'WorkingDocument'),'Entries'))==baseline and get(host,'SelectedComposition')==local_before,
              'Download neither places anything nor changes the local selection')
        service.call_method('DeletePreset',(downloaded_name,));host.call_method('RefreshCompositionLibrary')
        host.call_method('RefreshCommunitySources');setprop(host,'CommunitySourceName',name);host.call_method('ReviewCommunityComposition')
        check(str(get(panel,'PublishDescription').call_method('GetText'))=='Retained after errors','cancel keeps upload form values')
        setprop(host,'CommunityUploadLibraryID','stale-library-revision')
        host.call_method('SubmitCommunityComposition')
        check(not get(host,'CommunityPending') and not mailbox[0].exists(),'changed saved library identity blocks a previously reviewed upload')
        setprop(host,'CommunitySourceName','deleted-card')
        host.call_method('ReviewCommunityComposition')
        check(get(host,'CommunityUploadJSON')=='','deleted saved-card selection cannot retain a publishable review')
        setprop(host,'CommunitySourceName',name)
        host.call_method('ReviewCommunityComposition')
        host.call_method('SubmitCommunityComposition')
        failed_token=get(host,'CommunityToken')
        host.call_method('FailCommunityFetch',(failed_token,'Not connected. Connect and retry.'))
        check(not get(host,'CommunityPending') and str(get(panel,'PublishTitle').call_method('GetText'))=='VM saved composition'
              and get(host,'CommunityUploadJSON')==reviewed,'disconnected and recoverable failures retain reviewed payload and form')
        host.call_method('SubmitCommunityComposition')
        check(get(host,'CommunityPending'),'retry reuses the reviewed saved snapshot')
        protected_token=get(host,'CommunityToken');host.call_method('SetCommunityArea',('browse',));host.call_method('RefreshCommunityGallery')
        check(get(host,'CommunityToken')==protected_token and get(host,'CommunityPending'),'browsing cannot silently cancel an active upload')
        host.call_method('SetCommunityArea',('upload',))
        retry_token=get(host,'CommunityToken')
        deliver(retry_token,'ZCOM-COMMUNITY\t1\t'+retry_token+'\nprogress\tUploading cached preview...\nend')
        setprop(host,'CommunityMailboxAt',-1e9)
        host.call_method('PollCommunityMailbox')
        check(get(host,'CommunityPending') and get(host,'CommunityToken')==retry_token,'in-panel upload progress does not consume or cancel its request')
        host.call_method('FailCommunityFetch',(retry_token,'Published: https://share.zcom.app/comp/PublishedTest01'))
        check(get(host,'CommunityPublicURL')=='https://share.zcom.app/comp/PublishedTest01' and get(host,'CommunityPublicCode')=='PublishedTest01','successful publication keeps independently copyable public URL and share code')
        host.call_method('CopyCommunityURL')
        copied=unreal.GameplayStatics.load_game_from_slot(REQUEST,0)
        check(get(copied,'Input')=='COPYURL/PublishedTest01','URL copy sends only the validated opaque publication code to background transport')
        host.call_method('CancelCommunityFetch')
        host.call_method('CopyCommunityCode')
        copied=unreal.GameplayStatics.load_game_from_slot(REQUEST,0)
        check(get(copied,'Input')=='COPYCODE/PublishedTest01','share-code copy uses the background transport without an external form')

        keybox.call_method('SetText',('zcu_'+'a'*64,))
        host.call_method('SetEditorPanel',('',))
        check(not get(host,'CommunityPending') and not mailbox[0].exists() and str(keybox.call_method('GetText'))=='','closing Community clears draft credential text and invalidates pending work')
        host.call_method('SetEditorPanel',('community',))
        host.call_method('SetCommunityArea',('den',))
        check(get(host,'CommunityArea')=='den' and not get(host,'CommunityPending'),'Full Den unavailable area sends no composition upload request')
        host.call_method('SetCommunityArea',('browse',))



        # A second response with the same title may not replace a saved arrangement.
        prior = list(get(loaded, 'Entries'))
        token = start()
        deliver(token, wire(token))
        pump()
        again, status = service.call_method('LoadPreset', (name,))
        check(status == 1 and same_parts(list(get(again, 'Entries')), prior),
              'duplicate imported name is rejected without replacing the saved document')
        unchanged('duplicate import creates no additional entry', names_before + [name])

        import test_composition_thumbnails_native
        test_composition_thumbnails_native.run(unreal, host, loaded, get, field, check, name=name)
        host.call_method('SetEditorPanel',('compositions',))
        host.call_method('LoadEditorComposition', (name,))
        check(get(host, 'CompositionPlacing') and finish_preview(),
              'imported composition uses the existing asynchronous placement preview')
        host.call_method('SetCompositionPreviewOrigin', (unreal.Vector(41000, 43000, 45000),))
        check(host.call_method('CommitComposition', (False,)),
              'imported composition places through the ordinary whole-group transaction')
        placed = True
        settle()
        check(len(get(get(host, 'WorkingDocument'), 'Entries')) == len(baseline) + len(parts),
              'placement adds every imported part after all assets load')
        command('undo'); settle(); placed = False
        check(list(get(get(host, 'WorkingDocument'), 'Entries')) == baseline,
              'one undo restores the exact layout from before Community placement')

        # Opt-in, real cross-platform boundary proof: these bytes were produced
        # by the standalone Windows worker, not the Python test serializer.
        native_response = os.environ.get('DENDESIGNER_NATIVE_RESPONSE')
        if native_response:
            service.call_method('DeletePreset', (name,))
            host.call_method('RefreshCompositionLibrary')
            start()
            mailbox[1].write_bytes(Path(native_response).read_bytes())
            received = unreal.GameplayStatics.load_game_from_slot(RESPONSE, 0)
            assert received is not None, 'Windows-native SaveGame must deserialize in fresh kit process'
            native_token = get(received, 'Token')
            native_wire = get(received, 'Wire')
            check(native_wire.startswith('ZCOM-COMMUNITY\t1\t'+native_token+'\nok\n'),
                  'kit deserializes exact live native worker response without rebuilding its properties')
            native_name = native_wire.splitlines()[2].split('\t')[1]
            setprop(host, 'CommunityToken', native_token)
            setprop(host, 'CommunityMailboxAt', -1e9)
            pump()
            loaded, status = service.call_method('LoadPreset', (native_name,))
            check(status == 1 and loaded is not None, 'real live HTTPS worker result imports into the kit composition library')
            assert loaded is not None
            native_parts = list(get(loaded, 'Entries'))
            expected_mesh = '/Game/Game/Environments/Strategy/HQ/Props/Control/Control_Monitor_A.Control_Monitor_A'
            check(len(native_parts) == 1 and field(native_parts[0], 'Mesh') == expected_mesh,
                  'live test imports the independently reviewed game monitor dependency')
            check(unreal.load_asset(expected_mesh) is not None, 'published test mesh is actually loadable in the kit')
            test_composition_thumbnails_native.run(unreal, host, loaded, get, field, check, name=native_name)
            host.call_method('LoadEditorComposition', (native_name,))
            check(get(host, 'CompositionPlacing') and finish_preview(), 'live downloaded composition completes ordinary kit placement preview')
            host.call_method('SetCompositionPreviewOrigin', (unreal.Vector(41000, 43000, 45000),))
            check(host.call_method('CommitComposition', (False,)), 'live downloaded composition places through the existing transaction')
            placed = True
            settle()
            check(len(get(get(host, 'WorkingDocument'), 'Entries')) == len(baseline)+1, 'live monitor placement adds exactly one prop')
            command('undo'); settle(); placed = False
            check(list(get(get(host, 'WorkingDocument'), 'Entries')) == baseline, 'live downloaded monitor placement undoes as one transaction')
    finally:
        host.call_method('CancelCommunityFetch')
        host.call_method('CancelCompositionPreview')
        if placed:
            command('undo'); settle()
        if name in library_names():
            service.call_method('DeletePreset', (name,))
            host.call_method('RefreshCompositionLibrary')
        if native_name and native_name in library_names():
            service.call_method('DeletePreset', (native_name,))
            host.call_method('RefreshCompositionLibrary')
        for path, original in backups.items():
            if original is None:
                if path.exists():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(original)
