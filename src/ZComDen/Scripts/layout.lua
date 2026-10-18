-- Den Designer: the layout document. Pure Lua (no Unreal), so tests cover it fully.
--
--   { "format": 1,
--     "placed":  [ { "id": "p0001", "mesh": "/Game/.../SM_X.SM_X", "t": [x, y, z], "r": [pitch, yaw, roll],
--                    "s": [x, y, z], "solid": true, "mats": ["<material path>" or "" per slot],
--                    "from": "<vanilla key it was duplicated from>" } ],
--     "vanilla": { "<object path>": { "hidden": true } |
--                                   { "t": [..], "r": [..], "s": [..], "fp": { "mesh": "..", "at": [x, y, z] } } } }
--
-- Vanilla keys are full object paths (an actor or a component), which Unreal resolves directly. "fp" (mesh plus
-- location rounded to 1 cm) re-finds an object whose name changed in a game patch.
local json = require("json")
local M = {}

M.FORMAT = 1

function M.empty()
    return { format = M.FORMAT, placed = json.array(), vanilla = {} }
end

local function is_asset_path(s)
    return type(s) == "string" and s:match("^/[%w_]+/[^%.]+%.[%w_%-]+$") ~= nil
end

local function is_object_path(s)
    return type(s) == "string" and s:sub(1, 1) == "/" and s:find(":", 1, true) ~= nil
end

local function vec3(v)
    if type(v) ~= "table" or #v ~= 3 then return nil end
    for i = 1, 3 do
        if type(v[i]) ~= "number" or v[i] ~= v[i] or math.abs(v[i]) > 1e7 then return nil end
    end
    return json.array({ v[1], v[2], v[3] })
end

local function round(n) return math.floor(n + 0.5) end

-- Per-slot material overrides: an asset path, or "" to keep the mesh's own material. Bad slots become "".
local function materials(list, where, problems)
    if list == nil then return nil end
    if type(list) ~= "table" then
        problems[#problems + 1] = where .. ": mats must be a list of material paths"
        return nil
    end
    local out = json.array()
    for i, m in ipairs(list) do
        if m ~= "" and not is_asset_path(m) then
            problems[#problems + 1] = string.format("%s: mats[%d] is not a material path", where, i)
            m = ""
        end
        out[i] = m
    end
    return #out > 0 and out or nil
end

-- Validates a decoded document: returns a clean layout plus a list of problems. A bad entry is dropped and
-- reported, never guessed at.
function M.normalise(doc)
    local problems = {}
    local out = M.empty()
    if type(doc) ~= "table" then
        problems[#problems + 1] = "the layout is not a JSON object"
        return out, problems
    end
    if type(doc.format) == "number" and doc.format > M.FORMAT then
        problems[#problems + 1] = string.format("written by a newer Den Designer (format %s); loading what this version understands",
            tostring(doc.format))
    end
    if type(doc.game) == "string" then out.game = doc.game end

    local ids = {}
    for index, e in ipairs(type(doc.placed) == "table" and doc.placed or {}) do
        local where = string.format("placed #%d", index)
        local t, r, s
        if type(e) == "table" then
            t, r, s = vec3(e.t), e.r == nil and json.array({ 0, 0, 0 }) or vec3(e.r), e.s == nil and json.array({ 1, 1, 1 }) or vec3(e.s)
        end
        if type(e) ~= "table" then problems[#problems + 1] = where .. ": not an object"
        elseif type(e.id) ~= "string" or e.id == "" then problems[#problems + 1] = where .. ": missing id"
        elseif ids[e.id] then problems[#problems + 1] = where .. ": duplicate id " .. e.id
        elseif not is_asset_path(e.mesh) then problems[#problems + 1] = where .. " (" .. e.id .. "): mesh must be an asset path like /Game/Dir/SM_X.SM_X"
        elseif not t then problems[#problems + 1] = where .. " (" .. e.id .. "): t must be [x, y, z]"
        elseif not r then problems[#problems + 1] = where .. " (" .. e.id .. "): r must be [pitch, yaw, roll]"
        elseif not s or s[1] <= 0 or s[2] <= 0 or s[3] <= 0 then problems[#problems + 1] = where .. " (" .. e.id .. "): s must be three positive numbers"
        else
            ids[e.id] = true
            out.placed[#out.placed + 1] = { id = e.id, mesh = e.mesh, t = t, r = r, s = s,
                solid = type(e.solid) == "boolean" and e.solid or nil,
                mats = materials(e.mats, where .. " (" .. e.id .. ")", problems),
                from = type(e.from) == "string" and e.from or nil }
        end
    end

    for key, e in pairs(type(doc.vanilla) == "table" and doc.vanilla or {}) do
        local where = "vanilla " .. tostring(key)
        if not is_object_path(key) then problems[#problems + 1] = where .. ": key must be an object path"
        elseif type(e) ~= "table" then problems[#problems + 1] = where .. ": not an object"
        else
            local edit = { hidden = e.hidden == true or nil }
            local bad = false
            for _, field in ipairs({ "t", "r", "s" }) do
                if e[field] ~= nil then
                    edit[field] = vec3(e[field])
                    if not edit[field] then problems[#problems + 1] = where .. ": " .. field .. " must be three numbers"; bad = true end
                end
            end
            if edit.s and (edit.s[1] <= 0 or edit.s[2] <= 0 or edit.s[3] <= 0) then
                problems[#problems + 1] = where .. ": s must be positive"; bad = true
            end
            if type(e.fp) == "table" and is_asset_path(e.fp.mesh) and vec3(e.fp.at) then
                edit.fp = { mesh = e.fp.mesh, at = vec3(e.fp.at) }
            end
            if not bad and not edit.hidden and not edit.t and not edit.r and not edit.s then
                problems[#problems + 1] = where .. ": nothing to do (needs hidden, t, r or s)"; bad = true
            end
            if not bad then out.vanilla[key] = edit end
        end
    end
    return out, problems
end

function M.next_id(layout)
    local highest = 0
    for _, e in ipairs(layout.placed) do
        local n = tonumber(e.id:match("^p(%d+)$"))
        if n and n > highest then highest = n end
    end
    return string.format("p%04d", highest + 1)
end

function M.fingerprint(mesh_path, location)
    return { mesh = mesh_path, at = json.array({ round(location.X), round(location.Y), round(location.Z) }) }
end

-- True when a component's mesh and location match a fingerprint (within 2 cm).
function M.matches(fp, mesh_path, location)
    if not fp or fp.mesh ~= mesh_path then return false end
    return math.abs(fp.at[1] - location.X) <= 2 and math.abs(fp.at[2] - location.Y) <= 2
        and math.abs(fp.at[3] - location.Z) <= 2
end

-- A deep copy that keeps json.array markers.
function M.copy(value)
    if type(value) ~= "table" then return value end
    local out = {}
    for k, v in pairs(value) do out[k] = M.copy(v) end
    return setmetatable(out, getmetatable(value))
end

function M.counts(layout)
    local hidden, moved, vanilla = 0, 0, 0
    for _, e in pairs(layout.vanilla) do
        vanilla = vanilla + 1
        if e.hidden then hidden = hidden + 1 end
        if e.t or e.r or e.s then moved = moved + 1 end
    end
    return { placed = #layout.placed, vanilla = vanilla, hidden = hidden, moved = moved }
end

return M
