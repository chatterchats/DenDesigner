-- Den Designer: what the editor lets you pick. Pure Lua rules over facts the editor reads from the hit object,
-- so tests cover them fully.
--
-- Off limits: characters, interactive objects, anything in a gameplay, story, cinematic, lighting or audio
-- sublevel (the game drives those), meshes other mods spawned, and instanced meshes (not yet). The Den's
-- structure (walls, floors, girders, ceilings, the dropship) is locked unless the player unlocks it.
local M = {}

M.STRUCTURE_SIZE = 800  -- cm: anything wider than this counts as structure

-- Lua patterns on the level path (the part before ":PersistentLevel").
M.SCRIPTED_LEVELS = { "_Gameplay%.", "_Cinematics%.", "/CIN_", "Narrative", "/Audio/", "_Audio%.",
                      "Lighting", "/LGT_", "SpaceTravel", "Hyperspace" }

-- Lua patterns on the mesh path.
M.STRUCTURE_MESHES = { "/HQ/Structure/Girder/", "/HQ/Structure/Walls/", "/HQ/Structure/Floors/", "/HQ/Structure/Ceilings/",
                       "/HQ/Structure/Pipes/", "/HQ/Structure/Supports/", "/HQ/Structure/_GENERATED/",
                       "/SWAL_Fixtures/Floor", "/SWAL_Fixtures/Wall", "/SWAL_Fixtures/Ceiling", "/Vehicles/Dropship/",
                       "/Structures/DocksUnderground/" }

local function any(s, patterns)
    if type(s) ~= "string" then return false end
    for _, p in ipairs(patterns) do if s:find(p) then return true end end
    return false
end

function M.level_of(path)
    return type(path) == "string" and path:match("^(.-):PersistentLevel") or nil
end

-- facts: { path (the component's full path), placed (one of ours), pawn, interactable, foreign (another mod's
-- spawned actor), mesh_component, instanced, mesh (asset path), size (cm, largest bounds side), unlocked }.
-- Returns true, or false plus a reason for the player.
function M.allowed(facts)
    if facts.placed then return true end
    if facts.pawn then return false, "characters can't be edited" end
    if facts.foreign then return false, "another mod added this; edit it there" end
    if any(M.level_of(facts.path), M.SCRIPTED_LEVELS) then return false, "the game uses this for its story or gameplay" end
    if facts.interactable then return false, "interactive objects can't be edited" end
    if not facts.mesh_component then return false, "only props (static meshes) can be edited" end
    if facts.instanced then return false, "instanced meshes can't be edited yet" end
    if not facts.unlocked and (any(facts.mesh, M.STRUCTURE_MESHES) or (facts.size or 0) > M.STRUCTURE_SIZE) then
        return false, "the Den's structure is locked (unlock it in the toolbar)"
    end
    return true
end

-- The whole actor when the mesh is a StaticMeshActor's own mesh, else just the component.
function M.unit(static_mesh_actor, is_root)
    return (static_mesh_actor and is_root) and "actor" or "component"
end

-- A readable name: the mesh's asset name without its SM_ prefix, plus where it is.
function M.label(mesh, path)
    local name = type(mesh) == "string" and mesh:match("([^/%.]+)$") or nil
    name = name and name:gsub("^SM_", ""):gsub("_", " ") or "?"
    local level = M.level_of(path)
    local where = level and level:match("([^/%.]+)$") or nil
    where = where and where:gsub("^HUB_", ""):gsub("^LI_", ""):gsub("_LevelInstance.*$", ""):gsub("_", " ") or nil
    return where and (name .. "  (" .. where .. ")") or name
end

return M
