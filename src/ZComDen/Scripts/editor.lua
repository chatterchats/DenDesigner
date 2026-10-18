-- Den Designer: edit mode. Ctrl+Home in the Den opens it: a flying camera (BP_DenEditorRig, a kit asset that
-- flies itself from its own input actions), the toolbar (WBP_DenToolbar) and the editor's mapping context, which
-- outranks the game's so Hawks stays put. The kit assets call empty Lua_* functions that we pre-hook here.
--
-- Edits go to a working copy of the layout through history.lua (undo/redo) and to the Den through apply.lua.
-- Nothing reaches the layout file until Save; leaving without saving reapplies the file.
local History = require("history")
local Layout = require("layout")
local Pick = require("pick")
local Highlight = require("highlight")
local M = {}

local KIT = "/Game/ZComDen/Editor/"
local RIG_CLASS = KIT .. "BP_DenEditorRig.BP_DenEditorRig_C"
local TOOLBAR_CLASS = KIT .. "WBP_DenToolbar.WBP_DenToolbar_C"
local IMC = KIT .. "IMC_DenEditor.IMC_DenEditor"
local WBL = "/Script/UMG.Default__WidgetBlueprintLibrary"
local CLASSES = {
    actor = "/Script/Engine.Actor", pawn = "/Script/Engine.Pawn", mesh = "/Script/Engine.StaticMeshComponent",
    instanced = "/Script/Engine.InstancedStaticMeshComponent", static_actor = "/Script/Engine.StaticMeshActor",
    interactable = "/Script/BitReactorGame.InteractableComponent",
}
local IMC_PRIORITY = 1000000
-- Keys held while the mapping changes are ignored until released: without that, the Esc that closes the editor
-- reaches the game's own mapping and opens the pause menu, and the Ctrl of Ctrl+Home flies the camera down.
local IMC_OPTIONS = { bIgnoreAllPressedKeysUntilRelease = true, bForceImmediately = true, bNotifyUserSettings = false }
local VISIBLE, COLLAPSED = 0, 1

M.SNAPS = { 0, 5, 10, 25, 50 }     -- cm; 0 is off
M.REACHES = { 1000, 2000, 4000, 10000 } -- cm: how far a click or hover reaches
M.ROTATE_STEP, M.FINE_STEP = 15, 1 -- degrees per wheel notch / key press
M.SCALE_STEP = 1.05
M.NUDGE = 5                         -- cm per arrow press with snap off
M.DRAG_START = 0.005                -- radians the cursor ray must turn before a press becomes a drag
M.FLOOR = 0.7                       -- a hit normal at least this upright counts as something to stand things on
M.TRACE = 20000                     -- cm

-- Small vector helpers on {X, Y, Z} tables.
local function v(x, y, z) return { X = x, Y = y, Z = z } end
local function add(a, b) return v(a.X + b.X, a.Y + b.Y, a.Z + b.Z) end
local function sub(a, b) return v(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
local function mul(a, k) return v(a.X * k, a.Y * k, a.Z * k) end
local function dot(a, b) return a.X * b.X + a.Y * b.Y + a.Z * b.Z end
local function arr(a) return { a.X, a.Y, a.Z } end
local function round_to(x, step) return math.floor(x / step + 0.5) * step end
local function wrap(deg) deg = deg % 360; if deg > 180 then deg = deg - 360 end; return deg end

-- Where a ray meets a plane (point p, normal n), or nil when it runs along it or away from it.
local function ray_plane(o, d, p, n)
    local den = dot(d, n)
    if math.abs(den) < 1e-4 then return nil end
    local t = dot(sub(p, o), n) / den
    if t < 0 or t > M.TRACE * 2 then return nil end
    return add(o, mul(d, t))
end

function M.new(ctx)
    local g, log, actions, runtime, store, watch = ctx.g, ctx.log, ctx.actions, ctx.runtime, ctx.store, ctx.watch
    local apply = watch.apply
    local self = { active = false, snap = 1, reach = 2, unlocked = false }
    local highlight = Highlight.new(g)
    local hooked = false
    -- Per-session state, reset by reset_session().
    local s

    local function reset_session()
        s = { pc = nil, rig = nil, widget = nil, sub = nil, imc = nil, view_was = nil, cursor_was = false,
              click_was = true, over_was = true, doc = nil, history = nil, objects = {}, facts = {},
              sel = nil, hover = nil, press = nil, drag = nil, looking = false, frame = 0, message = "" }
    end
    reset_session()

    local function str(param)
        local ok, value = pcall(function() return param:get():ToString() end)
        return ok and value or ""
    end
    local function num(param)
        local ok, value = pcall(function() return param:get() end)
        return ok and tonumber(value) or 0
    end

    ---------------------------------------------------------------------------------------------- toolbar --
    local function text(field, value)
        if not g.valid(s.widget) then return end
        pcall(function() s.widget[field]:SetText(FText(value)) end)
    end

    local function refresh()
        if not s.doc then return end
        local counts = Layout.counts(s.doc)
        local scope = watch.scope == "campaign" and "this campaign's own layout" or "the home layout (every campaign)"
        text("Scope", string.format("Editing %s  |  %d placed, %d hidden, %d moved%s", scope, counts.placed,
            counts.hidden, counts.moved, s.history:dirty() and "  |  unsaved" or ""))
        text("Selection", s.sel and s.sel.label or "Nothing selected: click a prop")
        text("Status", s.message)
        local snap = M.SNAPS[self.snap]
        text("SnapLabel", snap == 0 and "Snap: off" or ("Snap: " .. snap .. " cm"))
        text("ReachLabel", string.format("Reach: %d m", math.floor(M.REACHES[self.reach] / 100)))
        text("LockLabel", self.unlocked and "Structure: unlocked" or "Structure: locked")
    end

    local function say(fmt, ...)
        local message = select("#", ...) > 0 and string.format(fmt, ...) or fmt
        if message ~= "" and message ~= s.message then log("Editor | %s", message) end
        s.message = message
        refresh()
    end

    local function confirm(show)
        if not g.valid(s.widget) then return end
        if show then
            local n = #s.history.undos
            text("ConfirmText", string.format("You made %d change%s since the last save.", n, n == 1 and "" or "s"))
        end
        pcall(function() s.widget.Confirm:SetVisibility(show and VISIBLE or COLLAPSED) end)
        s.confirming = show
    end

    ---------------------------------------------------------------------------------------------- picking --
    local function cursor_ray()
        local o, d = {}, {}
        local ok, hit = pcall(function() return s.pc:DeprojectMousePositionToWorld(o, d) end)
        if not ok or not hit or o.X == nil then return nil end
        return v(o.X, o.Y, o.Z), v(d.X, d.Y, d.Z)
    end

    local function trace(o, d, ignore, length)
        local hit = {}
        local ok, blocked = pcall(function()
            return g.kismet():LineTraceSingle(s.rig, o, add(o, mul(d, length or M.TRACE)), 0, true, ignore or {}, 0, hit, true,
                { R = 1, G = 0, B = 0, A = 1 }, { R = 0, G = 1, B = 0, A = 1 }, 0)
        end)
        if not ok or not blocked then return nil end
        local component = hit.Component and g.unwrap(hit.Component)
        local p, n = hit.ImpactPoint, hit.ImpactNormal
        return { component = g.valid(component) and component or nil, point = v(p.X, p.Y, p.Z), normal = v(n.X, n.Y, n.Z) }
    end

    local function bounds(component)
        local o, e = {}, {}
        local ok = pcall(function() g.kismet():GetComponentBounds(component, o, e, {}) end)
        if not ok or o.X == nil then return nil end
        return v(o.X, o.Y, o.Z), v(e.X, e.Y, e.Z)
    end

    -- What the rules need to know about a hit component; cached per component while the editor is open.
    local function facts(component)
        local path = g.path(component)
        local f = s.facts[path]
        if f and f.unlocked == self.unlocked then return f end
        local owner = (g.call(component, "GetOwner"))
        local owner_path = g.valid(owner) and g.path(owner) or "?"
        local mesh = component.StaticMesh
        f = { path = path, owner = owner, owner_path = owner_path, unlocked = self.unlocked,
              placed = apply:placed_id(owner_path), mesh_component = g.is_a(component, CLASSES.mesh),
              instanced = g.is_a(component, CLASSES.instanced), pawn = g.valid(owner) and g.is_a(owner, CLASSES.pawn),
              mesh = g.valid(mesh) and g.path(mesh) or nil }
        if g.valid(owner) and not f.placed then
            local class = StaticFindObject(CLASSES.interactable)
            f.interactable = class ~= nil and g.valid((g.call(owner, "GetComponentByClass", class)))
            -- Runtime-spawned plain actors in the persistent level belong to other mods (Plague Night, Arcade).
            f.foreign = g.full_name(owner):match("^Actor ") ~= nil and owner_path:find("/HUB_Root.HUB_Root:PersistentLevel.", 1, true) ~= nil
        end
        local _, extent = bounds(component)
        f.size = extent and 2 * math.max(extent.X, extent.Y, extent.Z) or 0
        f.ok, f.reason = Pick.allowed(f)
        if f.ok then
            if f.placed then
                f.kind, f.key, f.object = "placed", f.placed, owner
            else
                local root = (g.call(owner, "K2_GetRootComponent"))
                local is_root = g.valid(root) and g.path(root) == path
                local unit = Pick.unit(g.is_a(owner, CLASSES.static_actor), is_root)
                f.kind = "vanilla"
                f.key, f.object = unit == "actor" and owner_path or path, unit == "actor" and owner or component
            end
            f.label = Pick.label(f.mesh, not f.placed and path or nil)
        end
        s.facts[path] = f
        return f
    end

    local function pick(o, d)
        local hit = trace(o, d, nil, M.REACHES[self.reach])
        if not hit or not hit.component then return nil end
        return facts(hit.component), hit
    end

    ------------------------------------------------------------------------------------------- selection --
    local function select(f, component)
        if s.sel then highlight:clear(s.sel.component) end
        if s.hover then highlight:clear(s.hover); s.hover = nil end
        if not f then s.sel = nil; refresh(); return end
        s.sel = { kind = f.kind, key = f.key, object = f.object, component = component, label = f.label, mesh = f.mesh }
        if f.kind == "vanilla" then
            s.objects[f.key] = f.object
            apply:track(f.key, f.object)
        end
        highlight:set(component, Highlight.SELECTED)
        refresh()
    end

    -- After undo/redo a placed mesh may have been respawned (or removed), a vanilla one hidden.
    local function revalidate()
        local sel = s.sel
        if not sel then return end
        if sel.kind == "placed" then
            local record = apply.placed[sel.key]
            if record and g.valid(record.actor) then
                if g.path(record.component) ~= g.path(sel.component) then
                    highlight:clear(sel.component)
                    sel.object, sel.component = record.actor, record.component
                    highlight:set(sel.component, Highlight.SELECTED)
                end
                return
            end
        else
            local state = s.history:get("vanilla", sel.key)
            if not (state and state.hidden) then return end
        end
        select(nil)
    end

    -- The selection's transform as layout arrays: its edit where it has one, else where the Den put it.
    local function pose(sel)
        local state = s.history:get(sel.kind, sel.key)
        if sel.kind == "placed" then return state.t, state.r, state.s end
        local o = apply:original(sel.key)
        state = state or {}
        return state.t or arr(o.loc), state.r or { o.rot.Pitch, o.rot.Yaw, o.rot.Roll }, state.s or arr(o.scale)
    end

    -- The selection's entry with `change` applied; a vanilla edit gets its fingerprint on first change and is
    -- dropped (nil) once it no longer changes anything.
    local function changed(sel, change)
        local state = s.history:get(sel.kind, sel.key)
        if sel.kind == "vanilla" then
            state = state or {}
            local o = apply:original(sel.key)
            if not state.fp and o and o.mesh then state.fp = Layout.fingerprint(o.mesh, o.loc) end
        end
        change(state)
        if sel.kind == "vanilla" and not (state.hidden or state.t or state.r or state.s) then return nil end
        return state
    end

    local function commit(label, sel, state, merge)
        local ok, why = s.history:commit(label, { { sel.kind, sel.key, state } }, merge)
        if not ok then say("%s failed: %s", label, tostring(why)) end
        revalidate()
        return ok
    end

    -- Shows the selection somewhere without recording it (drag preview).
    local function preview(sel, t)
        local state = changed(sel, function(st) st.t = { t.X, t.Y, t.Z } end)
        if sel.kind == "placed" then apply:set_placed(sel.key, state) else apply:set_vanilla(sel.key, sel.object, state) end
    end

    ----------------------------------------------------------------------------------------------- drag --
    local function snap_xy(p)
        local step = M.SNAPS[self.snap]
        if step == 0 then return p end
        return v(round_to(p.X, step), round_to(p.Y, step), p.Z)
    end

    -- (Re)starts the drag maths from where the object is now: on a surface, it keeps its offset from the point
    -- under the cursor; with Shift, it moves only up and down on a plane facing the camera.
    local function rebase(o, d)
        local drag = s.drag
        drag.vertical = s.rig.bFast == true
        drag.base = drag.current
        if drag.vertical then
            drag.normal = v(-d.X, -d.Y, 0)
            local len = math.sqrt(drag.normal.X ^ 2 + drag.normal.Y ^ 2)
            if len < 1e-3 then drag.normal = v(1, 0, 0) else drag.normal = mul(drag.normal, 1 / len) end
            drag.grab = ray_plane(o, d, drag.base, drag.normal)
        else
            local hit = trace(o, d, drag.ignore)
            if hit and hit.normal.Z >= M.FLOOR then
                drag.grab, drag.plane_z = hit.point, hit.point.Z
            else
                drag.plane_z = drag.base.Z
                drag.grab = ray_plane(o, d, v(0, 0, drag.plane_z), v(0, 0, 1))
            end
        end
        if drag.grab then drag.offset = sub(drag.base, drag.grab) end
    end

    local function begin_drag(o, d)
        local sel = s.sel
        local t = pose(sel)
        local owner = sel.kind == "placed" and sel.object or (g.call(sel.component, "GetOwner"))
        s.drag = { current = v(t[1], t[2], t[3]), ignore = g.valid(owner) and { owner } or {} }
        s.drag.start = s.drag.current
        rebase(o, d)
    end

    local function update_drag(o, d)
        local drag = s.drag
        if (s.rig.bFast == true) ~= drag.vertical or not drag.grab then rebase(o, d) end
        if not drag.grab then return end
        local target
        if drag.vertical then
            local p = ray_plane(o, d, drag.grab, drag.normal)
            if not p then return end
            target = v(drag.base.X, drag.base.Y, drag.base.Z + (p.Z - drag.grab.Z))
        else
            local hit = trace(o, d, drag.ignore)
            local anchor
            if hit and hit.normal.Z >= M.FLOOR then
                anchor, drag.plane_z = hit.point, hit.point.Z
            else
                anchor = ray_plane(o, d, v(0, 0, drag.plane_z), v(0, 0, 1))
            end
            if not anchor then return end
            target = snap_xy(add(anchor, drag.offset))
        end
        drag.current = target
        preview(s.sel, target)
    end

    local function end_drag(cancel)
        local drag, sel = s.drag, s.sel
        s.drag = nil
        if not drag or not sel then return end
        local t = cancel and drag.start or drag.current
        local state = changed(sel, function(st) st.t = { t.X, t.Y, t.Z } end)
        if cancel then
            -- Put it back exactly as recorded.
            local before = s.history:get(sel.kind, sel.key)
            if sel.kind == "placed" then apply:set_placed(sel.key, before) else apply:set_vanilla(sel.key, sel.object, before) end
            say("Move cancelled")
            return
        end
        if commit("Move", sel, state) then say("Moved %s", sel.label) end
    end

    ------------------------------------------------------------------------------------------- commands --
    local commands = {}

    function commands.rotate(steps, step)
        local sel = s.sel
        if not sel then return say("Select a prop first") end
        local _, r = pose(sel)
        local yaw = wrap(r[2] + steps * (step or M.ROTATE_STEP))
        commit("Rotate", sel, changed(sel, function(st) st.r = { r[1], yaw, r[3] } end), "rotate")
        say("Rotated to %.0f degrees", yaw)
    end

    function commands.rotate_fine(steps) commands.rotate(steps, M.FINE_STEP) end

    function commands.scale(steps)
        local sel = s.sel
        if not sel then return say("Select a prop first") end
        local _, _, sc = pose(sel)
        local k = M.SCALE_STEP ^ steps
        local out = {}
        for i = 1, 3 do out[i] = math.max(0.05, math.min(20, sc[i] * k)) end
        commit("Scale", sel, changed(sel, function(st) st.s = out end), "scale")
        say("Scale %.2f", out[1])
    end

    -- Arrows / PgUp / PgDn: along the world axis nearest the camera's forward and right, or straight up.
    function commands.nudge(value)
        local sel = s.sel
        if not sel then return say("Select a prop first") end
        local step = M.SNAPS[self.snap] > 0 and M.SNAPS[self.snap] or M.NUDGE
        local yaw = math.rad(round_to(s.rig:K2_GetActorRotation().Yaw, 90))
        local fx, fy = math.cos(yaw), math.sin(yaw)
        local dx = (value.X * fx - value.Y * fy) * step
        local dy = (value.X * fy + value.Y * fx) * step
        local t = pose(sel)
        local to = { t[1] + dx, t[2] + dy, t[3] + value.Z * step }
        commit("Nudge", sel, changed(sel, function(st) st.t = to end), "nudge")
        say("Nudged %s", sel.label)
    end

    function commands.store()
        local sel = s.sel
        if not sel then return say("Select a prop first") end
        select(nil)
        if sel.kind == "placed" then
            commit("Remove", sel, nil)
            say("Removed %s (Z to undo)", sel.label)
        else
            commit("Store", sel, changed(sel, function(st) st.hidden = true end))
            say("Stored %s (Z to undo)", sel.label)
        end
    end

    function commands.duplicate()
        local sel = s.sel
        if not sel then return say("Select a prop first") end
        if not sel.mesh then return say("This prop has no mesh to copy") end
        local t, r, sc = pose(sel)
        local mats
        if sel.kind == "placed" then
            mats = s.history:get("placed", sel.key).mats
        else
            mats = {}
            local n = tonumber((g.call(sel.component, "GetNumMaterials"))) or 0
            for i = 0, n - 1 do
                local m = (g.call(sel.component, "GetMaterial", i))
                local p = g.valid(m) and g.path(m) or ""
                mats[#mats + 1] = p:match("^/[%w_]+/[^%.:]+%.[%w_]+$") and p or ""
            end
            if #mats == 0 then mats = nil end
        end
        -- Beside the original, to the camera's right.
        local _, extent = bounds(sel.component)
        local gap = extent and (2 * math.max(extent.X, extent.Y) + 10) or 100
        local yaw = math.rad(s.rig:K2_GetActorRotation().Yaw)
        local entry = { id = Layout.next_id(s.doc), mesh = sel.mesh, t = { t[1] - math.sin(yaw) * gap, t[2] + math.cos(yaw) * gap, t[3] },
                        r = r, s = sc, mats = mats, from = sel.kind == "vanilla" and sel.key or nil }
        entry = Layout.normalise({ placed = { entry } }).placed[1]
        if not entry then return say("Can't copy this prop") end
        local copy = { kind = "placed", key = entry.id }
        if not commit("Copy", copy, entry) then return end
        local record = apply.placed[entry.id]
        if record and g.valid(record.component) then
            select({ kind = "placed", key = entry.id, object = record.actor, label = Pick.label(entry.mesh, nil), mesh = entry.mesh },
                record.component)
        end
        say("Copied %s", sel.label)
    end

    function commands.reset()
        local sel = s.sel
        if not sel then return say("Select a prop first") end
        if sel.kind == "placed" then
            local _, r = pose(sel)
            commit("Reset", sel, changed(sel, function(st) st.r, st.s = { 0, r[2], 0 }, { 1, 1, 1 } end))
            say("Straightened %s and reset its scale", sel.label)
        else
            commit("Reset", sel, nil)
            say("Put %s back where the Den had it", sel.label)
        end
    end

    function commands.undo()
        if s.drag then end_drag(true) end
        local label = s.history:undo()
        revalidate()
        say(label and ("Undid " .. label:lower()) or "Nothing to undo")
    end

    function commands.redo()
        local label = s.history:redo()
        revalidate()
        say(label and ("Redid " .. label:lower()) or "Nothing to redo")
    end

    function commands.focus()
        local sel = s.sel
        if not sel then return say("Select a prop first") end
        local center, extent = bounds(sel.component)
        if not center then return end
        local radius = math.sqrt(extent.X ^ 2 + extent.Y ^ 2 + extent.Z ^ 2)
        local forward = s.rig:GetActorForwardVector()
        local at = sub(center, mul(v(forward.X, forward.Y, forward.Z), math.max(150, radius * 2.5)))
        s.rig:K2_SetActorLocation(at, false, {}, true)
    end

    function commands.snap()
        self.snap = self.snap % #M.SNAPS + 1
        local step = M.SNAPS[self.snap]
        say(step == 0 and "Grid snap off" or ("Grid snap " .. step .. " cm"))
    end

    function commands.reach()
        self.reach = self.reach % #M.REACHES + 1
        say("Clicks reach %d m", math.floor(M.REACHES[self.reach] / 100))
    end

    function commands.lock()
        self.unlocked = not self.unlocked
        s.facts = {}
        say(self.unlocked and "Structure unlocked: walls, floors and girders can be edited" or "Structure locked")
    end

    function commands.save()
        local ok, err = store:save(watch.scope, watch.campaign, s.doc)
        if not ok then return say("Save failed: %s", tostring(err)) end
        s.history:mark_saved()
        watch:adopt(s.doc)
        say("Saved")
        return true
    end

    function commands.exit()
        if s.drag then end_drag(true) end
        if s.history:dirty() then confirm(true) else self:close("closed") end
    end

    function commands.back()
        if s.drag then return end_drag(true) end
        if s.confirming then return confirm(false) end
        if s.sel then select(nil); return say("") end
        commands.exit()
    end

    function commands.confirm_save() if commands.save() then self:close("saved") end end
    function commands.confirm_discard() self:close("discarded", true) end
    function commands.confirm_cancel() confirm(false) end

    ---------------------------------------------------------------------------------------------- input --
    local input_mode = {}
    function input_mode.ui()
        local wbl = StaticFindObject(WBL)
        pcall(function() wbl:SetInputMode_GameAndUIEx(s.pc, nil, 0, false, false) end)
        s.pc.bShowMouseCursor = true
    end
    function input_mode.captured()
        local wbl = StaticFindObject(WBL)
        s.pc.bShowMouseCursor = false
        pcall(function() wbl:SetInputMode_GameOnly(s.pc, false) end)
    end

    local function on_action(name, value)
        if name == "look_hold" then
            -- Holding RMB hides and captures the cursor, so a turn can go on forever.
            s.looking = value > 0.5
            if s.looking then input_mode.captured() else input_mode.ui() end
            if s.hover then highlight:clear(s.hover); s.hover = nil end
            return
        end
        if s.confirming and name ~= "back" then return end
        if name == "select" then
            if value > 0.5 then
                local o, d = cursor_ray()
                if not o then return end
                local f, hit = pick(o, d)
                if not f then select(nil); return say("") end
                if not f.ok then select(nil); return say("Can't edit that: %s", f.reason) end
                if not (s.sel and s.sel.key == f.key) then select(f, hit.component) end
                s.press = { dir = d }
                say("")
            else
                s.press = nil
                if s.drag then end_drag(false) end
            end
            return
        end
        if name == "rotate" or name == "rotate_fine" or name == "scale" then
            local steps = value >= 0 and math.floor(value + 0.5) or -math.floor(-value + 0.5)
            if steps ~= 0 then commands[name](steps) end
            return
        end
        local command = commands[name]
        if command then command() end
    end

    local function on_tick()
        s.frame = s.frame + 1
        if s.looking or s.confirming then return end
        local o, d = cursor_ray()
        if not o then return end
        if s.press and not s.drag and s.sel and math.acos(math.max(-1, math.min(1, dot(d, s.press.dir)))) > M.DRAG_START then
            begin_drag(o, d)
        end
        if s.drag then return update_drag(o, d) end
        -- Hover outline, every other frame.
        if s.press or s.frame % 2 == 1 then return end
        local f, hit = pick(o, d)
        local component = f and f.ok and hit.component or nil
        if component and s.sel and g.path(component) == g.path(s.sel.component) then component = nil end
        local hover_path = s.hover and g.path(s.hover)
        local new_path = component and g.path(component)
        if hover_path ~= new_path then
            if s.hover then highlight:clear(s.hover) end
            s.hover = component
            if component then highlight:set(component, Highlight.HOVER) end
        end
    end

    local function guarded(fn)
        return function(...)
            local ok, err = pcall(fn, ...)
            if not ok then log("ERROR: editor | %s", tostring(err)) end
        end
    end

    local function ours(context)
        local rig = g.unwrap(context)
        return self.active and g.valid(rig) and g.valid(s.rig) and g.path(rig) == g.path(s.rig)
    end

    local function hook()
        if hooked then return end
        runtime:register_hook(RIG_CLASS .. ":Lua_Action", guarded(function(rig, name, value)
            if ours(rig) then on_action(str(name), num(value)) end
        end))
        runtime:register_hook(RIG_CLASS .. ":Lua_Vector", guarded(function(rig, name, value)
            if not ours(rig) or s.confirming then return end
            local vec = value:get()
            if str(name) == "nudge" then commands.nudge(v(vec.X, vec.Y, vec.Z)) end
        end))
        runtime:register_hook(RIG_CLASS .. ":Lua_Tick", guarded(function(rig)
            if ours(rig) then on_tick() end
        end))
        runtime:register_hook(TOOLBAR_CLASS .. ":Lua_Event", guarded(function(widget, name)
            if not self.active then return end
            local event = str(name)
            if s.confirming and not event:match("^confirm_") then return end
            local command = commands[event]
            if command then command() end
        end))
        hooked = true
    end

    ------------------------------------------------------------------------------------------- lifecycle --
    local function why_not()
        if self.active then return "already open" end
        if not watch.world or not watch.layout then return "only in the Den" end
        if apply.busy then return "the Den layout is still loading" end
        local context = g.any_context()
        local pc = context and (g.call(g.gameplay(), "GetPlayerController", context, 0))
        if not g.valid(pc) then return "no player" end
        local view = (g.call(pc, "GetViewTarget"))
        if not (g.valid(view) and g.full_name(view):match("^%S*Camroid")) then return "only while walking around the Den" end
        return nil, pc
    end

    function self:open()
        local why, pc = why_not()
        if why then log("Editor | can't open: %s", why); return false, why end
        local rig_class, toolbar_class = g.load_class(RIG_CLASS), g.load_class(TOOLBAR_CLASS)
        local imc = g.load_object(IMC)
        if not (rig_class and toolbar_class and imc) then
            log("ERROR: editor | kit assets missing (is ~mods/ZComDen_P installed?)")
            return false, "kit assets missing"
        end
        hook()
        reset_session()
        s.pc = pc
        local context = g.any_context()
        local cm = pc.PlayerCameraManager
        local at, rot = cm:GetCameraLocation(), cm:GetCameraRotation()
        local xf = g.xform(v(at.X, at.Y, at.Z), rot.Yaw)
        local deferred = (g.call(g.gameplay(), "BeginDeferredActorSpawnFromClass", context, rig_class, xf, 1, nil, 1))
        local rig = deferred and (g.call(g.gameplay(), "FinishSpawningActor", deferred, xf, 1))
        if not g.valid(rig) then log("ERROR: editor | rig spawn failed"); return false, "spawn failed" end
        rig:K2_SetActorRotation({ Pitch = rot.Pitch, Yaw = rot.Yaw, Roll = 0 }, true)
        s.rig = rig
        s.view_was = pc:GetViewTarget()
        pc:SetViewTargetWithBlend(rig, 0.3, 0, 0, false)
        if g.path(pc:GetViewTarget()) ~= g.path(rig) then
            pcall(function() rig:K2_DestroyActor() end)
            log("ERROR: editor | the camera manager refused the rig")
            return false, "camera refused"
        end
        self.active = true
        s.click_was, s.over_was, s.cursor_was = pc.bEnableClickEvents, pc.bEnableMouseOverEvents, pc.bShowMouseCursor
        pc.bEnableClickEvents, pc.bEnableMouseOverEvents = false, false
        rig:EnableInput(pc)
        s.sub, s.imc = FindFirstOf("EnhancedInputLocalPlayerSubsystem"), imc
        s.sub:AddMappingContext(imc, IMC_PRIORITY, IMC_OPTIONS)
        input_mode.ui()
        local wbl = StaticFindObject(WBL)
        s.widget = wbl:Create(pc, toolbar_class, pc)
        if g.valid(s.widget) then s.widget:AddToViewport(50) end
        s.doc = Layout.copy(watch.layout)
        s.history = History.new(s.doc, {
            vanilla = function(key, edit) return apply:set_vanilla(key, s.objects[key], edit) end,
            placed = function(id, entry) return apply:set_placed(id, entry) end,
        })
        watch.paused = true
        rig.bLuaTick = true
        say("Click a prop to select it; drag to move it. Esc or Exit to leave.")
        log("Editor | opened (%s layout)", watch.scope)
        return true
    end

    -- Leaves edit mode. discard: put the Den back as the saved layout has it.
    function self:close(reason, discard)
        if not self.active then return end
        self.active = false
        local dirty = s.history and s.history:dirty()
        highlight:clear_all()
        pcall(function() s.rig.bLuaTick = false end)
        pcall(function() s.widget:RemoveFromParent() end)
        pcall(function() s.sub:RemoveMappingContext(s.imc, IMC_OPTIONS) end)
        local pc = s.pc
        if g.valid(pc) then
            pcall(function()
                pc.bEnableClickEvents, pc.bEnableMouseOverEvents = s.click_was, s.over_was
                local view = g.valid(s.view_was) and s.view_was or FindFirstOf("BR_Camroid_Explore_Pro_B_C")
                pc:SetViewTargetWithBlend(view, 0.3, 0, 0, false)
            end)
            pcall(function()
                local wbl = StaticFindObject(WBL)
                if s.cursor_was then wbl:SetInputMode_GameAndUIEx(pc, nil, 0, false, false); pc.bShowMouseCursor = true
                else wbl:SetInputMode_GameOnly(pc, false); pc.bShowMouseCursor = false end
            end)
        end
        pcall(function() s.rig:K2_DestroyActor() end)
        watch.paused = false
        if discard and dirty then watch:reload("edits discarded") end
        log("Editor | closed (%s)", reason)
        reset_session()
    end

    -- The world went away under us: drop everything without touching the old world, except the input mapping,
    -- which lives on the local player.
    function self:abort(reason)
        if not self.active then return end
        self.active = false
        highlight:forget()
        pcall(function() s.sub:RemoveMappingContext(s.imc, IMC_OPTIONS) end)
        pcall(function() if g.valid(s.widget) then s.widget:RemoveFromParent() end end)
        watch.paused = false
        log("Editor | closed (%s); unsaved changes were dropped", reason)
        reset_session()
    end

    function self:toggle()
        if self.active then
            if s.confirming then return confirm(false) end
            return commands.exit()
        end
        self:open()
    end

    function self:install(key, modifiers)
        runtime:register_keybind(key, modifiers, function()
            ExecuteInGameThread(guarded(function() self:toggle() end))
        end)
        local prior = ctx.runtime.on_teardown
        ctx.runtime.on_teardown = function(reason)
            ExecuteInGameThread(function() pcall(function() self:close(reason) end) end)
            if prior then prior(reason) end
        end
    end

    return self
end

return M
