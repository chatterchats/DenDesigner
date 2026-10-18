-- Den Designer: catalog thumbnails. A small studio far above Hologram Land (the developers' old portrait area,
-- 5 km from the Den and out of the player's sight): one mesh, two short-range point lights and a scene capture
-- that renders only that mesh. Each picture is exported once as a PNG under Saved\ZComDen\thumbs and loaded back
-- as a texture for its catalog tile. The studio exists only while pictures are being rendered.
--
-- Rendering loads meshes, so it runs from scheduled actions (the game thread's tick), never inside a hook.
-- No texture is kept here: a picture is imported from its PNG and handed to the list item that shows it, in the
-- same tick. Only the list keeps it alive, and a Lua reference to a texture the game has since freed is not safe
-- to touch at all (even IsValid reads the freed memory: crashes 2026-10-18).
local M = {}

M.SIZE = 128            -- pixels
M.FOV = 30              -- degrees
M.MARGIN = 1.08
M.EVERY_MS = 50         -- one new picture per this many ms while the queue runs
M.BUDGET = 0.008        -- seconds per tick for loading pictures already on disk
M.IDLE_MS = 3000        -- studio torn down after this long with nothing to render
M.STUDIO = { X = -522700, Y = 13000, Z = 28800 }
M.VIEW = { 0.75, -0.55, 0.45 }  -- camera direction from the mesh: front right, from above
M.KEY, M.FILL = 14, 5           -- light intensity per cm^2 of bounding radius

local FORMAT_RGBA8, CAPTURE_LDR, SHOW_ONLY = 2, 2, 2

local function normalize(x, y, z)
    local len = math.sqrt(x * x + y * y + z * z)
    return x / len, y / len, z / len
end

-- How far back a camera looking along -view must stand to fit a box (center-relative half extents) in a square
-- frame of `fov` degrees. Pure: tested offline.
function M.distance(extent, view, fov)
    local fx, fy, fz = normalize(-view[1], -view[2], -view[3])        -- forward
    local rx, ry, rz = normalize(-fy, fx, 0)                          -- right (horizontal)
    if rx ~= rx then rx, ry, rz = 0, 1, 0 end
    local ux, uy, uz = ry * fz - rz * fy, rz * fx - rx * fz, rx * fy - ry * fx  -- up
    local t = math.tan(math.rad(fov / 2))
    local need = 1
    for _, sx in ipairs({ -1, 1 }) do
        for _, sy in ipairs({ -1, 1 }) do
            for _, sz in ipairs({ -1, 1 }) do
                local cx, cy, cz = sx * extent[1], sy * extent[2], sz * extent[3]
                local along = cx * fx + cy * fy + cz * fz
                local side = math.max(math.abs(cx * rx + cy * ry + cz * rz), math.abs(cx * ux + cy * uy + cz * uz))
                need = math.max(need, side / t - along)
            end
        end
    end
    return need * M.MARGIN
end

-- A stable file name for a mesh path: its readable name plus a hash of the whole path.
function M.file_name(path)
    local h = 5381
    for i = 1, #path do h = (h * 33 + path:byte(i)) % 4294967296 end
    local name = (path:match("([^/%.]+)$") or "mesh"):gsub("[^%w_%-]", "_")
    return string.format("%s_%08x.png", name, h)
end

function M.new(ctx, folder)
    local g, log, actions = ctx.g, ctx.log, ctx.actions
    -- enabled: the "Pictures in the catalog" setting; off, nothing new is rendered (pictures on disk still show).
    local self = { folder = folder, queue = {}, queued = {}, rendered = 0, enabled = true }
    local studio      -- { hosts, prop, mesh_component, key, fill, camera, capture, target }
    local running = false
    local idle_since

    local function v(x, y, z) return { X = x, Y = y, Z = z } end

    function self:file(path) return self.folder .. "\\" .. M.file_name(path) end

    local function exists(file)
        local f = io.open(file, "rb")
        if f then f:close() return true end
        return false
    end

    -- A new texture of the picture for `path`, imported from its PNG, or nil if it isn't rendered yet. Hand it
    -- to whatever shows it in the same tick.
    function self:texture(path)
        local file = self:file(path)
        if not exists(file) then return nil end
        local texture = (g.call(g.rendering(), "ImportFileAsTexture2D", g.any_context(), file))
        return g.valid(texture) and texture or nil
    end

    local function teardown()
        if not studio then return end
        for _, host in ipairs(studio.hosts) do pcall(function() host:K2_DestroyActor() end) end
        pcall(function() g.rendering():ReleaseRenderTarget2D(studio.target) end)
        studio = nil
    end

    local function build(context)
        local s = { hosts = {} }
        local function host()
            local a = g.spawn_host(context, M.STUDIO, 0)
            s.hosts[#s.hosts + 1] = a
            return a
        end
        s.prop = host()
        s.mesh_component = g.add_component(s.prop, "/Script/Engine.StaticMeshComponent")
        s.mesh_component:SetMobility(2)
        s.mesh_component:SetCollisionEnabled(0)
        local key_host, fill_host = host(), host()
        s.key = g.add_component(key_host, "/Script/Engine.PointLightComponent")
        s.fill = g.add_component(fill_host, "/Script/Engine.PointLightComponent")
        s.key_host, s.fill_host = key_host, fill_host
        for _, light in ipairs({ s.key, s.fill }) do light:SetCastShadows(false) end
        s.camera = host()
        s.capture = g.add_component(s.camera, "/Script/Engine.SceneCaptureComponent2D")
        s.capture.FOVAngle = M.FOV
        s.capture.bCaptureEveryFrame = false
        s.capture.bCaptureOnMovement = false
        s.capture.PrimitiveRenderMode = SHOW_ONLY
        s.capture.CaptureSource = CAPTURE_LDR
        s.capture:ShowOnlyActorComponents(s.prop, false)
        s.target = g.rendering():CreateRenderTarget2D(context, M.SIZE, M.SIZE, FORMAT_RGBA8, { R = 0, G = 0, B = 0, A = 1 }, false, false)
        s.capture.TextureTarget = s.target
        studio = s
    end

    -- Renders one mesh into a PNG; returns the texture or nil plus why.
    local function render(path)
        local context = g.any_context()
        if not context then return nil, "no world" end
        local mesh = g.load_object(path)
        if not mesh then return nil, "missing mesh" end
        if not studio then build(context) end
        local bounds = mesh:GetBounds()
        local o, e, r = bounds.Origin, bounds.BoxExtent, math.max(bounds.SphereRadius, 1)
        studio.mesh_component:SetStaticMesh(mesh)
        local at = M.STUDIO
        studio.prop:K2_SetActorLocation(v(at.X - o.X, at.Y - o.Y, at.Z - o.Z), false, {}, true)
        studio.key_host:K2_SetActorLocation(v(at.X + 2.5 * r, at.Y - 1.5 * r, at.Z + 2.5 * r), false, {}, true)
        studio.fill_host:K2_SetActorLocation(v(at.X - 2 * r, at.Y + 2.5 * r, at.Z + r), false, {}, true)
        for _, pair in ipairs({ { studio.key, M.KEY }, { studio.fill, M.FILL } }) do
            pair[1]:SetAttenuationRadius(r * 12)
            pair[1]:SetIntensity(pair[2] * r * r)
        end
        local dist = M.distance({ e.X, e.Y, e.Z }, M.VIEW, M.FOV)
        local dx, dy, dz = normalize(M.VIEW[1], M.VIEW[2], M.VIEW[3])
        local camera_at = v(at.X + dx * dist, at.Y + dy * dist, at.Z + dz * dist)
        studio.camera:K2_SetActorLocation(camera_at, false, {}, true)
        local look = g.cdo("/Script/Engine.Default__KismetMathLibrary"):FindLookAtRotation(camera_at, at)
        studio.camera:K2_SetActorRotation(look, true)
        studio.capture:CaptureScene()
        g.rendering():ExportRenderTarget(context, studio.target, self.folder, M.file_name(path))
        local texture = self:texture(path)
        if not texture then return nil, "export failed" end
        self.rendered = self.rendered + 1
        return texture
    end

    -- Each callback gets its own texture: whatever shows it keeps it alive.
    local function deliver(job, texture)
        for i, done in ipairs(job.done) do
            local t = i == 1 and texture or self:texture(job.path)
            if t then pcall(done, job.path, t) end
        end
    end

    local step
    function step()
        if not running then return end
        local job = table.remove(self.queue, 1)
        if not job then
            idle_since = idle_since or os.clock()
            if (os.clock() - idle_since) * 1000 >= M.IDLE_MS then
                running = false
                teardown()
                return
            end
            actions:schedule_after("den-thumbs", M.EVERY_MS, step)
            return
        end
        idle_since = nil
        -- Pictures already on disk load within a small budget per tick; a new one is rendered, then we wait.
        local t0, rendered_one = os.clock(), false
        while job do
            self.queued[job.path] = nil
            local texture = self:texture(job.path)
            if texture then
                deliver(job, texture)
            elseif not self.enabled then
                -- Pictures are off: only those already on disk are shown.
            else
                rendered_one = true
                local ok, rendered, why = pcall(render, job.path)
                if not ok then why, rendered = rendered, nil end
                if rendered then deliver(job, rendered)
                else log("WARNING: thumbnail %s | %s", job.path, tostring(why)) end
                break
            end
            if os.clock() - t0 >= M.BUDGET then break end
            job = table.remove(self.queue, 1)
        end
        actions:schedule_after("den-thumbs", rendered_one and M.EVERY_MS or 1, step)
    end

    -- Queues `path`; done(path, texture) runs when its picture is ready.
    -- A path asked for again while it's still queued gets the new callback too: a list rebuilt before its
    -- pictures arrived (the Storeroom, after a store or restore) must still get them.
    function self:request(path, done)
        local job = self.queued[path]
        if job then
            job.done[#job.done + 1] = done
            return
        end
        job = { path = path, done = { done } }
        self.queued[path] = job
        self.queue[#self.queue + 1] = job
        if not running then
            running, idle_since = true, nil
            local ok = pcall(function() g.make_directories(g.any_context(), { self.folder }) end)
            if not ok then log("WARNING: thumbnails | can't create %s", self.folder) end
            actions:schedule_after("den-thumbs", 0, step)
        end
    end

    -- Drops what's still waiting (the catalog moved on to another shelf).
    function self:forget_queue()
        self.queue, self.queued = {}, {}
    end

    function self:stop(reason)
        running = false
        actions:cancel_group("den-thumbs", reason)
        self:forget_queue()
        teardown()
    end

    -- The world went away: its actors went with it.
    function self:forget()
        running = false
        actions:cancel_group("den-thumbs", "left the Den")
        self:forget_queue()
        studio = nil
    end

    return self
end

return M
