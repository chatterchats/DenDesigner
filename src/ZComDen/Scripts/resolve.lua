-- Den Designer: finds the Den's own objects by full path, in bulk.
-- StaticFindObject is too slow for this in ZC's UE4SS 3.0.1 (measured 2026-10-17): about 16 ms the first time a
-- path is looked up and 25 ms for a path that doesn't exist (repeats of a found path are free). One
-- FindAllOf("Actor") plus a name match costs about 75 ms for the Den's 25k actors, whatever the layout's size.
-- World.Levels (3 ms) says which sublevels have streamed in, so missing objects cost nothing to detect.
local M = {}

-- "<level>:PersistentLevel.<actor>[.<component>]" -> level path, actor name, component name or nil.
function M.split(key)
    local level, rest = key:match("^(.-:PersistentLevel)%.(.+)$")
    if not level then return nil end
    local actor, component = rest:match("^([^%.]+)%.?(.*)$")
    return level, actor, component ~= "" and component or nil
end

function M.new(g)
    local r = {}

    -- Level paths currently in the world.
    function r.loaded_levels(context)
        local loaded = {}
        local world = context and (g.call(context, "GetWorld"))
        local levels = world and world.Levels
        if not levels then return loaded end
        for i = 1, #levels do
            local level = levels[i]
            if g.valid(level) then loaded[g.path(level)] = true end
        end
        return loaded
    end

    -- Resolves keys whose level is loaded. Returns found { key = object }, missing { keys } (level loaded,
    -- object absent) and waiting { keys } (level not loaded yet).
    function r.find(keys, context)
        local loaded = r.loaded_levels(context)
        local found, missing, waiting = {}, {}, {}
        local by_actor = {}
        for _, key in ipairs(keys) do
            local level, actor = M.split(key)
            if not level then missing[#missing + 1] = key
            elseif not loaded[level] then waiting[#waiting + 1] = key
            else
                by_actor[actor] = by_actor[actor] or {}
                local list = by_actor[actor]
                list[#list + 1] = key
            end
        end
        if next(by_actor) ~= nil then
            local component_class = StaticFindObject("/Script/Engine.ActorComponent")
            for _, actor in ipairs(FindAllOf("Actor") or {}) do
                local wanted = by_actor[g.name(actor)]
                if wanted then
                    local actor_path = g.path(actor)
                    for _, key in ipairs(wanted) do
                        local level, name, component = M.split(key)
                        if actor_path == level .. "." .. name then
                            if not component then
                                found[key] = actor
                            else
                                local components = (g.call(actor, "K2_GetComponentsByClass", component_class)) or {}
                                for i = 1, #components do
                                    -- The returned table holds wrapped values: unwrap before calling methods.
                                    local c = g.unwrap(components[i])
                                    if g.valid(c) and g.name(c) == component then found[key] = c; break end
                                end
                            end
                        end
                    end
                end
            end
            for _, list in pairs(by_actor) do
                for _, key in ipairs(list) do
                    if not found[key] then missing[#missing + 1] = key end
                end
            end
        end
        return found, missing, waiting
    end

    return r
end

return M
