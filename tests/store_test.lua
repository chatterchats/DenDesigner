-- Offline tests for json.lua, layout.lua and store.lua (LuaJIT, no game). Usage: luajit tests/store_test.lua src/ZComDen
local src = assert(arg[1], "usage: store_test.lua <mod dir>")
package.path = src .. "/Scripts/?.lua;" .. package.path
local json, Layout, Store = require("json"), require("layout"), require("store")

local failures, checks = 0, 0
local function check(cond, what)
    checks = checks + 1
    if not cond then failures = failures + 1; print("FAIL: " .. what) end
end

-- json
local doc = { format = 1, placed = json.array({ { id = "p0001", mesh = "/Game/A/SM_A.SM_A", t = json.array({ 1.23456, -2, 3e3 }) } }),
              vanilla = {}, note = 'quote " slash \\ tab \t nl \n' }
local text = json.encode(doc)
local back = assert(json.decode(text))
check(back.placed[1].t[1] == 1.235 and back.placed[1].t[3] == 3000, "numbers round to 3 decimals")
check(back.note == doc.note, "string escapes round-trip")
check(json.encode(back) == text, "encode is stable")
check(json.encode({ placed = json.array() }):find('"placed": %[%]') ~= nil, "empty marked array stays []")
check(json.encode({}):match("^{}") ~= nil, "empty table is {}")
check(text:find('"t": %[1.235, %-2, 3000%]') ~= nil, "short numeric arrays stay on one line")
local bad, err = json.decode('{\n "a": 1,\n "b": [1, 2,,]\n}')
check(bad == nil and err:match("^line 3:") ~= nil, "decode errors name the line (" .. tostring(err) .. ")")
check(json.decode('"\\u00e9"') == "\195\169", "\\u escapes decode to UTF-8")
check(json.decode("[1, 2] x") == nil, "trailing data is an error")

-- layout validation
local raw = {
    format = 1,
    placed = {
        { id = "p0001", mesh = "/Game/A/SM_A.SM_A", t = { 0, 0, 0 } },
        { id = "p0001", mesh = "/Game/A/SM_A.SM_A", t = { 1, 1, 1 } },
        { id = "p0002", mesh = "SM_A", t = { 0, 0, 0 } },
        { id = "p0003", mesh = "/Game/A/SM_A.SM_A", t = { 0, 0 } },
        { id = "p0004", mesh = "/Game/A/SM_A.SM_A", t = { 0, 0, 0 }, s = { 1, 0, 1 } },
        42,
    },
    vanilla = {
        ["/Game/Maps/HUB_Bar_A.HUB_Bar_A:PersistentLevel.Thing_1"] = { hidden = true },
        ["/Game/Maps/HUB_Bar_A.HUB_Bar_A:PersistentLevel.Thing_2"] = { t = { 1, 2, 3 }, fp = { mesh = "/Game/A/SM_B.SM_B", at = { 1, 2, 3 } } },
        ["/Game/Maps/HUB_Bar_A.HUB_Bar_A:PersistentLevel.Thing_3"] = {},
        ["Thing_4"] = { hidden = true },
    },
}
local layout, problems = Layout.normalise(raw)
check(#layout.placed == 1 and layout.placed[1].id == "p0001", "only the valid placed entry survives")
check(layout.placed[1].s[1] == 1 and layout.placed[1].r[2] == 0, "defaults for r and s")
check(#problems == 7, "each bad entry is reported (" .. #problems .. ")")
local c = Layout.counts(layout)
check(c.vanilla == 2 and c.hidden == 1 and c.moved == 1, "vanilla counts")
check(Layout.next_id(layout) == "p0002", "next id")
check(Layout.matches(Layout.fingerprint("/Game/A/SM_B.SM_B", { X = 1.4, Y = 2, Z = 3 }), "/Game/A/SM_B.SM_B", { X = 2.9, Y = 2, Z = 3 }),
    "fingerprints match within 2 cm")
check(not Layout.matches(layout.vanilla["/Game/Maps/HUB_Bar_A.HUB_Bar_A:PersistentLevel.Thing_2"].fp, "/Game/A/SM_B.SM_B", { X = 9, Y = 2, Z = 3 }),
    "fingerprints reject a distant object")
local _, newer = Layout.normalise({ format = 9 })
check(#newer == 1 and newer[1]:find("newer") ~= nil, "a newer format is reported")

-- store, on a temporary folder
local base = os.tmpname(); os.remove(base)
local function mkdir(folders)
    for _, f in ipairs(folders) do os.execute("mkdir -p '" .. f .. "'") end
    return true
end
local store = Store.new({ base = base, sep = "/", mkdir = mkdir })
local empty, info = store:load("home")
check(info.source == "none" and #empty.placed == 0, "no file: empty layout")
check(select(1, store:resolve("ABC")) == "home", "campaign without a file uses home")

local l1 = Layout.empty()
l1.placed[1] = { id = "p0001", mesh = "/Game/A/SM_A.SM_A", t = json.array({ 1, 2, 3 }), r = json.array({ 0, 90, 0 }), s = json.array({ 1, 1, 1 }) }
check(store:save("home", nil, l1), "save home")
local loaded = store:load("home")
check(#loaded.placed == 1 and loaded.placed[1].r[2] == 90, "home round-trips")
for i = 2, 8 do
    l1.placed[1].t[1] = i
    assert(store:save("home", nil, l1))
end
check(store.read(base .. "/backups/home.1.json"):find('"t": %[7, 2, 3%]') ~= nil, "backup 1 is the previous version")
check(store.read(base .. "/backups/home.5.json") ~= nil and store.read(base .. "/backups/home.6.json") == nil, "five backups kept")
check(store:save("home", nil, l1) and store.read(base .. "/backups/home.1.json"):find('"t": %[7, 2, 3%]') ~= nil,
    "saving an unchanged layout doesn't rotate backups")

local f = io.open(base .. "/home.json", "wb"); f:write("{ broken"); f:close()
local recovered, rinfo = store:load("home")
check(rinfo.source == "backup 1" and recovered.placed[1].t[1] == 7, "corrupt file falls back to backup 1 (" .. rinfo.source .. ")")
check(store.read(base .. "/home.json") == "{ broken", "the corrupt file is left alone on load")
assert(store:save("home", nil, recovered))
local corrupt = io.popen("ls '" .. base .. "/backups' | grep -c corrupt"):read("*l")
check(corrupt == "1", "saving over a corrupt file keeps it as .corrupt")
check(store.read(base .. "/backups/home.1.json"):find('"t": %[7, 2, 3%]') ~= nil, "a corrupt file doesn't push out good backups")

os.remove(base .. "/home.json")
local tf = io.open(base .. "/home.json.tmp", "wb"); tf:write(json.encode(l1)); tf:close()
local _, tinfo = store:load("home")
check(tinfo.source == "recovered", "a .tmp left by a crash is recovered")

assert(store:save("campaign", "BA3302BC", l1))
check(select(1, store:resolve("BA3302BC")) == "campaign", "a campaign file makes the campaign use its own layout")
check(store.read(base .. "/campaigns/BA3302BC.json") ~= nil, "campaign layouts live in campaigns/")

os.execute("rm -rf '" .. base .. "'")
print(string.format("store_test: %d checks, %d failures", checks, failures))
os.exit(failures == 0 and 0 or 1)
