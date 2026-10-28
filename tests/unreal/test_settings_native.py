"""Settings commands travel through the real bus/host and isolated save store."""
def run(unreal,host,rig,bus,get,check,helper,field):
    def command(name,arg=''):
        bus.call_method('Emit',(2,name,arg,0.0,unreal.Vector()))
        host.call_method('ProcessEditorEvents')
    def value(key):return get(host,'PreferencesDocument').call_method('ReadPreference',(key,))[0]
    from runtime_settings_widget import PATH
    from runtime_key_names import CODEC
    from runtime_editor_assets import EVENT
    picker=unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(PATH))
    codec=unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(CODEC))
    helper.call_method('SetSettingsBus',(picker,bus))
    chord=unreal.InputChord(key=codec.call_method('KeyFromName',('I',))[0])
    picker.call_method('CaptureSettingKey',('setting:key_forward',chord))
    found,event=bus.call_method('Take')
    check(found and field(event,'EventName',EVENT)=='setting:key_forward' and field(event,'Argument',EVENT)=='I',
          'native key capture translates FInputChord to stable persisted key name')
    helper.call_method('SetSettingsRefreshing',(picker,True))
    picker.call_method('CaptureSettingKey',('setting:key_forward',chord))
    check(not bus.call_method('Take')[0],'refreshing key labels cannot enqueue a settings mutation')
    helper.call_method('SetSettingsRefreshing',(picker,False))
    command('settings')
    check(get(host,'ActivePanel')=='settings','Settings opens through native event routing')
    command('snap');command('reach');command('lock');command('floors');command('walls');command('mode_scale')
    fields=['GridStep','GridIndex','ReachCm','ReachIndex','StructureEnabled','FloorsEnabled','WallsEnabled','GizmoMode']
    before=tuple(get(host,k) for k in fields)
    command('setting:fly_speed','1400')
    check(get(host,'SettingsStatus')==1 and get(rig,'Speed')==1400 and value('fly_speed')=='1400',
          'camera setting commits and applies through queued UI events')
    check(tuple(get(host,k) for k in fields)==before,'camera setting preserves live quickbar choices and gizmo mode')
    command('setting:fly_speed','99999')
    check(get(host,'SettingsStatus')==7 and get(rig,'Speed')==1400 and value('fly_speed')=='1400' and 'range' in get(host,'SettingsMessage'),
          'invalid camera setting keeps the accepted value and explains the limit')
    command('setting:key_forward','I')
    check(get(host,'SettingsStatus')==1 and value('key_forward')=='I','captured canonical key persists through native command routing')
    command('setting:key_back','I')
    check(get(host,'SettingsStatus')==7 and value('key_back')=='S' and 'assigned' in get(host,'SettingsMessage'),
          'duplicate key is rejected without displacing an existing action')
    command('setting:key_back','Escape')
    check(get(host,'SettingsStatus')==7 and value('key_back')=='S','reserved escape cannot become a movement binding')
    command('setting_cycle','autosave')
    check(value('autosave')=='false' and not get(host,'DraftEnabled'),'settings autosave toggle applies immediately')
    command('setting_cycle','thumbnails')
    check(value('thumbnails')=='false' and not get(host,'ThumbnailsEnabled'),'settings thumbnail toggle applies immediately')
    command('setting_cycle','toggle_modifier')
    check(value('toggle_modifier')=='shift','open-editor modifier cycles through validated values')
    check(tuple(get(host,k) for k in fields)==before,'key and background settings also preserve quickbar state')
    command('rotation_pivot')
    check(value('rotation_pivot')=='bottom' and get(host,'RotationPivot')=='bottom',
          'inspector pivot cycle persists and applies the bottom anchor')
    command('setting_cycle','rotation_pivot')
    check(value('rotation_pivot')=='top' and get(host,'RotationPivot')=='top',
          'Settings cycles the same persisted rotation pivot as the inspector')
    command('setting:fly_speed','1300')
    check(value('rotation_pivot')=='top' and get(host,'RotationPivot')=='top',
          'changing another setting preserves the saved rotation anchor')
    command('settings_close')
    check(get(host,'ActivePanel')=='' and get(host,'Editing'),'Settings closes without closing the editor')
    command('settings_reset')
    check(get(host,'SettingsStatus')==1 and value('key_forward')=='W' and get(rig,'Speed')==900 and get(host,'DraftEnabled') and get(host,'ThumbnailsEnabled'),
          'reset defaults restores persisted settings and applies them to the current editor')
    check(get(host,'RotationPivot')=='centre', 'reset settings restores the bounds-centre rotation anchor')
    check(get(host,'GridStep')==0 and get(host,'ReachCm')==2000 and get(host,'FloorsEnabled') and not get(host,'StructureEnabled') and not get(host,'WallsEnabled') and get(host,'GizmoMode')==1,
          'explicit reset also restores quickbar defaults')
