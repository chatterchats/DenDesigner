-- Den Designer: layout files under %LOCALAPPDATA%\SWZeroCompany\Saved\ZComDen. Never the game's own saves.
--
--   home.json                   the shared layout, used by every campaign without its own
--   campaigns\<campaign>.json   a campaign's own layout (its existence is the switch)
--   presets\<name>.json         named snapshots
--   backups\<name>.<1-5>.json   the five previous versions of home.json / campaign-<id>.json, newest first
--   presets\index.json          the preset names (plain Lua can't list a folder)
--   <layout>.draft.json          the editor's unsaved session, written as you edit and removed on save/discard
--
-- Writes go to <file>.tmp, then replace the file (a .tmp left by a crash is recovered on load). Pure Lua io:
-- tests run it on a temporary folder.
local json = require("json")
local Layout = require("layout")
local M = {}

M.BACKUPS = 5

-- options: base (folder, no trailing separator), sep, log, mkdir(list of folders) -> ok
function M.new(options)
    local base, sep = options.base, options.sep or "\\"
    local log = options.log or function() end
    local mkdir = options.mkdir or function() return true end
    local self = { base = base }

    local function join(...) return table.concat({ ... }, sep) end

    local function read(path)
        local f = io.open(path, "rb")
        if not f then return nil end
        local text = f:read("*a")
        f:close()
        return text
    end
    self.read = read

    local function write(path, text)
        local f, err = io.open(path, "wb")
        if not f then return false, err end
        local ok, werr = f:write(text)
        f:close()
        if not ok then return false, werr end
        return true
    end

    function self:folders()
        return { base, join(base, "campaigns"), join(base, "presets"), join(base, "backups") }
    end

    function self:file(scope, campaign)
        if scope == "campaign" then return join(base, "campaigns", campaign .. ".json") end
        return join(base, "home.json")
    end

    local function backup_name(scope, campaign)
        return scope == "campaign" and ("campaign-" .. campaign) or "home"
    end

    local function backup(scope, campaign, n)
        return join(base, "backups", backup_name(scope, campaign) .. "." .. n .. ".json")
    end

    function self:has_campaign(campaign)
        return campaign ~= nil and read(self:file("campaign", campaign)) ~= nil
    end

    -- Which layout a campaign uses: its own file when one exists, else home.
    function self:resolve(campaign)
        if self:has_campaign(campaign) then return "campaign", self:file("campaign", campaign) end
        return "home", self:file("home")
    end

    -- Returns layout, info { scope, path, source = file|recovered|backup N|none, text, problems }.
    function self:load(scope, campaign)
        local path = self:file(scope, campaign)
        local info = { scope = scope, path = path, problems = {} }
        local text = read(path)
        info.source = "file"
        if not text then
            text = read(path .. ".tmp")
            info.source = text and "recovered" or "none"
        end
        if not text then return Layout.empty(), info end
        info.text = text
        local doc, err = json.decode(text)
        if doc == nil then
            info.problems[#info.problems + 1] = string.format("%s is not valid JSON (%s)", path, tostring(err))
            info.source = "none"
            for n = 1, M.BACKUPS do
                local older = read(backup(scope, campaign, n))
                local older_doc = older and json.decode(older)
                if older_doc then
                    doc, info.source = older_doc, "backup " .. n
                    info.problems[#info.problems + 1] = "loaded backup " .. n .. " instead; the broken file is left as it is"
                    break
                end
            end
            if doc == nil then return Layout.empty(), info end
        end
        local layout, problems = Layout.normalise(doc)
        for _, p in ipairs(problems) do info.problems[#info.problems + 1] = p end
        return layout, info
    end

    -- Saves a layout; the replaced version moves into backups (a broken one is kept as .corrupt instead).
    function self:save(scope, campaign, layout)
        if not mkdir(self:folders()) then return false, "can't create " .. base end
        local path = self:file(scope, campaign)
        local text = json.encode(layout)
        local current = read(path)
        if current == text then return true end
        if current then
            if json.decode(current) ~= nil then
                for n = M.BACKUPS, 2, -1 do
                    os.remove(backup(scope, campaign, n))
                    os.rename(backup(scope, campaign, n - 1), backup(scope, campaign, n))
                end
                local ok, err = write(backup(scope, campaign, 1), current)
                if not ok then log("WARNING: backup of %s failed | %s", path, tostring(err)) end
            else
                write(join(base, "backups", backup_name(scope, campaign) .. ".corrupt-" .. os.time() .. ".json"), current)
            end
        end
        local ok, err = write(path .. ".tmp", text)
        if not ok then return false, err end
        os.remove(path)
        local renamed, rerr = os.rename(path .. ".tmp", path)
        if not renamed then return false, rerr end
        return true
    end

    local function write_atomic(path, text)
        local ok, err = write(path .. ".tmp", text)
        if not ok then return false, err end
        os.remove(path)
        local renamed, rerr = os.rename(path .. ".tmp", path)
        if not renamed then return false, rerr end
        return true
    end

    -- Presets -------------------------------------------------------------------------------------------

    -- A name safe for a file: letters, digits, spaces, - and _; at most 40 characters.
    function M.preset_name(name)
        name = tostring(name or ""):gsub("[^%w _%-]", ""):gsub("^%s+", ""):gsub("%s+$", ""):gsub("%s+", " ")
        return name:sub(1, 40)
    end

    local function preset_file(name) return join(base, "presets", name .. ".json") end
    local function index_file() return join(base, "presets", "index.json") end

    local function write_index(names)
        table.sort(names, function(a, b) return a:lower() < b:lower() end)
        return write_atomic(index_file(), json.encode({ presets = json.array(names) }))
    end

    -- The saved presets' names, sorted (index entries whose file is gone are dropped).
    function self:presets()
        local doc = json.decode(read(index_file()) or "") or {}
        local names = {}
        for _, name in ipairs(type(doc.presets) == "table" and doc.presets or {}) do
            if type(name) == "string" and read(preset_file(name)) then names[#names + 1] = name end
        end
        table.sort(names, function(a, b) return a:lower() < b:lower() end)
        return names
    end

    -- Saves (or overwrites) a preset; returns ok, err, the name it was saved under.
    function self:save_preset(name, layout)
        name = M.preset_name(name)
        if name == "" then return false, "the name needs letters or digits" end
        if not mkdir(self:folders()) then return false, "can't create " .. base end
        local ok, err = write_atomic(preset_file(name), json.encode(layout))
        if not ok then return false, err end
        local names = self:presets()
        local known = false
        for _, n in ipairs(names) do if n == name then known = true end end
        if not known then names[#names + 1] = name end
        write_index(names)
        return true, nil, name
    end

    -- Returns layout, problems; or nil when there's no such preset.
    function self:load_preset(name)
        local text = read(preset_file(M.preset_name(name)))
        if not text then return nil, { "no preset called " .. tostring(name) } end
        local doc, err = json.decode(text)
        if doc == nil then return nil, { "the preset is not valid JSON (" .. tostring(err) .. ")" } end
        return Layout.normalise(doc)
    end

    function self:delete_preset(name)
        name = M.preset_name(name)
        os.remove(preset_file(name))
        local names = {}
        for _, n in ipairs(self:presets()) do if n ~= name then names[#names + 1] = n end end
        return write_index(names)
    end

    -- A campaign's own layout -----------------------------------------------------------------------------

    function self:make_campaign(campaign, layout)
        if not campaign then return false, "unknown campaign" end
        return self:save("campaign", campaign, layout)
    end

    -- Back to the home layout: the campaign's file goes, a copy stays in backups.
    function self:drop_campaign(campaign)
        if not campaign then return false, "unknown campaign" end
        local path = self:file("campaign", campaign)
        local text = read(path)
        if text then
            write(join(base, "backups", "campaign-" .. campaign .. ".dropped-" .. os.time() .. ".json"), text)
        end
        os.remove(path .. ".tmp")
        os.remove(path)
        return read(path) == nil
    end

    -- Drafts (the editor's unsaved session) -----------------------------------------------------------------

    function self:draft_file(scope, campaign)
        return (self:file(scope, campaign):gsub("%.json$", ".draft.json"))
    end

    function self:save_draft(scope, campaign, layout)
        if not mkdir(self:folders()) then return false, "can't create " .. base end
        local doc = Layout.copy(layout)
        doc.draft_at = os.date("%Y-%m-%d %H:%M")
        return write_atomic(self:draft_file(scope, campaign), json.encode(doc))
    end

    -- Returns layout, when it was written (text), problems; or nil when there's no draft.
    function self:load_draft(scope, campaign)
        local text = read(self:draft_file(scope, campaign))
        local doc = text and json.decode(text)
        if type(doc) ~= "table" then return nil end
        local layout, problems = Layout.normalise(doc)
        return layout, type(doc.draft_at) == "string" and doc.draft_at or "earlier", problems
    end

    function self:clear_draft(scope, campaign)
        local path = self:draft_file(scope, campaign)
        os.remove(path .. ".tmp")
        os.remove(path)
    end

    return self
end

return M
