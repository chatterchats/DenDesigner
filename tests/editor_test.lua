-- Offline tests for history.lua and pick.lua (LuaJIT, no game). Usage: luajit tests/editor_test.lua src/ZComDen
local src = assert(arg[1], "usage: editor_test.lua <mod dir>")
package.path = src .. "/Scripts/?.lua;" .. package.path
local json, Layout, History, Pick, Catalog = require("json"), require("layout"), require("history"), require("pick"), require("catalog")
local Thumbs = require("thumbs")
local Keys = require("keys")

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

-- catalog ----------------------------------------------------------------------------------------------------
local data = require("catalog_data")
local t0 = os.clock()
local cat = Catalog.new(data)
check(cat.count > 4000 and #data.items % Catalog.STRIDE == 0, "the generated catalog loads (" .. cat.count .. " meshes)")
check(os.clock() - t0 < 0.5, "and indexes quickly")
local total = 0
for _, shelf in ipairs(cat.shelves) do
    local items = cat:shelf_items(shelf.key)
    total = total + #items
    for _, i in ipairs(items) do
        if cat:item(i).shelf ~= tonumber(shelf.key) then check(false, "item " .. i .. " is on shelf " .. shelf.title); break end
    end
end
check(total == cat.count, "every mesh is on exactly one shelf")
local bad = 0
for i = 1, cat.count do
    local item = cat:item(i)
    if not item.path:match("^/[%w_]+/[^%.]+%.[%w_%-]+$") or item.size[1] < 0 then bad = bad + 1 end
end
check(bad == 0, "every path is a loadable object path (" .. bad .. " bad)")
local cauldron = "/Game/Game/Environments/Faction/Universal/Props/Wares/UNI_Wares_Cauldron_Rogue_A/SM_UNI_Wares_Cauldron_Rogue_A.SM_UNI_Wares_Cauldron_Rogue_A"
check(cat:find(cauldron) ~= nil, "the cauldron from Phase 0 is in it")
local found, n = cat:search("cauldron rogue")
check(n >= 1 and cat:item(found[1]).path:find("Cauldron", 1, true) ~= nil, "search matches every word")
local _, crates = cat:search("crate")
check(crates > 10, "a broad search finds many (" .. crates .. ")")
local many = select(2, cat:search("a"))
check(#cat:search("a") == Catalog.SEARCH_LIMIT and many > Catalog.SEARCH_LIMIT, "results are capped, the total isn't")
check(#cat:search("   ") == 0, "a blank search finds nothing")
cat:remember(cauldron); cat:remember("/Game/X/SM_Y.SM_Y"); cat:remember(cauldron)
check(cat.recent[1] == cauldron and #cat.recent == 2, "recent keeps the latest first, once")
check(#cat:shelf_items("recent") == 1, "recent shows only meshes the catalog knows")
check(Catalog.name_of(cauldron) == "Wares Cauldron Rogue A", "names read well: " .. Catalog.name_of(cauldron))
check(Catalog.size_text({ 72, 71, 40 }) == "72 x 71 x 40 cm" and Catalog.size_text({ 450, 120, 300 }) == "4.5 x 1.2 x 3.0 m", "sizes read well")
local slow = os.clock()
for _ = 1, 10 do cat:search("chair") end
check((os.clock() - slow) / 10 < 0.02, string.format("a search takes under 20 ms (%.1f ms)", (os.clock() - slow) * 100))

-- thumbnails ----------------------------------------------------------------------------------------------
local cube = Thumbs.distance({ 50, 50, 50 }, Thumbs.VIEW, Thumbs.FOV)
local rug = Thumbs.distance({ 100, 70, 1 }, Thumbs.VIEW, Thumbs.FOV)
local pole = Thumbs.distance({ 5, 5, 150 }, Thumbs.VIEW, Thumbs.FOV)
local function sphere_fit(e) return math.sqrt(e[1] ^ 2 + e[2] ^ 2 + e[3] ^ 2) / math.sin(math.rad(Thumbs.FOV / 2)) end
check(cube > 50 and rug > 100 and pole > 150, "the camera stands outside the box")
check(rug <= sphere_fit({ 100, 70, 1 }) * Thumbs.MARGIN and pole <= sphere_fit({ 5, 5, 150 }) * Thumbs.MARGIN,
    "never farther than a bounding-sphere fit (plus the margin)")
check(Thumbs.distance({ 10, 10, 10 }, Thumbs.VIEW, Thumbs.FOV) * 10 - Thumbs.distance({ 100, 100, 100 }, Thumbs.VIEW, Thumbs.FOV) < 1e-6,
    "framing scales with size")
local a, b = Thumbs.file_name(cauldron), Thumbs.file_name(cauldron:gsub("Rogue", "Rogui"))
check(a:match("^SM_UNI_Wares_Cauldron_Rogue_A_%x%x%x%x%x%x%x%x%.png$") ~= nil, "picture files are named readably: " .. a)
check(a ~= b and Thumbs.file_name(cauldron) == a, "and stably, unique per path")

-- keys -----------------------------------------------------------------------------------------------------
check(Keys.key_name(0x51) == "Q" and Keys.key_name(0x35) == "Five" and Keys.key_name(0x63) == "NumPadThree"
    and Keys.key_name(0x7B) == "F12" and Keys.key_name(0xA2) == "LeftControl" and Keys.key_name(0x07) == nil,
    "virtual-key codes become Unreal key names")
local function plan(values) return Keys.plan(function(k) return values[k] end) end
local names = plan({})
check(names.key_forward == "W" and names.key_down == "LeftControl" and names.key_catalog == "Tab", "no settings: the shipped keys")
names = plan({ key_forward = 0x5A, key_undo = 0x55 })  -- AZERTY-style: forward on Z, undo moves to U
check(names.key_forward == "Z" and names.key_undo == "U", "rebinding works")
local clash, problems = plan({ key_forward = 0x5A })     -- Z is undo's key
check(clash.key_forward == "W" and clash.key_undo == "Z" and #problems == 1, "a key that's taken keeps the shipped one")
local reserved, why = plan({ key_store = 0x1B })         -- Escape
check(reserved.key_store == "X" and why[1]:find("can't be used") ~= nil, "reserved keys are refused")
local settings_doc = dofile(src .. "/MXM/settings.lua")
local listed = {}
for _, e in ipairs(settings_doc.settings) do if e.key then listed[e.key] = e end end
local missing = 0
for _, b in ipairs(Keys.BINDINGS) do if not (listed[b[1]] and listed[b[1]].default == b[4]) then missing = missing + 1 end end
check(missing == 0 and settings_doc.id == "ZComDenDesigner", "every binding is in the MXM settings with its shipped key")

-- editor.lua defines a local select(prop) for the selection: Lua's select("#", ...) after it calls that instead
-- (it once made a bogus selection on every deferred command).
local editor_src = io.open(src .. "/Scripts/editor.lua"):read("*a")
local shadow_at = editor_src:find("local function select%(")
check(shadow_at and not editor_src:find('select%("#"', shadow_at), "no select(\"#\", ...) after the local select()")

print(string.format("editor_test: %d checks, %d failures", checks, failures))
os.exit(failures == 0 and 0 or 1)
