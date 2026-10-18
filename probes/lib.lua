-- Shared probe helpers for the dev console (run first; S persists between console snippets).
-- Den Designer's own game.lua (loaded by file: other mods also have a module named "game").
S.DEN='Z:/run/media/chats/e0057d4a-fe46-43eb-a837-db51979c500f/ZComMods/ZComDenDesigner/src/ZComDen/Scripts/'
S.g=dofile(S.DEN..'game.lua').new(print)
local g=S.g
S.LOG='Z:/tmp/den-probe.log'
function S.log(...)
 local t={};for i=1,select('#',...) do t[#t+1]=tostring(select(i,...)) end
 local line=os.date('%H:%M:%S ')..table.concat(t,' ')
 print(line);local f=io.open(S.LOG,'a');if f then f:write(line..'\n');f:close() end
end
-- Kit-cooked assets: engine soft loads only (UE4SS LoadAsset crashed on kit assets before).
function S.load_class(path)
 local ok,found=pcall(StaticFindObject,path);if ok and g.valid(found) then return found end
 local k=g.kismet()
 local ref=k:Conv_SoftClassPathToSoftClassRef(k:MakeSoftClassPath(path))
 local c=k:LoadClassAsset_Blocking(ref);return g.valid(c) and c or nil
end
function S.load_object(path)
 local ok,found=pcall(StaticFindObject,path);if ok and g.valid(found) then return found end
 local k=g.kismet()
 local ref=k:Conv_SoftObjPathToSoftObjRef(k:MakeSoftObjectPath(path))
 local o=k:LoadAsset_Blocking(ref);return g.valid(o) and o or nil
end
function S.pc()
 local ctx=g.any_context();if not g.valid(ctx) then return nil end
 local pc=g.gameplay():GetPlayerController(ctx,0);return g.valid(pc) and pc or nil
end
function S.str(p) local ok,v=pcall(function() return p:get():ToString() end);return ok and v or tostring(p) end
S.P='/Game/ZComDen/Probe/'
print('lib ok',g.world_name(g.any_context()))
