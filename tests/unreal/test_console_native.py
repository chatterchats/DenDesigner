"""Compiled office-console identity, request and world-lifetime behavior."""

def run(unreal,check):
    from runtime_console import CONSOLE,MESH,PROMPT,LABEL,ICON_TAG
    cls=unreal.EditorAssetLibrary.load_blueprint_class(CONSOLE)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    console=actors.spawn_actor_from_class(cls,unreal.Vector(),unreal.Rotator(),transient=True)
    target=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(100,200,300),unreal.Rotator(),transient=True)
    component=target.static_mesh_component
    component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
    prop=lambda obj,key:obj.get_editor_property(key)
    def set_target(value):
        problem=unreal.ZComAuthoringLibrary.set_property_from_text(console,'Target','None' if value is None else value.get_path_name())
        assert not problem,problem
    try:
        check(console.call_method('MatchesConsole',(MESH,'/Game/Game/Maps/Hub/HUB_Root.HUB_Root:PersistentLevel.Console')),
              'office console matches its exact mesh in a native Den level')
        for mesh,path in [(MESH.replace('3x1','1x1'),'/Game/Game/Maps/Hub/HUB_Root.HUB_Root:PersistentLevel.Console'),
                          (MESH,'/Game/Game/Maps/Missions/Test.Test:PersistentLevel.Console'),
                          (MESH,'/DenDesignerGF/Runtime/Test.Test:PersistentLevel.Copy'),
                          (MESH,'/Game/Game/Maps/HubCopy/Test.Test:PersistentLevel.Console')]:
            check(not console.call_method('MatchesConsole',(mesh,path)),
                  'office interaction rejects a different mesh, mission, mod copy or similarly named level')
        indicator=prop(console,'PromptIndicator')
        check(indicator is not None and prop(indicator,'Lifetime')==unreal.BitReactorWidgetComponentLifetime.MANUAL,
              'console owns a manually managed native exploration prompt indicator: '+str(prop(indicator,'Lifetime')))
        config=prop(indicator,'IndicatorConfig')
        widget=config.get_editor_property('WidgetClass')
        widget_path=widget.get_path_name() if hasattr(widget,'get_path_name') else str(widget)
        check(widget_path==PROMPT and config.get_editor_property('bClampToScreen'),
              'console indicator uses the shipped exploration key and label widget: '+str(config))
        interaction=prop(console,'Interaction')
        check(interaction.get_attach_parent()==console.root_component,
              'native interaction stays attached to the moving console anchor')
        actions=prop(interaction,'InputActionAbilities')
        check(len(actions)==1 and actions[0].input_action is not None and actions[0].input_action.get_path_name()=='/Game/Game/Input/Actions/IA_ExploreInteract.IA_ExploreInteract',
              'console prompt uses the game exploration interaction action')
        # Reproduce the game's non-ability action: correct input, empty metadata.
        live=unreal.new_object(unreal.InteractableAction,outer=console)
        empty=unreal.InputActionAbilities()
        empty.set_editor_property('InputAction',actions[0].input_action)
        live.set_editor_property('Abilities',empty)
        assert not unreal.ZComAuthoringLibrary.set_property_from_text(interaction,'CurrentInteraction',live.get_path_name())
        assert not unreal.ZComAuthoringLibrary.set_property_from_text(live,'Abilities.AbilityTags','(GameplayTags=((TagName="BitReactor.Ability.Type.Interaction")))')
        console.call_method('PresentCurrentInteraction')
        presented=prop(live,'Abilities')
        check(str(presented.interaction_text)==LABEL and presented.input_action==actions[0].input_action,
              'live non-ability action receives the designer label without changing its input action')
        check(str(presented.icon.image_bank_tag.get_editor_property('TagName'))==ICON_TAG and presented.icon.image_reference_type==unreal.BitReactorImageReferenceType.IMAGE_BANK,
              'live non-ability action receives the registered edit icon for the distant marker')
        check('BitReactor.Ability.Type.Interaction' in str(presented.ability_tags),
              'live presentation preserves existing gameplay ability tags')
        console.call_method('PresentCurrentInteraction')
        check(str(prop(live,'Abilities').interaction_text)==LABEL,
              'repeated proximity presentation keeps a stable designer label')
        assert not unreal.ZComAuthoringLibrary.set_property_from_text(interaction,'CurrentInteraction','None')
        console.call_method('PresentInteractionAction',(None,))
        console.call_method('PresentCurrentInteraction')
        console.call_method('RequestOpen')
        check(not console.call_method('ConsumeRequest'),'uninitialized console cannot request the editor')
        set_target(component);console.call_method('SetAvailable',(True,))
        console.call_method('RequestOpen');console.call_method('RequestOpen')
        check(console.call_method('ConsumeRequest') and not console.call_method('ConsumeRequest'),
              'repeated native interaction coalesces into a single consumed editor request')
        console.call_method('RequestOpen');console.call_method('SetAvailable',(False,))
        check(not console.call_method('ConsumeRequest') and not prop(console,'Enabled'),
              'disabling the console clears pending activation while the designer is open')
        console.call_method('UpdateConsole',(True,))
        position=console.get_actor_location()
        check(prop(console,'Enabled') and all(abs(value-expected)<.01 for value,expected in zip((position.x,position.y,position.z),(100,200,300))),
              'interaction follows the console mesh bounds rather than an empty Blueprint root')
        actors.destroy_actor(target);target=None
        console.call_method('UpdateConsole',(True,));console.call_method('RequestOpen')
        check(not prop(console,'Enabled') and not console.call_method('ConsumeRequest'),
              'streaming out the target removes availability and prevents stale activation')
        set_target(None);console.call_method('SetAvailable',(True,));console.call_method('RequestOpen')
        check(not console.call_method('ConsumeRequest'),'an enabled interaction still requires a live console target')
    finally:
        if target is not None:actors.destroy_actor(target)
        actors.destroy_actor(console)
