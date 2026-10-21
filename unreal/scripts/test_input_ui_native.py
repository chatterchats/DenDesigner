"""Editor preference application and mapping preparation using real native objects."""
def run(unreal,host,rig,get,check):
    from runtime_key_names import CODEC
    from runtime_input_mappings import BUILDER
    host.call_method('ReadEditorPreferences');host.call_method('ApplyEditorPreferences')
    check(get(host,'PreferencesStatus')==0 and get(rig,'Speed')==900 and get(host,'DraftEnabled'),
          'opening absent preferences applies the original camera and draft defaults')
    service=get(host,'PreferenceService')
    changes={'fly_speed':'1200','fast_multiplier':'4','look_speed':'3.5','snap':'25','reach':'4000',
             'unlock_structure':'true','select_floors':'false','select_walls':'true','gimbal':'scale','autosave':'false',
             'thumbnails':'false','key_forward':'I'}
    check(all(service.call_method('ChangePreference',(key,value))[1]==1 for key,value in changes.items()),
          'editor preference fixture saves camera, editing, thumbnail and input options')
    host.call_method('ReadEditorPreferences');host.call_method('ApplyEditorPreferences')
    check((get(rig,'Speed'),get(rig,'FastMultiplier'),get(rig,'LookRate'))==(1200,4,3.5),
          'validated saved camera values apply to the native rig')
    check((get(host,'GridStep'),get(host,'GridIndex'),get(host,'ReachCm'),get(host,'ReachIndex'))==(25,3,4000,2),
          'saved grid and range apply with matching toolbar cycle indices')
    check(get(host,'StructureEnabled') and not get(host,'FloorsEnabled') and get(host,'WallsEnabled') and get(host,'GizmoMode')==3,
          'saved independent structure, floor, wall and gizmo preferences apply')
    check(not get(host,'DraftEnabled') and not get(host,'DraftPending'),'disabling autosave stops the pending draft schedule')
    host.call_method('EnsureThumbnailWorker')
    worker=get(host,'ThumbnailWorker')
    check(worker is not None and not get(worker,'Enabled'),'new thumbnail worker inherits disabled rendering preference')
    context,accepted,defaults=host.call_method('PrepareEditorMappings')
    codec=unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(CODEC))
    rows=list(context.get_editor_property('Mappings'))
    check(accepted and not defaults and codec.call_method('NameFromKey',(rows[0].key,))[0]=='I',
          'editor prepares its private mappings from the loaded preference document')
    check(not host.call_method('InstallEditorMappings') and get(host,'EditorMappingContext') is None,
          'mapping install without a player subsystem does not take input ownership')
    host.call_method('ReleaseEditorMappings')
    check(get(host,'EditorMappingContext') is None,'mapping release is safe before installation')
    check(service.call_method('ResetSettings')[1]==1,'editor preference fixture resets through native service')
    host.call_method('ReadEditorPreferences');host.call_method('ApplyEditorPreferences')
    check((get(rig,'Speed'),get(rig,'FastMultiplier'),get(rig,'LookRate'))==(900,3,2.5) and
          get(host,'GridStep')==0 and get(host,'ReachCm')==2000 and get(host,'DraftEnabled') and get(worker,'Enabled'),
          'reset settings reapplies defaults to both existing camera and thumbnail worker')
    host.call_method('ReleaseThumbnails')
