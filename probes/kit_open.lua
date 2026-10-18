-- Phase 0b: load the kit-cooked probe assets, show WBP_Probe, spawn BP_ProbeRig as the view target with its IMC.
local g,P,log=S.g,S.P,S.log
local pc=assert(S.pc(),'no player controller')
local ctx=g.any_context()
local classes={}
for _,n in ipairs({'WBP_Probe','WBP_ProbeEntry','BP_ProbeItem','BP_ProbeRig'}) do
 classes[n]=S.load_class(P..n..'.'..n..'_C');log('class',n,classes[n] and classes[n]:GetFullName() or 'MISSING')
end
local imc=S.load_object(P..'IMC_Probe.IMC_Probe');log('imc',imc and imc:GetFullName() or 'MISSING')
assert(classes.WBP_Probe and classes.BP_ProbeRig and imc,'probe assets missing')

if not S.hooked then
 RegisterHook(P..'WBP_Probe.WBP_Probe_C:Lua_Event',function(self,name,arg)
  local n,a=S.str(name),S.str(arg);log('Lua_Event',n,a)
  pcall(function() self:get().Status:SetText(FText('Lua heard: '..n..' "'..a..'"')) end)
 end)
 -- Holding RMB hides and locks the cursor (GameOnly captures the mouse) so a drag can turn forever.
 S.on_action=function(name,value)
  if name~='look_hold' then return end
  local pc=S.pc();local wbl=StaticFindObject('/Script/UMG.Default__WidgetBlueprintLibrary')
  if value>0.5 then pc.bShowMouseCursor=false;wbl:SetInputMode_GameOnly(pc,false)
  else wbl:SetInputMode_GameAndUIEx(pc,nil,0,false,false);pc.bShowMouseCursor=true end
 end
 RegisterHook(P..'BP_ProbeRig.BP_ProbeRig_C:Lua_Action',function(self,name,value)
  local n,v=S.str(name),value:get();log('Lua_Action',n,v)
  local ok,err=pcall(S.on_action,n,v);if not ok then log('on_action error',err) end
 end)
 RegisterHook(P..'BP_ProbeRig.BP_ProbeRig_C:Lua_Tick',function(self,dt)
  S.ticks=(S.ticks or 0)+1
 end)
 S.hooked=true;log('hooks registered')
end

local wbl=StaticFindObject('/Script/UMG.Default__WidgetBlueprintLibrary')
local w=wbl:Create(pc,classes.WBP_Probe,pc);assert(g.valid(w),'widget create failed')
w:AddToViewport(50);S.widget=w;log('widget',w:GetFullName())
for i,name in ipairs({'Crate','Barrel','Holo table','Bar stool','Lamp','Plant'}) do
 local item=StaticConstructObject(classes.BP_ProbeItem,w,FName('ProbeItem'..i),0,0,false,false,nil)
 item.Title=name;w.Items:AddItem(item)
end
log('items',w.Items:GetNumItems())

-- Start where the game camera is. The rig is a CameraActor: the Den's camera manager rejects
-- view targets that aren't camera-rooted (and the pawn); hand back the Camroid we replace on close.
local cm=pc.PlayerCameraManager
local at,rot=cm:GetCameraLocation(),cm:GetCameraRotation()
local xf=g.xform(at,rot.Yaw)
local d=g.gameplay():BeginDeferredActorSpawnFromClass(ctx,classes.BP_ProbeRig,xf,1,nil,1)
local rig=d and g.gameplay():FinishSpawningActor(d,xf,1);assert(g.valid(rig),'rig spawn failed')
rig:K2_SetActorRotation({Pitch=rot.Pitch,Yaw=rot.Yaw,Roll=0},true)
S.rig=rig;log('rig',rig:GetFullName(),'Speed',rig.Speed)
S.view_was=pc:GetViewTarget()
pc:SetViewTargetWithBlend(rig,0.3,0,0,false)
log('view target',pc:GetViewTarget():GetFName():ToString())
-- Clicks go only to our actions while the probe is open.
pc.bEnableClickEvents=false;pc.bEnableMouseOverEvents=false
rig:EnableInput(pc)
local sub=FindFirstOf('EnhancedInputLocalPlayerSubsystem')
sub:AddMappingContext(imc,1000000,{bIgnoreAllPressedKeysUntilRelease=false,bForceImmediately=true,bNotifyUserSettings=false})
S.sub,S.imc=sub,imc
S.cursor_was=pc.bShowMouseCursor
wbl:SetInputMode_GameAndUIEx(pc,nil,0,false,false);pc.bShowMouseCursor=true
log('open: WASD fly, Space/Ctrl up/down, Shift fast, hold RMB to look, LMB click, Go button, type + Enter')
