-- Den Designer: applies a layout to the loaded Den, and undoes it.
-- Vanilla objects are found in bulk (resolve.lua); edits then run in frame-budgeted batches, clutter first,
-- then placed meshes. An object whose sublevel hasn't streamed in yet waits (cheap level checks, one scan when
-- the level arrives); one that never appears is reported as dormant, and the layout keeps it.
-- Objects we touch are kept for undo, and checked (valid, same world, same full path) before each use; when
-- the Den itself goes away, forget() drops them without touching them.
-- The editor changes single objects through set_vanilla / set_placed, the same code the layout load uses.
local Layout = require("layout")
local Resolve = require("resolve")
local M = {}

M.BUDGET = 0.004     -- seconds of work per frame
M.WAIT_PASSES = 8    -- level checks for objects whose sublevel isn't loaded yet
M.WAIT_MS = 1500
M.SOLID_SIZE = 50    -- cm: a placed mesh bigger than this blocks pawns unless the layout says otherwise

local ACTOR = "/Script/Engine.Actor"
local STATIC_MESH = "/Script/Engine.StaticMesh"
local MESH_COMPONENT = "/Script/Engine.StaticMeshComponent"
local MATERIAL = "/Script/Engine.MaterialInterface"
local ECC_PAWN, ECR_IGNORE, NO_COLLISION = 2, 0, 0

function M.new(ctx)
    local g, log, actions = ctx.g, ctx.log, ctx.actions
    local resolver = Resolve.new(g)
    -- edits: key -> record of a vanilla object we track; placed: id -> record of a mesh we spawned.
    local self = { epoch = 0, world = nil, placed = {}, edits = {}, report = nil, busy = false }

    local function vec(a) return g.vec(a[1], a[2], a[3]) end
    local function rot(a) return g.rot(a[1], a[2], a[3]) end
    local function copy(v) return { X = v.X, Y = v.Y, Z = v.Z } end
    local function copy_rot(r) return { Pitch = r.Pitch, Yaw = r.Yaw, Roll = r.Roll } end

    -- UE4SS's GetWorld on an actor in a streamed sublevel returns the sublevel's own UWorld, not the game world;
    -- its components report the real one. So actors are checked through their root component.
    local function in_world(object)
        local probe = object
        if g.is_a(object, ACTOR) then
            local root = (g.call(object, "K2_GetRootComponent"))
            if g.valid(root) then probe = root end
        end
        return g.world_key(probe) == self.world
    end
    local function owns(object, path)
        return g.valid(object) and in_world(object) and g.path(object) == path
    end
    function self:owns(object, path) return owns(object, path) end

    -- An actor's or a component's world transform, as plain tables.
    function self:transform(object)
        if g.is_a(object, ACTOR) then
            return copy(object:K2_GetActorLocation()), copy_rot(object:K2_GetActorRotation()), copy(object:GetActorScale3D())
        end
        return copy(object:K2_GetComponentLocation()), copy_rot(object:K2_GetComponentRotation()), copy(object:K2_GetComponentScale())
    end

    local function set_transform(record, loc, r, scale)
        local object = record.object
        if record.actor then
            object:K2_SetActorLocationAndRotation(loc, r, false, {}, true)
            object:SetActorScale3D(scale)
        else
            object:K2_SetWorldLocationAndRotation(loc, r, false, {}, true)
            object:SetWorldScale3D(scale)
        end
    end

    -- Starts tracking a vanilla object: remembers everything we may change, changes nothing.
    local function track(key, object)
        local record = self.edits[key]
        if record and owns(record.object, key) then return record end
        local is_actor = g.is_a(object, ACTOR)
        local root = is_actor and (g.call(object, "K2_GetRootComponent")) or object
        if not g.valid(root) then return nil, "no root component" end
        record = { object = object, actor = is_actor, root = root, mobility = root.Mobility }
        record.loc, record.rot, record.scale = self:transform(object)
        if is_actor then
            record.was_hidden, record.collision = object.bHidden == true, object:GetActorEnableCollision()
        else
            record.was_hidden, record.collision = object:IsVisible() == false, object:GetCollisionEnabled()
        end
        local mesh = root.StaticMesh
        record.mesh = g.valid(mesh) and g.path(mesh) or nil
        self.edits[key] = record
        return record
    end

    -- Makes a tracked object match `edit` (nil: as the Den had it). Visibility comes back only if we hid it and it
    -- was visible before: another mod (Plague Night's bar cleanup) may hide the same object in its own time.
    local function realize(record, edit)
        if edit and (edit.t or edit.r or edit.s) then
            record.root:SetMobility(2)
            set_transform(record, edit.t and vec(edit.t) or record.loc, edit.r and rot(edit.r) or record.rot,
                edit.s and vec(edit.s) or record.scale)
            record.moved = true
        elseif record.moved then
            set_transform(record, record.loc, record.rot, record.scale)
            record.root:SetMobility(record.mobility)
            record.moved = false
        end
        local object = record.object
        if edit and edit.hidden and not record.hidden then
            if record.actor then
                object:SetActorHiddenInGame(true)
                object:SetActorEnableCollision(false)
            else
                object:SetVisibility(false, true)
                object:SetCollisionEnabled(NO_COLLISION)
            end
            record.hidden = true
        elseif not (edit and edit.hidden) and record.hidden then
            if record.was_hidden == false then
                if record.actor then
                    object:SetActorHiddenInGame(false)
                    object:SetActorEnableCollision(record.collision ~= false)
                else
                    object:SetVisibility(true, true)
                    object:SetCollisionEnabled(record.collision)
                end
            end
            record.hidden = false
        end
    end

    local function apply_edit(key, edit, object)
        local record, why = track(key, object)
        if not record then return false, why end
        realize(record, edit)
        return true
    end

    -- The editor's way in: starts tracking a vanilla object it selected (nothing changes yet).
    function self:track(key, object)
        if not self.edits[key] and not owns(object, key) then return nil, "not in this Den" end
        return track(key, object)
    end

    -- Makes the tracked or given vanilla object `key` (an actor or component in this Den) match `edit`. A record
    -- stays after the object is put back, so the editor can still read where it stood.
    function self:set_vanilla(key, object, edit)
        local record = self.edits[key]
        if not record then
            if edit == nil then return true end
            if not owns(object, key) then return false, "not in this Den" end
        end
        return apply_edit(key, edit, record and record.object or object)
    end

    -- How a vanilla object stood in the Den before any edit (for the layout's fingerprint), or nil.
    function self:original(key)
        local record = self.edits[key]
        if not record then return nil end
        return { loc = record.loc, rot = record.rot, scale = record.scale, mesh = record.mesh }
    end

    local function destroy_placed(id)
        local record = self.placed[id]
        if not record then return end
        if owns(record.actor, record.path) then pcall(function() record.actor:K2_DestroyActor() end) end
        self.placed[id] = nil
    end

    local function same_list(a, b)
        a, b = a or {}, b or {}
        if #a ~= #b then return false end
        for i = 1, #a do if a[i] ~= b[i] then return false end end
        return true
    end

    local function place(entry, context)
        destroy_placed(entry.id)
        local mesh = g.load_object(entry.mesh)
        if not mesh or not g.is_a(mesh, STATIC_MESH) then return false, "missing mesh" end
        local host = g.spawn_host(context, vec(entry.t), 0)
        if not host then return false, "spawn failed" end
        local record = { actor = host, path = g.path(host), mesh = entry.mesh, mats = entry.mats }
        self.placed[entry.id] = record
        local component = g.add_component(host, MESH_COMPONENT)
        if not component then return false, "no mesh component" end
        record.component = component
        component:SetMobility(2)
        component:SetStaticMesh(mesh)
        for slot, path in ipairs(entry.mats or {}) do
            local material = path ~= "" and g.load_object(path) or nil
            if material and g.is_a(material, MATERIAL) then component:SetMaterial(slot - 1, material) end
        end
        local solid = entry.solid
        if solid == nil then
            local bounds = (g.call(mesh, "GetBounds"))
            local e = bounds and bounds.BoxExtent
            local scale = math.max(entry.s[1], entry.s[2], entry.s[3])
            solid = e ~= nil and math.max(e.X, e.Y, e.Z) * 2 * scale > M.SOLID_SIZE
        end
        -- Not solid: pawns walk through, but visibility traces (the editor's clicks) still hit it.
        component:SetCollisionProfileName(FName("BlockAll"), true)
        if not solid then component:SetCollisionResponseToChannel(ECC_PAWN, ECR_IGNORE) end
        -- After the component: an actor spawned without a root loses its spawn transform.
        host:K2_SetActorLocationAndRotation(vec(entry.t), rot(entry.r), false, {}, true)
        host:SetActorScale3D(vec(entry.s))
        return true
    end

    -- The editor's way in for placed meshes: entry nil removes it; a changed transform moves the existing
    -- actor; a changed mesh or materials respawns it.
    function self:set_placed(id, entry)
        if entry == nil then destroy_placed(id); return true end
        local record = self.placed[id]
        if record and owns(record.actor, record.path) and record.mesh == entry.mesh and same_list(record.mats, entry.mats) then
            record.actor:K2_SetActorLocationAndRotation(vec(entry.t), rot(entry.r), false, {}, true)
            record.actor:SetActorScale3D(vec(entry.s))
            return true
        end
        local context = g.any_context()
        if not context then return false, "no world" end
        return place(entry, context)
    end

    -- The id of a placed mesh from its actor's path, or nil.
    function self:placed_id(path)
        for id, record in pairs(self.placed) do
            if record.path == path then return id end
        end
        return nil
    end

    function self:placed_count()
        local n = 0
        for _ in pairs(self.placed) do n = n + 1 end
        return n
    end

    -- A patch may have renamed an object: match fingerprints (mesh + location) against the loaded static mesh
    -- components, one scan for all of them.
    local function refind(keys, layout)
        local wanted = {}
        for _, key in ipairs(keys) do if layout.vanilla[key].fp then wanted[#wanted + 1] = key end end
        local found = {}
        if #wanted == 0 then return found end
        for _, component in ipairs(FindAllOf("StaticMeshComponent") or {}) do
            if g.valid(component) and in_world(component) then
                local mesh = component.StaticMesh
                local mesh_path = g.valid(mesh) and g.path(mesh) or nil
                if mesh_path then
                    local at = component:K2_GetComponentLocation()
                    for _, key in ipairs(wanted) do
                        if not found[key] and Layout.matches(layout.vanilla[key].fp, mesh_path, at) then found[key] = component end
                    end
                end
            end
        end
        return found
    end

    -- The Den is gone (a new world): its objects went with it, so drop everything without touching it.
    function self:forget(reason)
        self.epoch = self.epoch + 1
        actions:cancel_group("den-apply", reason)
        self.edits, self.placed, self.world, self.busy = {}, {}, nil, false
    end

    -- Undo everything in the current Den.
    function self:clear(reason)
        self.epoch = self.epoch + 1
        actions:cancel_group("den-apply", reason)
        for key, record in pairs(self.edits) do
            local ok, err = pcall(function() if owns(record.object, key) then realize(record, nil) end end)
            if not ok then log("WARNING: restore %s | %s", key, tostring(err)) end
        end
        for id in pairs(self.placed) do destroy_placed(id) end
        self.edits, self.placed, self.world, self.busy = {}, {}, nil, false
    end

    -- Applies `layout` to the world `world` (a g.world_key); `on_done(report)` runs once everything settled.
    function self:begin(layout, world, on_done)
        self:clear("replaced")
        self.world, self.busy = world, true
        local epoch = self.epoch
        local report = { placed = 0, hidden = 0, moved = 0, refound = 0, dormant = {}, missing = {}, errors = 0,
                         frames = 0, work = 0, slowest = 0, scans = 0, started = os.clock() }
        self.report = report

        local waiting = {}
        for key in pairs(layout.vanilla) do waiting[#waiting + 1] = key end
        table.sort(waiting)
        local queue, index, absent, wait_pass = {}, 1, {}, 0

        local function count_edit(edit)
            if edit.hidden then report.hidden = report.hidden + 1 end
            if edit.t or edit.r or edit.s then report.moved = report.moved + 1 end
        end

        -- One bulk scan for every waiting key whose level is loaded; the rest keep waiting.
        local function resolve(context)
            local t0 = os.clock()
            local found, missing, still = resolver.find(waiting, context)
            report.scans = report.scans + 1
            report.work = report.work + (os.clock() - t0)
            for _, key in ipairs(waiting) do
                if found[key] then queue[#queue + 1] = { key = key, object = found[key] } end
            end
            for _, key in ipairs(missing) do absent[#absent + 1] = key end
            waiting = still
        end

        local function run(job, context)
            if job.entry then
                local ok, why = place(job.entry, context)
                if ok then report.placed = report.placed + 1
                else report.missing[#report.missing + 1] = job.entry.id .. " (" .. why .. ": " .. job.entry.mesh .. ")" end
                return
            end
            if not owns(job.object, g.path(job.object)) then
                report.dormant[#report.dormant + 1] = job.key .. " (gone before it was edited)"
                return
            end
            local edit = layout.vanilla[job.key]
            local ok, why = apply_edit(job.key, edit, job.object)
            if ok then count_edit(edit) else report.dormant[#report.dormant + 1] = job.key .. " (" .. why .. ")" end
        end

        local function finish()
            local found = refind(absent, layout)
            for _, key in ipairs(absent) do
                local component = found[key]
                if component and apply_edit(key, layout.vanilla[key], component) then
                    report.refound = report.refound + 1
                    count_edit(layout.vanilla[key])
                    log("Den | re-found %s by its fingerprint as %s", key, g.path(component))
                else
                    report.dormant[#report.dormant + 1] = key .. " (not in its level)"
                end
            end
            for _, key in ipairs(waiting) do report.dormant[#report.dormant + 1] = key .. " (level not loaded)" end
            report.seconds = os.clock() - report.started
            self.busy = false
            if on_done then on_done(report) end
        end

        local step
        local function wait_for_levels()
            if self.epoch ~= epoch then return end
            local context = g.any_context()
            if not g.valid(context) or g.world_key(context) ~= world then return end
            wait_pass = wait_pass + 1
            local loaded = resolver.loaded_levels(context)
            local arrived = false
            for _, key in ipairs(waiting) do
                if loaded[(Resolve.split(key))] then arrived = true; break end
            end
            if arrived then
                resolve(context)
                step()
            elseif wait_pass < M.WAIT_PASSES then
                actions:schedule_after("den-apply", M.WAIT_MS, wait_for_levels)
            else
                finish()
            end
        end

        function step()
            if self.epoch ~= epoch then return end
            local context = g.any_context()
            if not g.valid(context) or g.world_key(context) ~= world then return end
            report.frames = report.frames + 1
            local t0 = os.clock()
            while index <= #queue and os.clock() - t0 < M.BUDGET do
                local job = queue[index]
                index = index + 1
                local j0 = os.clock()
                local ok, err = pcall(run, job, context)
                local spent = os.clock() - j0
                if spent > report.slowest then report.slowest, report.slowest_job = spent, job.key or job.entry.id end
                if not ok then
                    report.errors = report.errors + 1
                    log("WARNING: Den | %s | %s", job.key or job.entry.id, tostring(err))
                end
            end
            report.work = report.work + (os.clock() - t0)
            if index <= #queue then
                actions:schedule_after("den-apply", 1, step)
            elseif #waiting > 0 and wait_pass < M.WAIT_PASSES then
                actions:schedule_after("den-apply", M.WAIT_MS, wait_for_levels)
            else
                finish()
            end
        end

        local context = g.any_context()
        if #waiting > 0 then resolve(context) end
        -- Vanilla edits first: the clutter goes before anything new appears.
        for _, entry in ipairs(layout.placed) do queue[#queue + 1] = { entry = entry } end
        step()
    end

    return self
end

return M
