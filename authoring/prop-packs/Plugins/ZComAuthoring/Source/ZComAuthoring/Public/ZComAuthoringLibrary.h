#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "ZComAuthoringLibrary.generated.h"

/**
 * Builds mod assets from JSON specs (see the plugin README for the format). Called from Python
 * (unreal.ZComAuthoringLibrary) by headless authoring scripts; editor-only, never cooked.
 */
UCLASS()
class ZCOMAUTHORING_API UZComAuthoringLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Builds one asset (blueprint, widget, input_action or mapping_context) from a JSON spec. The asset must not
	 * exist yet: delete it first with ForceDeleteAssets. Returns a JSON report {"ok": bool, "messages": [..]};
	 * the caller saves the asset when ok.
	 */
	UFUNCTION(BlueprintCallable, Category = "ZCom Authoring")
	static FString BuildAssetFromJson(const FString& SpecJson);

	/**
	 * Deletes the assets at these package paths (missing ones are skipped), then collects garbage. There is no
	 * reference check: delete a whole set of assets that only reference each other.
	 */
	UFUNCTION(BlueprintCallable, Category = "ZCom Authoring")
	static int32 ForceDeleteAssets(const TArray<FString>& PackagePaths);

	/**
	 * Sets one property of Object from Unreal's text import format, with the spec rules for "props" (a dotted
	 * path walks into structs). For types Python can't build, such as a GameFeatureAction's entry structs.
	 * Returns an empty string on success, otherwise what went wrong.
	 */
	UFUNCTION(BlueprintCallable, Category = "ZCom Authoring")
	static FString SetPropertyFromText(UObject* Object, const FString& Path, const FString& Value);

	/** Headless tests only: finish async IO and advance latent callbacks in a non-game editor world. */
	UFUNCTION(BlueprintCallable, Category = "ZCom Authoring|Tests")
	static bool ProcessTestLatentActions(UObject* Context);
};
