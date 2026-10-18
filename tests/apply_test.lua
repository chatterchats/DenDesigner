-- Offline test of apply.lua + den_watch.lua against a small mock of the UE4SS API (LuaJIT, no game).
-- Usage: luajit tests/apply_test.lua src/ZComDen
local src = assert(arg[1], "usage: apply_test.lua <mod dir>")
package.path = src .. "/Scripts/?.lua;" .. package.path

local failures, checks = 0, 0
local function check(cond, what)
    checks = checks + 1
    if not cond then failures = failures + 1; print("FAIL: " .. what) end
end

-- Mock UE4SS ----------------------------------------------------------------------------------------------
local objects, queue, handles, now = {}, {}, 0, 0
local WORLD = { name = "World /Game/Game/Maps/Hub/HUB_Root.HUB_Root", address = 1 }
local Object = {}
Object.__index = Object
function Object:IsValid() return not self.destroyed end
function Object:GetFullName() return self.class .. " " .. self.path end
function Object:GetFName() local n = self.path:match("[%.:]([^%.:]+)$"); return { ToString = function() return n end } end
function Object:GetWorld() return self.world end
function Object:IsA(class) return self.isa[class.path] == true end
local function new(path, class, isa, fields)
    local o = setmetatable(fields or {}, Object)
    o.path, o.class, o.isa, o.world = path, class, isa or {}, WORLD
    objects[path] = o
    return o
end
local world_obj = setmetatable({}, { __index = function(_, k)
    if k == "GetFullName" then return function() return WORLD.name end end
    if k == "GetAddress" then return function() return WORLD.address end end
    if k == "IsValid" then return function() return true end end
end })
WORLD.obj = world_obj
function Object:GetWorld() return self.world and self.world.obj end

local function class(path) return new(path, "Class", {}) end
for _, p in ipairs({ "/Script/Engine.Actor", "/Script/Engine.StaticMesh", "/Script/Engine.StaticMeshComponent", "/Script/Engine.ActorComponent",
                    "/Script/Engine.MaterialInterface" }) do class(p) end
local ACTOR, COMPONENT = { ["/Script/Engine.Actor"] = true }, { ["/Script/Engine.StaticMeshComponent"] = true }

local function scene(o)
    o.loc, o.rot, o.scale, o.Mobility, o.visible, o.collision = o.loc or { X = 0, Y = 0, Z = 0 }, { Pitch = 0, Yaw = 0, Roll = 0 }, { X = 1, Y = 1, Z = 1 }, o.Mobility or 0, true, 3
    function o:SetMobility(m) self.Mobility = m end
    function o:K2_GetComponentLocation() return self.loc end
    function o:K2_GetComponentRotation() return self.rot end
    function o:K2_GetComponentScale() return self.scale end
    function o:K2_SetWorldLocationAndRotation(l, r) assert(self.Mobility == 2, "moved while static"); self.loc, self.rot = l, r end
    function o:SetWorldScale3D(s) self.scale = s end
    function o:IsVisible() return self.visible end
    function o:SetVisibility(v) self.visible = v end
    function o:GetCollisionEnabled() return self.collision end
    function o:SetCollisionEnabled(c) self.collision = c end
    function o:SetStaticMesh(m) self.StaticMesh = m end
    function o:SetCollisionProfileName(n) self.profile = n:ToString() end
    function o:SetCollisionResponseToChannel(ch, r) self.pawn_ignored = ch == 2 and r == 0 end
    function o:SetMaterial(slot, m) self.materials = self.materials or {}; self.materials[slot] = m end
    return o
end
local function actor(path, root)
    local a = new(path, "Actor", ACTOR, { root = root, bHidden = false, enable_collision = true })
    function a:K2_GetRootComponent() return self.root end
    function a:K2_GetActorLocation() return self.root.loc end
    function a:K2_GetActorRotation() return self.root.rot end
    function a:GetActorScale3D() return self.root.scale end
    function a:K2_SetActorLocationAndRotation(l, r) assert(not self.root or self.root.Mobility == 2 or self.spawned, "moved while static"); self.root.loc, self.root.rot = l, r end
    function a:SetActorScale3D(s) self.root.scale = s end
    function a:SetActorHiddenInGame(h) self.bHidden = h end
    function a:GetActorEnableCollision() return self.enable_collision end
    function a:SetActorEnableCollision(c) self.enable_collision = c end
    function a:K2_DestroyActor() self.destroyed = true; objects[self.path] = nil end
    function a:K2_GetComponentsByClass()
        local out = {}
        for path, o in pairs(objects) do
            -- Like UE4SS: the returned table holds wrapped values (call :get() for the object).
            if path:sub(1, #self.path + 1) == self.path .. "." and not path:sub(#self.path + 2):find("%.") then out[#out + 1] = { get = function() return o end } end
        end
        return out
    end
    return a
end

local BAR = "/Game/Game/Maps/Hub/Sublevels/Environment/HUB_Bar_A.HUB_Bar_A:PersistentLevel."
local LATE = "/Game/Game/Maps/Hub/Sublevels/Environment/HUB_Late.HUB_Late:PersistentLevel"
local levels = { new(BAR:sub(1, -2), "Level", {}) }
rawset(world_obj, "Levels", levels)
local chair = actor(BAR .. "Chair_1", scene(new(BAR .. "Chair_1.StaticMeshComponent0", "StaticMeshComponent", COMPONENT)))
local bottle = scene(new(BAR .. "Shelf_2.Bottle", "StaticMeshComponent", COMPONENT))
actor(BAR .. "Shelf_2", scene(new(BAR .. "Shelf_2.Root", "SceneComponent", COMPONENT)))
local mesh = new("/Game/Props/SM_Lamp.SM_Lamp", "StaticMesh", { ["/Script/Engine.StaticMesh"] = true })
function mesh:GetBounds() return { BoxExtent = { X = 40, Y = 40, Z = 60 } } end
local tiny = new("/Game/Props/SM_Cup.SM_Cup", "StaticMesh", { ["/Script/Engine.StaticMesh"] = true })
function tiny:GetBounds() return { BoxExtent = { X = 5, Y = 5, Z = 8 } } end
local red = new("/Game/Props/MI_Red.MI_Red", "MaterialInstanceConstant", { ["/Script/Engine.MaterialInterface"] = true })
local instance = new("/Engine/Transient.GameEngine_0:BP_BrunoGameInstance_C_0", "BP_BrunoGameInstance_C", {})

local spawned = 0
local gameplay = new("/Script/Engine.Default__GameplayStatics", "GameplayStatics", {})
function gameplay:BeginDeferredActorSpawnFromClass() spawned = spawned + 1; local a = actor("/Game/Game/Maps/Hub/HUB_Root.HUB_Root:PersistentLevel.Actor_" .. spawned); a.spawned = true; return a end
function gameplay:FinishSpawningActor(a) return a end
function Object:AddComponentByClass()
    local c = scene(new(self.path .. ".StaticMeshComponent0", "StaticMeshComponent", COMPONENT))
    self.root = c
    return c
end
local kismet = new("/Script/Engine.Default__KismetSystemLibrary", "KismetSystemLibrary", {})
function kismet:MakeSoftObjectPath(p) return { p = p } end
function kismet:Conv_SoftObjPathToSoftObjRef(s) return s end
function kismet:LoadAsset_Blocking(s) return objects[s.p] end

function StaticFindObject(path) return objects[path] end
function FindFirstOf(name)
    if name == "BrunoGameInstance" then return instance end
    if name == "BrunoSaveGameSubsystem" then return nil end
end
function FindAllOf(class)
    local out = {}
    if class == "Actor" then for _, o in pairs(objects) do if o.isa["/Script/Engine.Actor"] and not o.destroyed then out[#out + 1] = o end end end
    return out
end
function FName(s) return { ToString = function() return s end } end
function MakeActionHandle() handles = handles + 1; return handles end
function ExecuteInGameThreadWithDelay(handle, delay, fn) queue[#queue + 1] = { at = now + delay, fn = fn, handle = handle } end
function ExecuteInGameThread(fn) fn() end
function CancelDelayedAction(handle)
    for i, q in ipairs(queue) do if q.handle == handle then table.remove(queue, i); return true end end
    return false
end
function IsValidDelayedActionHandle() return true end
function IsDelayedActionActive() return true end
function UnregisterHook() end
local function advance(ms)
    local stop = now + ms
    while true do
        table.sort(queue, function(a, b) return a.at < b.at end)
        local q = queue[1]
        if not q or q.at > stop then break end
        table.remove(queue, 1)
        now = q.at
        q.fn()
    end
    now = stop
end

-- Den Designer over the mock ----------------------------------------------------------------------------
local json = require("json")
local logs = {}
local function log(fmt, ...) logs[#logs + 1] = select("#", ...) > 0 and string.format(fmt, ...) or fmt end
local runtime = require("hook_registry").start("ZComDenTestRuntime", {})
local actions = require("actions").new(runtime, { log = log })
local g = require("game").new(log)
local base = os.tmpname(); os.remove(base)
local store = require("store").new({ base = base, sep = "/", log = log,
    mkdir = function(f) for _, d in ipairs(f) do os.execute("mkdir -p '" .. d .. "'") end return true end })
local ctx = { runtime = runtime, actions = actions, log = log, g = g, store = store }

local layout = {
    format = 1,
    placed = json.array({
        { id = "p0001", mesh = "/Game/Props/SM_Lamp.SM_Lamp", t = json.array({ 100, 200, 0 }), r = json.array({ 0, 90, 0 }) },
        { id = "p0002", mesh = "/Game/Props/SM_Cup.SM_Cup", t = json.array({ 0, 0, 90 }) },
        { id = "p0003", mesh = "/Game/Props/SM_Gone.SM_Gone", t = json.array({ 0, 0, 0 }) },
    }),
    vanilla = {
        [BAR .. "Chair_1"] = { t = json.array({ 50, 60, 0 }), r = json.array({ 0, 45, 0 }) },
        [BAR .. "Shelf_2.Bottle"] = { hidden = true },
        [BAR .. "NotStreamed_9"] = { hidden = true },
        [LATE .. ".LateChair_1"] = { hidden = true },
    },
}
assert(store:save("home", nil, require("layout").normalise(layout)))

local watch = require("den_watch").new(ctx)
watch:install()
-- HUB_Late streams in three seconds after arrival.
local late_chair
advance(3000)
levels[#levels + 1] = new(LATE, "Level", {})
late_chair = actor(LATE .. ".LateChair_1", scene(new(LATE .. ".LateChair_1.StaticMeshComponent0", "StaticMeshComponent", COMPONENT)))
advance(20000)
check(late_chair.bHidden == true, "an object in a late-streamed level is edited when its level arrives")
local report = watch.apply.report
check(report.placed == 2, "placed 2 of 3 (" .. report.placed .. ")")
check(#report.missing == 1 and report.missing[1]:find("p0003") ~= nil, "the missing mesh is reported")
check(report.hidden == 2 and report.moved == 1, "two hidden, one moved (" .. report.hidden .. ", " .. report.moved .. ")")
check(#report.dormant == 1 and report.dormant[1]:find("NotStreamed_9") ~= nil, "an object missing from a loaded level is dormant")
check(report.scans == 2, "one scan on arrival, one when the late level came in (" .. report.scans .. ")")
check(chair.root.loc.X == 50 and chair.root.rot.Yaw == 45 and chair.root.Mobility == 2, "chair moved (made movable)")
check(bottle.visible == false and bottle.collision == 0, "bottle hidden, no collision")
local lamp_host = objects["/Game/Game/Maps/Hub/HUB_Root.HUB_Root:PersistentLevel.Actor_1"]
check(lamp_host and lamp_host.root.loc.X == 100 and lamp_host.root.rot.Yaw == 90, "placed transform set after the component")
check(lamp_host.root.profile == "BlockAll" and not lamp_host.root.pawn_ignored, "big mesh is solid")
local cup_host = objects["/Game/Game/Maps/Hub/HUB_Root.HUB_Root:PersistentLevel.Actor_2"]
check(cup_host and cup_host.root.pawn_ignored, "small mesh lets pawns through")
local summary
for _, l in ipairs(logs) do if l:find("^Den | home layout") then summary = l end end
check(summary ~= nil and summary:find("2 placed, 2 hidden, 1 moved") ~= nil, "summary logged: " .. tostring(summary))

-- The editor's single-object operations.
local apply = watch.apply
local BOTTLE = BAR .. "Shelf_2.Bottle"
check(apply:set_vanilla(BOTTLE, bottle, { t = json.array({ 7, 8, 9 }), hidden = true }) and bottle.loc.X == 7 and bottle.visible == false,
    "set_vanilla moves and hides one object")
check(apply:original(BOTTLE).loc.X == 0, "and remembers where it stood")
check(apply:set_vanilla(BOTTLE, bottle, nil) and bottle.loc.X == 0 and bottle.visible == true and bottle.Mobility == 0,
    "set_vanilla nil puts it back as the Den had it")
check(apply:original(BOTTLE) ~= nil, "the record stays for the editor")
local SHELF_ROOT = BAR .. "Shelf_2.Root"
check(apply:track(SHELF_ROOT, objects[SHELF_ROOT]) ~= nil and apply:original(SHELF_ROOT).loc.X == 0, "track records without changing")
check(apply:track(BAR .. "Ghost_1", objects["/Game/Props/SM_Cup.SM_Cup"]) == nil, "track refuses an object at another path")
local entry = { id = "p0009", mesh = "/Game/Props/SM_Lamp.SM_Lamp", t = json.array({ 1, 1, 1 }), r = json.array({ 0, 0, 0 }),
                s = json.array({ 1, 1, 1 }), mats = json.array({ "", "/Game/Props/MI_Red.MI_Red" }) }
check(apply:set_placed("p0009", entry), "set_placed spawns a new mesh")
local record = apply.placed.p0009
check(record and record.component.materials and record.component.materials[1] == red, "with its material overrides")
check(apply:placed_id(record.path) == "p0009", "placed_id finds it by its actor's path")
local host = record.actor
entry.t = json.array({ 5, 5, 5 })
check(apply:set_placed("p0009", entry) and apply.placed.p0009.actor == host and host.root.loc.X == 5, "a move keeps the same actor")
entry.mats = nil
check(apply:set_placed("p0009", entry) and host.destroyed and apply.placed.p0009.actor ~= host, "new materials respawn it")
host = apply.placed.p0009.actor
check(apply:set_placed("p0009", nil) and host.destroyed and apply.placed.p0009 == nil, "set_placed nil removes it")

-- Hot reload: unhide the bottle in the file; the old edits are undone and the new layout applied.
layout.vanilla[BAR .. "Shelf_2.Bottle"] = nil
assert(store:save("home", nil, require("layout").normalise(layout)))
advance(20000)
check(bottle.visible == true and bottle.collision == 3, "bottle back after the file changed")
check(lamp_host.destroyed and watch.apply.placed.p0001 and not watch.apply.placed.p0001.actor.destroyed,
    "placed meshes rebuilt on reload")

-- Another mod hid the bottle first: our restore must not unhide it.
layout.vanilla[BAR .. "Shelf_2.Bottle"] = { hidden = true }
bottle.visible = false
assert(store:save("home", nil, require("layout").normalise(layout)))
advance(20000)
-- A mod reload while in the Den undoes everything in place.
runtime:teardown("test reload")
check(bottle.visible == false, "an object hidden by someone else stays hidden after we restore")
check(chair.root.loc.X == 0 and chair.root.Mobility == 0, "chair restored, static again")
local live = 0
for p, o in pairs(objects) do if p:find("PersistentLevel%.Actor_%d+$") and not o.destroyed then live = live + 1 end end
check(live == 0, "placed meshes destroyed on teardown (" .. live .. " left)")

-- Leaving the Den: nothing of the old world is touched.
runtime = require("hook_registry").start("ZComDenTestRuntime2", {})
actions = require("actions").new(runtime, { log = log })
ctx = { runtime = runtime, actions = actions, log = log, g = g, store = store }
watch = require("den_watch").new(ctx)
watch:install()
advance(20000)
local chair_x = chair.root.loc.X
local touched = false
local orig = chair.K2_SetActorLocationAndRotation
chair.K2_SetActorLocationAndRotation = function(...) touched = true; return orig(...) end
WORLD.address, WORLD.name = 2, "World /Game/Game/Maps/Mission/M.M"
advance(3000)
check(not touched and chair.root.loc.X == chair_x, "leaving the Den doesn't touch the old world's objects")
check(next(watch.apply.edits) == nil and next(watch.apply.placed) == nil, "and drops every reference")

os.execute("rm -rf '" .. base .. "'")
print(string.format("apply_test: %d checks, %d failures", checks, failures))
if failures > 0 then for _, l in ipairs(logs) do print("  log: " .. l) end end
os.exit(failures == 0 and 0 or 1)
