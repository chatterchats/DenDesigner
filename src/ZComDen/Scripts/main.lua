-- Den Designer v0.2.0 (Phase 2: the editor; Ctrl+Home in the Den)
-- Saves to %LOCALAPPDATA%\SWZeroCompany\Saved\ZComDen, never the game's saves. Loader-thread composition only:
-- all Unreal work starts on the game thread (the final scheduled action below).
local VERSION = "0.2.0"
local source = debug.getinfo(1, "S").source:gsub("^@", "")
local directory = assert(source:match("^(.*[/\\])"), "Scripts directory unavailable")
-- Explicit path: never resolve another mod's generic module names.
package.path = directory .. "?.lua;" .. package.path
for _, module in ipairs({ "hook_registry", "actions", "logging", "game", "json", "layout", "store", "resolve", "apply", "den_watch",
                          "history", "pick", "highlight", "editor" }) do
    package.loaded[module] = nil
end
local Runtime = require("hook_registry")
local Actions = require("actions")
local Logging = require("logging")
local runtime = Runtime.start("ZComDenRuntime", { clear_all = true })
local logger = Logging.new(runtime, { tag = "[ZComDen]", file = "zcom_den.log", folder = "ZComDen" })
local actions = Actions.new(runtime, {
    valid = function(obj)
        if not obj then return false end
        local ok, result = pcall(function() return obj:IsValid() end)
        return ok and result == true
    end,
    log = function(...) logger:log(...) end,
})
logger:transition("runtime", "loading", "version=" .. VERSION)

local function data_folder()
    local base = os.getenv("LOCALAPPDATA")
    if base and base ~= "" then return base .. "\\SWZeroCompany\\Saved\\ZComDen" end
    return (directory:gsub("[/\\][Ss]cripts[/\\]$", "")) .. "\\data"
end

local function start()
    local log = function(...) logger:log(...) end
    local g = require("game").new(log)
    local base = data_folder()
    local store = require("store").new({
        base = base, sep = "\\", log = log,
        mkdir = function(folders)
            local context = g.any_context()
            return context ~= nil and g.make_directories(context, folders)
        end,
    })
    local ctx = { runtime = runtime, actions = actions, log = log, g = g, store = store, dir = directory }
    local watch = require("den_watch").new(ctx)
    watch:install()
    ctx.watch = watch
    local editor = require("editor").new(ctx)
    -- Installed after the watch: on a reload the editor closes before the Den edits are undone.
    editor:install(Key.HOME, { ModifierKey.CONTROL })
    watch.on_leave[#watch.on_leave + 1] = function(reason) editor:abort(reason) end
    logger:transition("runtime", "ready", "layouts=" .. base)
end

-- This MUST remain the final operation: all Unreal work starts on the game thread.
return actions:schedule_after("bootstrap", 0, function()
    local ok, err = pcall(start)
    if not ok then
        logger:log("ERROR: game-thread setup failed | %s", tostring(err))
        runtime:teardown("setup failed")
        error(err)
    end
end)
