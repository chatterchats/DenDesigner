"""Execute the native mapping builder; validate full mapping payloads and isolation."""
def run(unreal,fixture,field,field_name,check):
    from runtime_input_mappings import BUILDER, IMC
    from runtime_preferences import DOCUMENT, BINDINGS, ROW
    from runtime_key_names import CODEC
    from runtime_editor_assets import UIROOT
    builder=unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(BUILDER))
    codec=unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(CODEC))
    doc=unreal.GameplayStatics.create_save_game_object(unreal.EditorAssetLibrary.load_blueprint_class(DOCUMENT))
    template=unreal.load_asset(UIROOT+'IMC_DenEditor')
    rows=lambda obj:list(obj.get_editor_property('Mappings'))
    original=rows(template)
    def key_name(row):return codec.call_method('NameFromKey',(row.key,))[0]
    def contents_equal(a,b):
        return a.action==b.action and fixture.call_method('SameInputKeys',(a.key,b.key)) and list(a.modifiers)==list(b.modifiers) and list(a.triggers)==list(b.triggers)
    first,accepted,defaults=builder.call_method('BuildEditorContext',(doc,))
    check(accepted and not defaults and first is not None and first!=template,'native input builder creates a private context from defaults')
    check(len(rows(first))==len(original) and all(contents_equal(a,b) for a,b in zip(rows(first),original)),
          'private context preserves every action, fixed key, modifier and trigger in order')
    settings=[builder.call_method('BindingForMapping',(row,)) for row in original]
    check(sorted(x for x in settings if x)==sorted(b[0] for b in BINDINGS),'each rebindable action axis matches exactly one template mapping')
    updates={'key_forward':'I','key_up':'U','key_fast':'RightShift','key_turn_left':'B','key_catalog':'F2','toggle_key':'F12'}
    check(all(doc.call_method('WritePreference',(k,value))[0] for k,value in updates.items()),'independent native bindings accepted for mapping test')
    second,accepted,defaults=builder.call_method('BuildEditorContext',(doc,))
    check(accepted and not defaults and second!=first and second!=template,'rebuilding creates a new mapping context')
    changed=rows(second)
    check(all(key_name(row)==updates[setting] if setting in updates else fixture.call_method('SameInputKeys',(row.key,source.key))
              for row,source,setting in zip(changed,original,settings)),
          'saved bindings remap only their intended action and axis')
    check(all(row.action==source.action and list(row.modifiers)==list(source.modifiers) and list(row.triggers)==list(source.triggers)
              for row,source in zip(changed,original)),
          'rebound movement retains swizzle/negate and rotation retains repeat/chord configuration')
    check(all(contents_equal(a,b) for a,b in zip(rows(template),original)) and
          all(contents_equal(a,b) for a,b in zip(rows(first),original)),
          'rebinding never mutates the cooked template or another editor context')
    first.call_method('UnmapAll')
    check(not rows(first) and len(rows(second))==len(original) and len(rows(template))==len(original),
          'removing one editor context mappings leaves other contexts and template intact')
    # A structurally valid document can still contain conflicting bindings.
    # Refuse the full saved plan and use all shipped mappings, not a partial
    # fallback that could leave a movement direction or command unreachable.
    assert doc.call_method('WritePreference',('key_left','J'))[0]
    values=list(doc.get_editor_property('Entries'))
    bad=next(row for row in values if field(row,'Key',ROW)=='key_forward')
    bad.set_editor_property(field_name('Value',ROW),'J')
    fixture.call_method('SetPreferencesEntries',(doc,values))
    check(not builder.call_method('ValidateBindings',(doc,)),'effective bindings reject corrupted duplicate keys')
    fallback,accepted,defaults=builder.call_method('BuildEditorContext',(doc,))
    check(accepted and defaults and all(contents_equal(a,b) for a,b in zip(rows(fallback),original)),
          'conflicting saved plan falls back to the complete reachable default mapping')
    fallback,accepted,defaults=builder.call_method('BuildEditorContext',(None,))
    check(accepted and defaults and all(contents_equal(a,b) for a,b in zip(rows(fallback),original)),
          'missing preference document still produces usable default controls')
