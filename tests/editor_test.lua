-- Offline tests for history.lua and pick.lua (LuaJIT, no game). Usage: luajit tests/editor_test.lua src/ZComDen
local src = assert(arg[1], "usage: editor_test.lua <mod dir>")
package.path = src .. "/Scripts/?.lua;" .. package.path
local json, Layout, History, Pick = require("json"), require("layout"), require("history"), require("pick")

local failures, checks = 0, 0
local function check(cond, what)
    checks = checks + 1
    if not cond then failures = failures + 1; print("FAIL: " .. what) end
end

-- history ----------------------------------------------------------------------------------------------------
local CHAIR = "/Game/Maps/HUB_Bar_A.HUB_Bar_A:PersistentLevel.Chair_1"
local doc = Layout.normalise({ format = 1, placed = { { id = "p0001", mesh = "/Game/A/SM_A.SM_A", t = { 0, 0, 0 } } },
                               vanilla = { [CHAIR] = { hidden = true } } })
local seen = {}  -- what the "Den" was told last, per entry
local refuse
local world = {
    vanilla = function(key, edit) seen["v:" .. key] = edit or "none"; return true end,
    placed = function(id, entry) seen["p:" .. id] = entry or "none"; if refuse then return false, "refused" end return true end,
}
local now = 0
local h = History.new(doc, world, { clock = function() return now end })

check(not h:dirty(), "a fresh history is clean")
local lamp = { id = "p0002", mesh = "/Game/A/SM_Lamp.SM_Lamp", t = json.array({ 1, 2, 3 }), r = json.array({ 0, 0, 0 }), s = json.array({ 1, 1, 1 }) }
h:commit("Copy", { { "placed", "p0002", lamp } })
check(#doc.placed == 2 and doc.placed[2].id == "p0002", "a placed entry is added to the layout")
check(seen["p:p0002"].mesh == lamp.mesh, "and to the Den")
lamp.t[1] = 99
check(doc.placed[2].t[1] == 1, "the layout keeps its own copy")
check(h:dirty(), "a change makes it dirty")

h:commit("Store", { { "vanilla", CHAIR, nil } })
check(doc.vanilla[CHAIR] == nil and seen["v:" .. CHAIR] == "none", "a vanilla entry can be removed")
check(h:undo() == "Store" and doc.vanilla[CHAIR].hidden == true and seen["v:" .. CHAIR].hidden == true, "undo puts it back")
check(h:undo() == "Copy" and #doc.placed == 1 and seen["p:p0002"] == "none", "undo removes the copy again")
check(not h:dirty(), "undoing everything is clean again")
check(h:undo() == nil, "nothing more to undo")
check(h:redo() == "Copy" and #doc.placed == 2, "redo adds it back")
check(h:redo() == "Store" and doc.vanilla[CHAIR] == nil, "redo removes the edit again")
check(h:redo() == nil, "nothing more to redo")

-- Wheel turns on the same object merge into one step within a second.
local function turn(yaw) h:commit("Rotate", { { "placed", "p0001", { id = "p0001", mesh = "/Game/A/SM_A.SM_A", t = { 0, 0, 0 }, r = { 0, yaw, 0 }, s = { 1, 1, 1 } } } }, "rotate") end
local steps = #h.undos
turn(15); now = 0.5; turn(30); now = 0.9; turn(45)
check(#h.undos == steps + 1 and doc.placed[1].r[2] == 45, "three quick turns are one step")
now = 3; turn(60)
check(#h.undos == steps + 2, "a turn after a pause is a new step")
h:undo()
check(doc.placed[1].r[2] == 45, "undo goes back one step")
h:undo()
check(doc.placed[1].r == nil or doc.placed[1].r[2] == 0, "and the merged step goes back to before the first turn")
now = 3.2; turn(90)
check(#h.redos == 0 and doc.placed[1].r[2] == 90, "a new change clears redo and doesn't merge across an undo")

h:mark_saved()
check(not h:dirty(), "saved is clean")
now = 10; turn(100)
check(h:dirty(), "a change after saving is dirty")
h:undo()
check(not h:dirty(), "undo back to the save point is clean")

refuse = true
local ok, why = h:commit("Move", { { "placed", "p0001", { id = "p0001", mesh = "/Game/A/SM_A.SM_A", t = { 5, 5, 5 }, r = { 0, 0, 0 }, s = { 1, 1, 1 } } } })
check(ok == false and why == "refused" and doc.placed[1].t[1] == 5, "a refusal is reported; the layout still records it")
refuse = false

local text = json.encode(doc)
local back = Layout.normalise(json.decode(text))
check(#back.placed == 2 and back.vanilla[CHAIR] == nil, "the edited layout saves and loads cleanly")

-- layout: materials
local norm, problems = Layout.normalise({ placed = { { id = "p1", mesh = "/Game/A/SM_A.SM_A", t = { 0, 0, 0 },
                                                       mats = { "", "/Game/M/MI_Red.MI_Red", "not a path" } } } })
check(norm.placed[1].mats[2] == "/Game/M/MI_Red.MI_Red" and norm.placed[1].mats[3] == "" and #problems == 1,
    "bad material slots fall back to the mesh's own")
check(json.encode(norm):find('"mats"') ~= nil, "materials are saved")

-- pick rules -------------------------------------------------------------------------------------------------
local BAR = "/Game/Game/Maps/Hub/Sublevels/Environment/HUB_Bar_A.HUB_Bar_A:PersistentLevel.StaticMeshActor_3.StaticMeshComponent0"
local GAMEPLAY = "/Game/Game/Maps/Hub/Sublevels/Facilities/HUB_Holotable_Gameplay.HUB_Holotable_Gameplay:PersistentLevel.BP_Holotable_C_1.HoloTable_Body"
local CIN = "/Game/Game/Maps/Hub/Sublevels/HUB_Cinematics.HUB_Cinematics:PersistentLevel.Cube_2.StaticMeshComponent0"
local function prop(extra)
    local f = { path = BAR, mesh_component = true, mesh = "/Game/Game/Environments/Strategy/HQ/Props/Bar/Bottles/SM_Bottle.SM_Bottle", size = 30 }
    for k, val in pairs(extra or {}) do f[k] = val end
    return f
end
check(Pick.allowed(prop()) == true, "a bar prop can be edited")
check(Pick.allowed(prop({ placed = "p0001", path = GAMEPLAY })) == true, "our own placed meshes always can")
check(select(2, Pick.allowed(prop({ pawn = true }))):find("characters") ~= nil, "characters can't")
check(Pick.allowed(prop({ path = GAMEPLAY })) == false, "gameplay sublevels can't")
check(Pick.allowed(prop({ path = CIN })) == false, "cinematic sublevels can't")
check(Pick.allowed(prop({ interactable = true })) == false, "interactive objects can't")
check(Pick.allowed(prop({ foreign = true })) == false, "other mods' spawned meshes can't")
check(Pick.allowed(prop({ mesh_component = false })) == false, "non-mesh components can't")
check(Pick.allowed(prop({ instanced = true })) == false, "instanced meshes can't (yet)")
local wall = prop({ mesh = "/Game/Game/Environments/Strategy/HQ/Structure/Walls/SM_Wall_A.SM_Wall_A" })
check(Pick.allowed(wall) == false, "walls are locked")
wall.unlocked = true
check(Pick.allowed(wall) == true, "and editable once unlocked")
check(Pick.allowed(prop({ size = 1500 })) == false, "anything huge counts as structure")
check(Pick.unit(true, true) == "actor" and Pick.unit(true, false) == "component" and Pick.unit(false, true) == "component",
    "whole actor only for a StaticMeshActor's own mesh")
check(Pick.label("/Game/X/SM_Hub_Pit_ConferenceChair_01.SM_Hub_Pit_ConferenceChair_01", BAR) == "Hub Pit ConferenceChair 01  (Bar A)",
    "labels read well: " .. Pick.label("/Game/X/SM_Hub_Pit_ConferenceChair_01.SM_Hub_Pit_ConferenceChair_01", BAR))

print(string.format("editor_test: %d checks, %d failures", checks, failures))
os.exit(failures == 0 and 0 or 1)
