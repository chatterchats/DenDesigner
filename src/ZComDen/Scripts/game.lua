-- Den Designer: Unreal helpers. Construct and call on the game thread only.
-- Rules from Plague Night's and this mod's probes:
-- - a Lua reference doesn't keep a UObject alive: attach what we create to a component or actor straight away;
-- - never write FText or soft-object properties; FText as a function argument is fine;
-- - an Actor spawned with no root loses its spawn transform: set the transform after adding the first component;
-- - kit and game assets load through the engine's soft loads only (UE4SS LoadAsset crashed on kit assets);
-- - match objects by full path, never by a name substring ("StaticMeshActor_1." is inside "BitReactorStaticMeshActor_1.").
local M = {}

M.IDENTITY = { Rotation = { X = 0, Y = 0, Z = 0, W = 1 }, Translation = { X = 0, Y = 0, Z = 0 },
               Scale3D = { X = 1, Y = 1, Z = 1 } }
M.MOVABLE = 2

function M.new(log)
    local g = {}

    function g.safe(name, callback)
        return function(...)
            local ok, err = pcall(callback, ...)
            if not ok then log("ERROR: %s | %s", name, tostring(err)) end
        end
    end

    function g.unwrap(value)
        if value == nil then return nil end
        local ok, inner = pcall(function() return value:get() end)
        if ok and inner ~= nil then return inner end
        return value
    end

    function g.valid(object)
        object = g.unwrap(object)
        if object == nil then return false end
        local ok, result = pcall(function() return object:IsValid() end)
        return ok and result == true
    end

    function g.name(object)
        local ok, value = pcall(function() return object:GetFName():ToString() end)
        return ok and value or "?"
    end

    function g.full_name(object)
        local ok, value = pcall(function() return object:GetFullName() end)
        return ok and value or "?"
    end

    -- "Class /Path/Obj.Obj" -> "/Path/Obj.Obj"
    function g.path(object)
        return (g.full_name(object):match(" (.*)$")) or "?"
    end

    local unpack = table.unpack or unpack
    local function pack(...) return { n = select("#", ...), ... } end

    -- Calls a method; returns its results, or nil plus the error.
    function g.call(object, method, ...)
        local args = pack(...)
        local results = pack(pcall(function() return object[method](object, unpack(args, 1, args.n)) end))
        if not results[1] then return nil, tostring(results[2]) end
        return unpack(results, 2, results.n)
    end

    local cdo_cache = {}
    function g.cdo(path)
        local cdo = cdo_cache[path]
        if cdo == nil or not g.valid(cdo) then
            cdo = StaticFindObject(path)
            cdo_cache[path] = cdo
        end
        return cdo
    end
    function g.gameplay() return g.cdo("/Script/Engine.Default__GameplayStatics") end
    function g.kismet() return g.cdo("/Script/Engine.Default__KismetSystemLibrary") end
    function g.rendering() return g.cdo("/Script/Engine.Default__KismetRenderingLibrary") end

    function g.vec(x, y, z) return { X = x, Y = y, Z = z } end
    function g.rot(pitch, yaw, roll) return { Pitch = pitch or 0, Yaw = yaw or 0, Roll = roll or 0 } end
    function g.xform(location, yaw)
        local h = math.rad(yaw or 0) / 2
        return { Rotation = { X = 0, Y = 0, Z = math.sin(h), W = math.cos(h) }, Translation = location,
                 Scale3D = { X = 1, Y = 1, Z = 1 } }
    end

    local instance_path
    local function instance()
        local found = instance_path and StaticFindObject(instance_path)
        if not g.valid(found) then
            found = FindFirstOf("BrunoGameInstance")
            instance_path = g.valid(found) and g.path(found) or nil
        end
        return g.valid(found) and found or nil
    end

    -- The game instance supplies the current world in menus, missions and the Den.
    function g.any_context()
        local gi = instance()
        if gi and g.world_name(gi) then return gi end
        local pc = FindFirstOf("PlayerController")
        return g.valid(pc) and pc or nil
    end

    function g.world_name(context)
        local world = context and (g.call(context, "GetWorld"))
        return world and g.full_name(world) or nil
    end

    -- Name plus address: a reloaded Den is a new world even though its name is the same.
    function g.world_key(context)
        local world = context and (g.call(context, "GetWorld"))
        if not world then return nil end
        return g.full_name(world) .. "@" .. tostring((g.call(world, "GetAddress")))
    end

    -- An asset by object path: already in memory, else the engine's blocking soft load. Never UE4SS LoadAsset.
    function g.load_object(path)
        local ok, found = pcall(StaticFindObject, path)
        if ok and g.valid(found) then return found end
        local k = g.kismet()
        local soft_path = (g.call(k, "MakeSoftObjectPath", path))
        local soft_ref = soft_path ~= nil and (g.call(k, "Conv_SoftObjPathToSoftObjRef", soft_path)) or nil
        local object = soft_ref ~= nil and (g.call(k, "LoadAsset_Blocking", soft_ref)) or nil
        return g.valid(object) and object or nil
    end

    function g.load_class(path)
        local ok, found = pcall(StaticFindObject, path)
        if ok and g.valid(found) then return found end
        local k = g.kismet()
        local soft_path = (g.call(k, "MakeSoftClassPath", path))
        local soft_ref = soft_path ~= nil and (g.call(k, "Conv_SoftClassPathToSoftClassRef", soft_path)) or nil
        local class = soft_ref ~= nil and (g.call(k, "LoadClassAsset_Blocking", soft_ref)) or nil
        return g.valid(class) and class or nil
    end

    -- An empty actor; its transform only sticks once a component is its root (see place_mesh).
    function g.spawn_host(context, location, yaw)
        local gs = g.gameplay()
        local xf = g.xform(location or g.vec(0, 0, 0), yaw)
        local deferred = (g.call(gs, "BeginDeferredActorSpawnFromClass", context,
            StaticFindObject("/Script/Engine.Actor"), xf, 1, nil, 1))
        if not deferred then return nil end
        local actor = (g.call(gs, "FinishSpawningActor", deferred, xf, 1))
        return g.valid(actor) and actor or nil
    end

    function g.add_component(actor, class_path)
        local class = StaticFindObject(class_path)
        local component = class and (g.call(actor, "AddComponentByClass", class, false, M.IDENTITY, false))
        return g.valid(component) and component or nil
    end

    function g.is_a(object, class_path)
        local class = StaticFindObject(class_path)
        return class ~= nil and (g.call(object, "IsA", class)) == true
    end

    function g.console(context, command)
        local _, err = g.call(g.kismet(), "ExecuteConsoleCommand", context, command, nil)
        return err
    end

    -- The campaign of the latest save, as 32 hex digits (the GUID's A..D), or nil. A brand-new campaign that
    -- hasn't saved yet still reports the previous campaign: callers treat this as a hint, not proof.
    function g.campaign_id()
        local subsystem = FindFirstOf("BrunoSaveGameSubsystem")
        if not g.valid(subsystem) then return nil end
        local info = {}
        local ok = (g.call(subsystem, "GetLatestSaveGameInfo", info))
        local id = ok and info.CampaignID
        if type(id) ~= "table" and type(id) ~= "userdata" then return nil end
        local parts = {}
        for _, key in ipairs({ "A", "B", "C", "D" }) do
            local n = tonumber(id[key])
            if not n then return nil end
            parts[#parts + 1] = string.format("%08X", math.floor(n % 4294967296))
        end
        local hex = table.concat(parts)
        return hex ~= string.rep("0", 32) and hex or nil
    end

    -- Creates a directory tree without a shell: Unreal's file writer creates missing parent folders when it
    -- exports a render target, then the export is deleted again. Needs a world context.
    function g.make_directories(context, directories)
        local r = g.rendering()
        local target = r and (g.call(r, "CreateRenderTarget2D", context, 4, 4, 2, { R = 0, G = 0, B = 0, A = 1 }, false, false))
        if not g.valid(target) then return false, "no render target" end
        local made = true
        for _, dir in ipairs(directories) do
            local probe = dir .. "\\zcomden_mkdir.png"
            local f = io.open(probe, "rb")
            if f then f:close() else
                g.call(r, "ExportRenderTarget", context, target, dir, "zcomden_mkdir.png")
                f = io.open(probe, "rb")
                if f then f:close() else made = false end
            end
            os.remove(probe)
        end
        g.call(r, "ReleaseRenderTarget2D", target)
        return made
    end

    -- Line trace on the visibility channel; returns the hit table or nil.
    function g.trace(context, from, to, complex)
        local hit = {}
        local ok, blocked = pcall(function()
            return g.kismet():LineTraceSingle(context, from, to, 0, complex == true, {}, 0, hit, true,
                { R = 1, G = 0, B = 0, A = 1 }, { R = 0, G = 1, B = 0, A = 1 }, 0)
        end)
        if not ok or not blocked or not hit.bBlockingHit then return nil end
        return hit
    end

    return g
end

return M
