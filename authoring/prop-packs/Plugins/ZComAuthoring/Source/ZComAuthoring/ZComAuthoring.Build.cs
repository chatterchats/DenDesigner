using UnrealBuildTool;

public class ZComAuthoring : ModuleRules
{
	public ZComAuthoring(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });
		PrivateDependencyModuleNames.AddRange(new[]
		{
			"AssetRegistry", "BlueprintGraph", "EnhancedInput", "InputBlueprintNodes", "InputCore", "Json", "Kismet",
			"KismetCompiler", "Slate", "SlateCore", "UMG", "UMGEditor", "UnrealEd",
		});
	}
}
