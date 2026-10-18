-- Den Designer: applies the right layout whenever the Den loads, and undoes it when the Den goes away.
-- While in the Den the layout file is re-read every poll, so a hand edit (or another tool) shows up within a
-- second. The editor pauses that while it's open, and saves through the same file.
local Apply = require("apply")
local Layout = require("layout")
local M = {}

M.POLL_MS = 1000

local function in_den(world_name)
    return type(world_name) == "string" and world_name:find("/HUB_Root.HUB_Root", 1, true) ~= nil
end
M.in_den = in_den

function M.new(ctx)
    local g, log, actions, store = ctx.g, ctx.log, ctx.actions, ctx.store
    -- layout/scope: what's applied now (the editor starts from it); on_leave: called when the Den goes away.
    local self = { world = nil, campaign = nil, path = nil, text = nil, layout = nil, scope = nil, paused = false,
                   on_leave = {} }
    local apply = Apply.new(ctx)
    self.apply = apply

    local function summary(scope, info, report)
        local parts = {
            string.format("Den | %s layout (%s)", scope, info.source),
            string.format("%d placed, %d hidden, %d moved", report.placed, report.hidden, report.moved),
        }
        if report.refound > 0 then parts[#parts + 1] = report.refound .. " re-found by fingerprint" end
        if #report.dormant > 0 then parts[#parts + 1] = #report.dormant .. " dormant" end
        if #report.missing > 0 then parts[#parts + 1] = #report.missing .. " missing" end
        if report.errors > 0 then parts[#parts + 1] = report.errors .. " errors" end
        parts[#parts + 1] = string.format("%d frames, %d scans, %.0f ms work (slowest job %.0f ms: %s), %.1f s total",
            report.frames, report.scans, report.work * 1000, report.slowest * 1000, tostring(report.slowest_job), report.seconds)
        log(table.concat(parts, " | "))
        for _, d in ipairs(report.dormant) do log("Den | dormant: %s", d) end
        for _, m in ipairs(report.missing) do log("WARNING: Den | missing: %s", m) end
    end

    local function load_and_apply(world)
        local scope, path = store:resolve(self.campaign)
        local layout, info = store:load(scope, self.campaign)
        self.path, self.text, self.layout, self.scope = path, store.read(path) or "", layout, scope
        for _, problem in ipairs(info.problems) do log("WARNING: layout | %s", problem) end
        apply:begin(Layout.copy(layout), world, function(report) summary(scope, info, report) end)
    end

    -- The editor saved `layout` to the current file: it's already in the Den, so don't reapply it.
    function self:adopt(layout)
        local _, path = store:resolve(self.campaign)
        self.path, self.text, self.layout = path, store.read(path) or "", Layout.copy(layout)
    end

    -- Reapplies the file (the editor's Discard).
    function self:reload(reason)
        if not self.world then return end
        log("Den | %s; reapplying the saved layout", reason)
        load_and_apply(self.world)
    end

    function self:poll()
        local context = g.any_context()
        local name = context and g.world_name(context)
        local world = name and g.world_key(context)
        if self.world and self.world ~= world then
            -- The old Den's objects went with it: drop our references, touch nothing.
            for _, callback in ipairs(self.on_leave) do pcall(callback, "left the Den") end
            apply:forget("left the Den")
            self.world, self.path, self.text, self.layout = nil, nil, nil, nil
        end
        if not in_den(name) or not world then return end
        if not self.world then
            self.world = world
            self.campaign = g.campaign_id()
            log("Den | arrived; campaign %s", self.campaign or "unknown")
            load_and_apply(world)
            return
        end
        if self.paused then return end
        -- A changed file, or a campaign layout created or deleted since: reapply.
        local _, path = store:resolve(self.campaign)
        local text = store.read(path) or ""
        if path ~= self.path or text ~= self.text then
            log("Den | %s changed; reapplying", path)
            load_and_apply(world)
        end
    end

    function self:install()
        local prior = ctx.runtime.on_teardown
        ctx.runtime.on_teardown = function(reason)
            -- A reload can retire this runtime off the game thread: undo the Den edits on the game thread.
            ExecuteInGameThread(function() apply:clear(reason) end)
            if prior then prior(reason) end
        end
        local function watch()
            local ok, err = pcall(function() self:poll() end)
            if not ok then log("WARNING: Den watch | %s", tostring(err)) end
            actions:schedule_after("den-watch", M.POLL_MS, watch)
        end
        watch()
    end

    return self
end

return M
