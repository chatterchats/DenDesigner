-- Undo kit_open.lua: widget, rig, mapping context, view target, input mode.
local g,log=S.g,S.log
local pc=S.pc()
pcall(function() if g.valid(S.widget) then S.widget:RemoveFromParent() end end)
pcall(function() if g.valid(S.sub) and g.valid(S.imc) then S.sub:RemoveMappingContext(S.imc,{bIgnoreAllPressedKeysUntilRelease=false,bForceImmediately=true,bNotifyUserSettings=false}) end end)
if pc then
 pc.bEnableClickEvents=true;pc.bEnableMouseOverEvents=true
 local pawn=g.gameplay():GetPlayerPawn(g.any_context(),0)
 pcall(function() pc:SetViewTargetWithBlend(g.valid(S.view_was) and S.view_was or FindFirstOf('BR_Camroid_Explore_Pro_B_C') or pawn,0.3,0,0,false) end)
 local wbl=StaticFindObject('/Script/UMG.Default__WidgetBlueprintLibrary')
 pcall(function()
  if S.cursor_was then wbl:SetInputMode_GameAndUIEx(pc,nil,0,false,false);pc.bShowMouseCursor=true
  else wbl:SetInputMode_GameOnly(pc,false);pc.bShowMouseCursor=false end
 end)
end
pcall(function() if g.valid(S.rig) then S.rig:K2_DestroyActor() end end)
log('closed; rig ticks into Lua:',S.ticks or 0)
S.widget,S.rig,S.imc=nil,nil,nil
