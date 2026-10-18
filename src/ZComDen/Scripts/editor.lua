-- Den Designer: edit mode. Ctrl+Home in the Den opens it: a flying camera (BP_DenEditorRig, a kit asset that
-- flies itself from its own input actions), the toolbar (WBP_DenToolbar) and the editor's mapping context, which
-- outranks the game's so Hawks stays put. The kit assets call empty Lua_* functions that we pre-hook here.
--
-- Edits go to a working copy of the layout through history.lua (undo/redo) and to the Den through apply.lua.
-- Nothing reaches the layout file until Save; leaving without saving reapplies the file.
-- Tab opens the catalog (WBP_DenCatalog): picking a mesh there attaches a preview ("ghost") to the cursor until
-- a click places it.
local Catalog = require("catalog")
local Thumbs = require("thumbs")
local History = require("history")
local Layout = require("layout")
local Pick = require("pick")
local Highlight = require("highlight")
local Resolve = require("resolve")
local Keys = require("keys")
local json = require("json")
local M = {}
local nargs = function(...) return select("#", ...) end  -- the editor's own select() (selection) shadows Lua's below

-- The kit assets' own package names. The pak also remaps them onto /Game/ZComDen/..., but loading them by that
-- name gives a second copy of each class, distinct from the one the assets reference internally: an entry
-- widget's cast to BP_DenCatalogItem then fails for items Lua built from the /Game copy (seen 2026-10-18).
local KIT = "/ZComDen/ZComDen/Editor/"
local RIG_CLASS = KIT .. "BP_DenEditorRig.BP_DenEditorRig_C"
local TOOLBAR_CLASS = KIT .. "WBP_DenToolbar.WBP_DenToolbar_C"
local CATALOG_CLASS = KIT .. "WBP_DenCatalog.WBP_DenCatalog_C"
local ITEM_CLASS = KIT .. "BP_DenCatalogItem.BP_DenCatalogItem_C"
local LAYOUTS_CLASS = KIT .. "WBP_DenLayouts.WBP_DenLayouts_C"
local STOREROOM_CLASS = KIT .. "WBP_DenStoreroom.WBP_DenStoreroom_C"
local TRANSFORM_CLASS = KIT .. "WBP_DenTransform.WBP_DenTransform_C"
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
M.SEARCH_DELAY = 150                -- ms after the last keystroke before the catalog searches
M.GHOST_DISTANCE = 500              -- cm in front of the camera when nothing is under the cursor
M.REFRESH_MS = 250                  -- catalog tiles redraw at most this often while pictures arrive
M.DRAFT_MS = 2000                   -- the unsaved session is written this long after the last change
M.CONFIRM_SECONDS = 5               -- a second click within this confirms a destructive button

-- Small vector helpers on {X, Y, Z} tables.
local function v(x, y, z) return { X = x, Y = y, Z = z } end
local function add(a, b) return v(a.X + b.X, a.Y + b.Y, a.Z + b.Z) end
local function sub(a, b) return v(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
local function mul(a, k) return v(a.X * k, a.Y * k, a.Z * k) end
local function dot(a, b) return a.X * b.X + a.Y * b.Y + a.Z * b.Z end
local function arr(a) return { a.X, a.Y, a.Z } end
local function round_to(x, step) return math.floor(x / step + 0.5) * step end
local function wrap(deg) deg = deg % 360; if deg > 180 then deg = deg - 360 end; return deg end

-- Where a ray enters a box (center, half extents), as a distance along it, or nil if it misses.
local function ray_box(o, d, center, extent)
    local near, far = 0, M.TRACE
    for _, k in ipairs({ "X", "Y", "Z" }) do
        local lo, hi = center[k] - extent[k], center[k] + extent[k]
        if math.abs(d[k]) < 1e-8 then
            if o[k] < lo or o[k] > hi then return nil end
        else
            local t1, t2 = (lo - o[k]) / d[k], (hi - o[k]) / d[k]
            if t1 > t2 then t1, t2 = t2, t1 end
            near, far = math.max(near, t1), math.min(far, t2)
            if near > far then return nil end
        end
    end
    return near
end

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
    -- catalog: loaded on first use and kept (with its Recent shelf) for the rest of the game.
    local self = { active = false, snap = 1, reach = 2, unlocked = false, autosave = true, catalog = nil }
    local highlight = Highlight.new(g)
    local thumbs = Thumbs.new(ctx, store.base .. "\\thumbs")
    local hooked = {}  -- paths hooked for this session
    -- Per-session state, reset by reset_session().
    local s

    local function reset_session()
        s = { pc = nil, rig = nil, widget = nil, sub = nil, imc = nil, view_was = nil, cursor_was = false,
              click_was = true, over_was = true, doc = nil, history = nil, objects = {}, facts = {},
              sel = nil, hover = nil, press = nil, drag = nil, looking = false, frame = 0, message = "",
              panel = nil, shelf = nil, ghost = nil, serial = 0, side = nil, notes = {} }
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

    local update_transform, history_changed, apply_settings, rebind

    local function refresh()
        if not s.doc then return end
        if update_transform then pcall(update_transform) end
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

    -- The first thing under the cursor within reach. Placed meshes without a collision body can't be traced, so
    -- they're tested by their bounds.
    local function pick(o, d)
        local reach = M.REACHES[self.reach]
        local hit = trace(o, d, nil, reach)
        local nearest = hit and math.sqrt(dot(sub(hit.point, o), sub(hit.point, o))) or reach
        for id, record in pairs(apply.placed) do
            if record.box_pick and id ~= "ghost" and g.valid(record.component) then
                local center, extent = bounds(record.component)
                local t = center and ray_box(o, d, center, extent)
                if t and t < nearest then
                    nearest = t
                    hit = { component = record.component, point = add(o, mul(d, t)), normal = v(0, 0, 1) }
                end
            end
        end
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
        s.facts = {}
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
        if not o then
            -- Not tracked yet (or no longer): track it now; failing that, where it stands right now.
            apply:track(sel.key, sel.object)
            o = apply:original(sel.key)
            if not o then
                local loc, rot, scale = apply:transform(sel.object)
                o = { loc = loc, rot = rot, scale = scale }
            end
        end
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
        -- Spawned meshes reuse actor names (Actor_N): what a cached path was may have changed.
        s.facts = {}
        local ok, why = s.history:commit(label, { { sel.kind, sel.key, state } }, merge)
        if not ok then say("%s failed: %s", label, tostring(why)) end
        revalidate()
        history_changed()
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

    -------------------------------------------------------------------------------------- ghost placing --
    local update_ghost
    local function cancel_ghost()
        local ghost = s.ghost
        if not ghost then return end
        s.ghost = nil
        if ghost.lit then highlight:clear(ghost.lit) end
        apply:set_placed("ghost", nil)
        s.facts = {}
    end

    -- Attaches a preview of `path` to the cursor.
    local function start_ghost(path)
        cancel_ghost()
        select(nil)
        local mesh = g.load_object(path)
        if not mesh then return say("Can't load %s", Catalog.name_of(path)) end
        local bounds_ = (g.call(mesh, "GetBounds"))
        local bottom = bounds_ and (bounds_.Origin.Z - bounds_.BoxExtent.Z) or 0
        -- Facing the camera, squared to the grid.
        local yaw = wrap(round_to(s.rig:K2_GetActorRotation().Yaw, 90) + 180)
        s.ghost = { entry = { id = "ghost", ghost = true, mesh = path, t = { 0, 0, 0 }, r = { 0, yaw, 0 }, s = { 1, 1, 1 } },
                    bottom = bottom, name = Catalog.name_of(path) }
        if self.catalog then
            self.catalog:remember(path)
            if g.valid(s.recent_item) then
                s.recent_item.Title = string.format("Recent (%d)", #self.catalog.recent)
                pcall(function() s.panel.Shelves:RegenerateAllEntries() end)
            end
        end
        say("Placing %s: click to place it (Shift+click: place more), wheel turns it, Esc cancels", s.ghost.name)
        -- Spawn now: from here on the preview holds the mesh, so the per-frame updates (inside the rig's Tick,
        -- where a blocking load could deadlock) only ever move it.
        local o, d = cursor_ray()
        if o then update_ghost(o, d) end
    end

    function update_ghost(o, d)
        local ghost = s.ghost
        local hit = trace(o, d, nil, M.REACHES[self.reach])
        local p = snap_xy(hit and hit.point or add(o, mul(d, M.GHOST_DISTANCE)))
        local e = ghost.entry
        e.t = { p.X, p.Y, p.Z - ghost.bottom * e.s[3] }
        local ok, why = apply:set_placed("ghost", e)
        if not ok then
            cancel_ghost()
            return say("Can't place that: %s", tostring(why))
        end
        local record = apply.placed.ghost
        if record and record.component and not ghost.lit then
            highlight:set(record.component, Highlight.HOVER)
            ghost.lit = record.component
        end
    end

    local function place_ghost(more)
        local ghost = s.ghost
        if not ghost.lit then return end  -- not shown yet
        local e = Layout.copy(ghost.entry)
        e.ghost, e.id = nil, Layout.next_id(s.doc)
        local entry = Layout.normalise({ placed = { e } }).placed[1]
        if not entry then return say("Can't place that") end
        if not commit("Place", { kind = "placed", key = entry.id }, entry) then return end
        if more then return say("Placed %s; click to place another, Esc to stop", ghost.name) end
        cancel_ghost()
        local record = apply.placed[entry.id]
        if record and g.valid(record.component) then
            select({ kind = "placed", key = entry.id, object = record.actor, label = Catalog.name_of(entry.mesh), mesh = entry.mesh },
                record.component)
        end
        say("Placed %s", ghost.name)
    end

    ------------------------------------------------------------------------------------------- catalog --
    local function panel_text(field, value)
        pcall(function() s.panel[field]:SetText(FText(value)) end)
    end

    local function list_item(key, title, detail, outer)
        s.serial = s.serial + 1
        local item = StaticConstructObject(s.item_class, outer or s.panel, FName("DenCatalogItem_" .. s.serial), 0, 0, false, false, nil)
        item.Key, item.Title, item.Detail = key, title, detail
        return item
    end

    -- Pictures arrive one by one: redraw the visible tiles at most every REFRESH_MS.
    local function refresh_tiles()
        if s.tiles_pending then return end
        s.tiles_pending = true
        actions:schedule_after("den-input", M.REFRESH_MS, function()
            s.tiles_pending = false
            pcall(function() if g.valid(s.panel) then s.panel.Items:RegenerateAllEntries() end end)
        end)
    end

    local function show_items(indices, footer)
        local list = s.panel.Items
        list:ClearListItems()
        thumbs:forget_queue()
        for _, i in ipairs(indices) do
            local item = self.catalog:item(i)
            local entry = list_item(item.path, item.name, Catalog.size_text(item.size) .. (item.solid and "" or "\nno collision"))
            local picture = thumbs:loaded(item.path)
            if picture then
                entry.Thumb = picture
            else
                thumbs:request(item.path, function(_, texture)
                    if g.valid(entry) then entry.Thumb = texture; refresh_tiles() end
                end)
            end
            list:AddItem(entry)
        end
        panel_text("Footer", footer .. "\nClick a mesh, then click in the Den to place it. Shift+click places more; Esc cancels.")
    end

    local function show_shelf(key)
        s.shelf = key
        local indices = self.catalog:shelf_items(key)
        local title = key == "recent" and "Recent" or self.catalog.shelves[tonumber(key)].title
        show_items(indices, string.format("%s: %d mesh%s", title, #indices, #indices == 1 and "" or "es"))
    end

    local function fill_shelves()
        local list = s.panel.Shelves
        list:ClearListItems()
        s.recent_item = list_item("recent", string.format("Recent (%d)", #self.catalog.recent), "")
        list:AddItem(s.recent_item)
        for _, shelf in ipairs(self.catalog.shelves) do
            list:AddItem(list_item(shelf.key, string.format("%s (%d)", shelf.title, shelf.count), ""))
        end
    end

    local function search(text)
        actions:cancel_group("den-search", "new search")
        actions:schedule_after("den-search", M.SEARCH_DELAY, function()
            if not (self.active and g.valid(s.panel)) then return end
            local ok, err = pcall(function()
                if text:match("^%s*$") then return show_shelf(s.shelf or "1") end
                local found, total = self.catalog:search(text)
                show_items(found, total > #found and string.format("%d matches for \"%s\" (showing %d)", total, text, #found)
                    or string.format("%d match%s for \"%s\"", total, total == 1 and "" or "es", text))
            end)
            if not ok then log("ERROR: editor | search | %s", tostring(err)) end
        end)
    end

    local function set_visible(widget, on)
        pcall(function() widget:SetVisibility(on and VISIBLE or COLLAPSED) end)
    end

    local function create(class, z)
        local w = StaticFindObject(WBL):Create(s.pc, class, s.pc)
        if not g.valid(w) then return nil end
        w:AddToViewport(z)
        return w
    end

    local function open_catalog()
        if not self.catalog then
            local t0 = os.clock()
            self.catalog = Catalog.new()
            log("Editor | catalog loaded: %d meshes on %d shelves in %.0f ms", self.catalog.count,
                #self.catalog.shelves, (os.clock() - t0) * 1000)
        end
        if not g.valid(s.panel) then return false end
        local fresh = not s.catalog_filled
        s.catalog_filled = true
        fill_shelves()
        if fresh then show_shelf(#self.catalog.recent > 0 and "recent" or "1") end
        return true
    end

    ------------------------------------------------------------------------------- whole-layout changes --
    local resolver = Resolve.new(g)

    -- Vanilla objects the editor hasn't touched yet (from a preset or a draft): one bulk scan finds them.
    local function ensure_objects(keys)
        local want = {}
        for _, key in ipairs(keys) do
            if not apply.edits[key] and not s.objects[key] then want[#want + 1] = key end
        end
        if #want == 0 then return end
        local found = resolver.find(want, g.any_context())
        for key, object in pairs(found) do s.objects[key] = object end
    end

    local function same(a, b) return json.encode(a) == json.encode(b) end

    -- Makes the working layout equal `target` as one undo step; returns how many entries changed and how many
    -- the Den couldn't show (objects it hasn't loaded).
    local function replace_layout(label, target)
        local changes, keys, seen = {}, {}, {}
        for key, e in pairs(s.doc.vanilla) do
            seen[key] = true
            if not same(e, target.vanilla[key]) then changes[#changes + 1] = { "vanilla", key, target.vanilla[key] } end
        end
        for key, e in pairs(target.vanilla) do
            if not seen[key] then changes[#changes + 1] = { "vanilla", key, e } end
        end
        for _, c in ipairs(changes) do keys[#keys + 1] = c[2] end
        local wanted = {}
        for _, e in ipairs(target.placed) do wanted[e.id] = true end
        for _, e in ipairs(s.doc.placed) do
            if not wanted[e.id] then changes[#changes + 1] = { "placed", e.id, nil } end
        end
        for _, e in ipairs(target.placed) do
            if not same(s.history:get("placed", e.id), e) then changes[#changes + 1] = { "placed", e.id, e } end
        end
        if #changes == 0 then return 0, 0 end
        ensure_objects(keys)
        if s.sel then select(nil) end
        cancel_ghost()
        s.facts = {}
        s.history:commit(label, changes)
        local absent = 0
        for _, key in ipairs(keys) do
            if s.doc.vanilla[key] and not apply.edits[key] then absent = absent + 1 end
        end
        revalidate()
        history_changed()
        return #changes, absent
    end

    -- A destructive button needs a second click within CONFIRM_SECONDS.
    local function twice(tag)
        if s.armed == tag and os.clock() - s.armed_at <= M.CONFIRM_SECONDS then s.armed = nil; return true end
        s.armed, s.armed_at = tag, os.clock()
        return false
    end

    ------------------------------------------------------------------------------------------- layouts --
    local function note(panel, fmt, ...)
        s.notes[panel] = nargs(...) > 0 and string.format(fmt, ...) or fmt
        local w = s[panel]
        if g.valid(w) then pcall(function() w.Footer:SetText(FText(s.notes[panel])) end) end
        if s.notes[panel] ~= "" then log("Editor | %s", s.notes[panel]) end
    end

    local function refresh_layouts()
        local w = s.layouts
        if not g.valid(w) then return end
        local scope_text, button
        if not watch.campaign then
            scope_text, button = "This campaign couldn't be identified (it hasn't been saved yet), so only the home layout "
                .. "is available.", "Give this campaign its own layout"
        elseif watch.scope == "campaign" then
            scope_text, button = "This campaign has its own layout. Every other campaign uses the home layout.",
                "Use the home layout again"
        else
            scope_text, button = "This campaign uses the home layout, which every campaign without its own layout shares.",
                "Give this campaign its own layout"
        end
        pcall(function() w.ScopeText:SetText(FText(scope_text)) end)
        pcall(function() w.ScopeLabel:SetText(FText(button)) end)
        local list = w.Presets
        list:ClearListItems()
        for _, name in ipairs(store:presets()) do
            list:AddItem(list_item(name, (name == s.preset and "> " or "") .. name, "", w))
        end
        pcall(function() w.Footer:SetText(FText(s.notes.layouts or "")) end)
    end

    -- Closes the editor, lets the watch apply the layout file again, then opens the editor on it.
    local function reopen(side)
        self:close("switching layout")
        watch:reload("layout switched")
        local tries = 0
        local function try()
            tries = tries + 1
            if not apply.busy and watch.layout and not self.active then
                if self:open() and side then self.show_side(side) end
            elseif tries < 150 then
                actions:schedule_after("den-reopen", 200, try)
            end
        end
        actions:schedule_after("den-reopen", 200, try)
    end

    -------------------------------------------------------------------------------------------- storeroom --
    local function vanilla_mesh(key)
        local original = apply:original(key)
        local e = s.doc.vanilla[key]
        return (original and original.mesh) or (e and e.fp and e.fp.mesh) or nil
    end

    local function refresh_storeroom()
        local w = s.storeroom
        if not g.valid(w) then return end
        local stored, dormant = {}, {}
        for key, e in pairs(s.doc.vanilla) do
            if not apply.edits[key] and not s.objects[key] then dormant[#dormant + 1] = key
            elseif e.hidden then stored[#stored + 1] = key end
        end
        table.sort(stored); table.sort(dormant)
        local list = w.Stored
        list:ClearListItems()
        for _, key in ipairs(stored) do
            local mesh = vanilla_mesh(key)
            local e = s.doc.vanilla[key]
            local item = list_item(key, Pick.label(mesh, key), (e.t or e.r or e.s) and "moved, then stored" or "stored", w)
            if mesh then
                local picture = thumbs:loaded(mesh)
                if picture then item.Thumb = picture
                else
                    thumbs:request(mesh, function(_, texture)
                        if g.valid(item) then
                            item.Thumb = texture
                            pcall(function() if g.valid(w) then w.Stored:RegenerateAllEntries() end end)
                        end
                    end)
                end
            end
            list:AddItem(item)
        end
        pcall(function() w.StoredText:SetText(FText(#stored == 0 and "Nothing stored. Select a prop and press X to store it."
            or string.format("%d stored prop%s. Click one to put it back.", #stored, #stored == 1 and "" or "s"))) end)
        local dl = w.Dormant
        dl:ClearListItems()
        for _, key in ipairs(dormant) do
            local e = s.doc.vanilla[key]
            local what = e.hidden and "stored" or "moved"
            dl:AddItem(list_item(key, Pick.label(vanilla_mesh(key) or key:match("([^%.:]+)$"), key) .. "  - " .. what, "", w))
        end
        pcall(function() w.DormantText:SetText(FText(#dormant == 0 and "Every edit in this layout found its object."
            or string.format("%d edit%s found no object in this Den: the Den changes as the story goes on, and a patch can "
                .. "rename things. They stay in the layout and apply when their object appears. Click one to forget it.",
                #dormant, #dormant == 1 and " has" or "s have"))) end)
        pcall(function() w.Footer:SetText(FText(s.notes.storeroom or "")) end)
    end

    ---------------------------------------------------------------------------------------------- side --
    -- The catalog, the storeroom and the layouts share the right of the screen: one at a time.
    local SIDES = { "catalog", "storeroom", "layouts" }
    function self.show_side(name)
        local opening = s.side ~= name
        for _, side in ipairs(SIDES) do
            local w = side == "catalog" and s.panel or s[side]
            if g.valid(w) then set_visible(w, false) end
        end
        s.side = nil
        if not opening then return end
        if name == "catalog" then
            if not open_catalog() then return say("The catalog didn't open") end
            set_visible(s.panel, true)
        else
            if not g.valid(s[name]) then
                s[name] = create(s.classes[name], 40)
                if not s[name] then return say("The %s panel didn't open", name) end
            end
            set_visible(s[name], true)
            if name == "layouts" then refresh_layouts() else refresh_storeroom() end
        end
        s.side = name
    end

    ---------------------------------------------------------------------------------------------- transform --
    local FIELDS = { X = { "t", 1 }, Y = { "t", 2 }, Z = { "t", 3 }, Pitch = { "r", 1 }, Yaw = { "r", 2 }, Roll = { "r", 3 },
                     Scale = { "s", 1 } }

    local function number_text(x, decimals)
        local text = string.format("%." .. decimals .. "f", x):gsub("%.?0+$", "")
        return text == "-0" and "0" or text
    end

    function update_transform()
        local w = s.transform
        if not g.valid(w) then return end
        if not s.sel then return set_visible(w.Panel, false) end
        set_visible(w.Panel, true)
        local t, r, sc = pose(s.sel)
        local parts = { t = t, r = r, s = sc }
        for name, field in pairs(FIELDS) do
            local box = w["Field" .. name]
            if g.valid(box) and not box:HasKeyboardFocus() then
                box:SetText(FText(number_text(parts[field[1]][field[2]], name == "Scale" and 2 or 1)))
            end
        end
    end

    local function set_field(name, text)
        local sel = s.sel
        if not sel then return end
        local value = tonumber((tostring(text or ""):gsub(",", ".")))
        if not value or value ~= value then update_transform(); return say("%s needs a number", name) end
        local field = FIELDS[name]
        local t, r, sc = pose(sel)
        local current = ({ t = t, r = r, s = sc })[field[1]][field[2]]
        if math.abs(current - value) < 1e-4 then return end
        local state = changed(sel, function(st)
            if field[1] == "t" then st.t = { t[1], t[2], t[3] }; st.t[field[2]] = value
            elseif field[1] == "r" then st.r = { r[1], r[2], r[3] }; st.r[field[2]] = wrap(value)
            else local k = math.max(0.05, math.min(20, value)); st.s = { k, k, k } end
        end)
        commit("Edit " .. name, sel, state)
        say("Set %s to %s", name, number_text(value, 2))
    end

    ------------------------------------------------------------------------------------------------ draft --
    local function write_draft()
        if not (self.active and s.history) then return end
        if s.history:dirty() then
            local ok, err = store:save_draft(watch.scope, watch.campaign, s.doc)
            if not ok then log("WARNING: editor | draft not saved: %s", tostring(err)) end
        else
            store:clear_draft(watch.scope, watch.campaign)
        end
    end

    function history_changed()
        s.facts = {}
        if s.side == "storeroom" then pcall(refresh_storeroom) end
        if not self.autosave then return end
        s.draft_due = os.clock() + M.DRAFT_MS / 1000
        if s.draft_pending then return end
        s.draft_pending = true
        local function check()
            if not self.active then return end
            if os.clock() < s.draft_due then return actions:schedule_after("den-draft", 250, check) end
            s.draft_pending = false
            pcall(write_draft)
        end
        actions:schedule_after("den-draft", M.DRAFT_MS, check)
    end

    ------------------------------------------------------------------------------------------- commands --
    local commands = {}

    function commands.rotate(steps, step)
        if s.ghost then
            local r = s.ghost.entry.r
            r[2] = wrap(r[2] + steps * (step or M.ROTATE_STEP))
            return
        end
        local sel = s.sel
        if not sel then return say("Select a prop first") end
        local _, r = pose(sel)
        local yaw = wrap(r[2] + steps * (step or M.ROTATE_STEP))
        commit("Rotate", sel, changed(sel, function(st) st.r = { r[1], yaw, r[3] } end), "rotate")
        say("Rotated to %.0f degrees", yaw)
    end

    function commands.rotate_fine(steps) commands.rotate(steps, M.FINE_STEP) end

    function commands.scale(steps)
        if s.ghost then
            local k = math.max(0.05, math.min(20, s.ghost.entry.s[1] * M.SCALE_STEP ^ steps))
            s.ghost.entry.s = { k, k, k }
            return
        end
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
                mats[#mats + 1] = p:match("^/[%w_]+/[^%.:]+%.[%w_%-]+$") and p or ""
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
        history_changed()
        say(label and ("Undid " .. label:lower()) or "Nothing to undo")
    end

    function commands.redo()
        local label = s.history:redo()
        revalidate()
        history_changed()
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
        actions:cancel_group("den-draft", "saved")
        store:clear_draft(watch.scope, watch.campaign)
        watch:adopt(s.doc)
        say("Saved")
        return true
    end

    function commands.exit()
        if s.drag then end_drag(true) end
        if s.history:dirty() then confirm(true) else self:close("closed") end
    end

    function commands.catalog() self.show_side("catalog") end
    function commands.storeroom() self.show_side("storeroom") end
    function commands.layouts() self.show_side("layouts") end

    function commands.scope()
        if not watch.campaign then return note("layouts", "This campaign can't have its own layout until it has been saved once.") end
        if watch.scope ~= "campaign" then
            local ok, err = store:make_campaign(watch.campaign, s.doc)
            if not ok then return note("layouts", "Couldn't create the campaign's layout: %s", tostring(err)) end
            store:clear_draft("home", nil)
            watch:adopt(s.doc)
            s.history:mark_saved()
            note("layouts", "This campaign now has its own layout, starting from what you see. Home is unchanged.")
            refresh_layouts()
            return refresh()
        end
        if s.history:dirty() and not twice("scope") then
            return note("layouts", "You have unsaved changes to this campaign's layout. Click again to drop them and go back to home.")
        end
        store:drop_campaign(watch.campaign)
        store:clear_draft("campaign", watch.campaign)
        s.notes.layouts = "Back on the home layout; the campaign's copy is in backups."
        reopen("layouts")
    end

    function commands.save_preset(name)
        local ok, err, saved = store:save_preset(name, s.doc)
        if not ok then return note("layouts", "Preset not saved: %s", tostring(err)) end
        s.preset = saved
        note("layouts", "Saved the preset \"%s\".", saved)
        refresh_layouts()
    end

    function commands.preset(name)
        s.preset = name
        note("layouts", "\"%s\" selected: Load puts it in the Den (Z undoes), Delete removes the file.", name)
        refresh_layouts()
    end

    function commands.load_preset()
        if not s.preset then return note("layouts", "Click a preset first.") end
        local layout, problems = store:load_preset(s.preset)
        if not layout then return note("layouts", "%s", (problems or {})[1] or "That preset couldn't be read.") end
        local n, absent = replace_layout("Load preset " .. s.preset, layout)
        if n == 0 then return note("layouts", "\"%s\" is what you already have.", s.preset) end
        note("layouts", "Loaded \"%s\": %d change%s%s. Save keeps it; Z undoes it.", s.preset, n, n == 1 and "" or "s",
            absent > 0 and string.format(" (%d waiting for objects this Den hasn't loaded)", absent) or "")
        refresh()
    end

    function commands.delete_preset()
        if not s.preset then return note("layouts", "Click a preset first.") end
        if not twice("delete " .. s.preset) then
            return note("layouts", "Click Delete again to delete \"%s\" (it can't be undone).", s.preset)
        end
        store:delete_preset(s.preset)
        note("layouts", "Deleted \"%s\".", s.preset)
        s.preset = nil
        refresh_layouts()
    end

    function commands.restore(key)
        local state = s.history:get("vanilla", key)
        if not state then return end
        state.hidden = nil
        if not (state.t or state.r or state.s) then state = nil end
        commit("Restore", { kind = "vanilla", key = key }, state)
        note("storeroom", "Put %s back.", Pick.label(vanilla_mesh(key), key))
        refresh_storeroom()
        refresh()
    end

    function commands.restore_all()
        local changes = {}
        for key, e in pairs(s.doc.vanilla) do
            if e.hidden and (apply.edits[key] or s.objects[key]) then
                local state = Layout.copy(e)
                state.hidden = nil
                if not (state.t or state.r or state.s) then state = nil end
                changes[#changes + 1] = { "vanilla", key, state }
            end
        end
        if #changes == 0 then return note("storeroom", "Nothing to restore.") end
        s.facts = {}
        s.history:commit("Restore everything", changes)
        revalidate()
        history_changed()
        note("storeroom", "Put %d prop%s back (Z undoes).", #changes, #changes == 1 and "" or "s")
        refresh_storeroom()
        refresh()
    end

    function commands.forget(key)
        if not s.doc.vanilla[key] then return end
        commit("Forget", { kind = "vanilla", key = key }, nil)
        note("storeroom", "Forgot the edit for %s.", Pick.label(vanilla_mesh(key) or key:match("([^%.:]+)$"), key))
        refresh_storeroom()
        refresh()
    end

    for name in pairs(FIELDS) do
        commands["set_" .. name:lower()] = function(text) set_field(name, text) end
    end

    function commands.back()
        if s.ghost then cancel_ghost(); return say("Placement cancelled") end
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
            if value > 0.5 and s.ghost then return place_ghost(s.rig.bFast == true) end
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
        if s.ghost then return update_ghost(o, d) end
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
            local ok, err = xpcall(fn, debug.traceback, ...)
            if not ok then log("ERROR: editor | %s", tostring(err)) end
        end
    end

    -- Kit events arrive inside the engine's own call (a Slate click, an input action). A blocking asset load
    -- there deadlocked the game (2026-10-18: clicking a catalog mesh froze it), so commands run a frame later,
    -- from the game thread's tick, where loads are safe (Phase 1 loads there).
    local function later(fn, ...)
        local args = { n = nargs(...), ... }
        actions:schedule_after("den-input", 0, function()
            if not self.active then return end
            local ok, err = xpcall(fn, debug.traceback, (table.unpack or unpack)(args, 1, args.n))
            if not ok then log("ERROR: editor | %s", tostring(err)) end
        end)
    end

    local function ours(context)
        local rig = g.unwrap(context)
        return self.active and g.valid(rig) and g.valid(s.rig) and g.path(rig) == g.path(s.rig)
    end

    -- Hooks live exactly as long as the editor session: a kit class nothing references gets garbage collected
    -- (its functions with it), so every panel is created when the editor opens, and the hooks go at close.
    local function register(path, fn)
        runtime:register_hook(path, fn)
        hooked[#hooked + 1] = path
    end

    local function unhook()
        for _, path in ipairs(hooked) do runtime:unregister_hook(path) end
        hooked = {}
    end

    local function hook()
        register(RIG_CLASS .. ":Lua_Action", guarded(function(rig, name, value)
            if not ours(rig) then return end
            local action = str(name)
            -- Cursor capture must follow the button at once; it never loads anything.
            if action == "look_hold" then on_action(action, num(value)) else later(on_action, action, num(value)) end
        end))
        register(RIG_CLASS .. ":Lua_Vector", guarded(function(rig, name, value)
            if not ours(rig) or s.confirming then return end
            local vec = value:get()
            if str(name) == "nudge" then later(commands.nudge, v(vec.X, vec.Y, vec.Z)) end
        end))
        register(RIG_CLASS .. ":Lua_Tick", guarded(function(rig)
            if ours(rig) then on_tick() end
        end))
        register(TOOLBAR_CLASS .. ":Lua_Event", guarded(function(widget, name)
            if not self.active then return end
            local event = str(name)
            if s.confirming and not event:match("^confirm_") then return end
            local command = commands[event]
            if command then later(command) end
        end))
        register(CATALOG_CLASS .. ":Lua_Event", guarded(function(widget, name, arg)
            if not self.active or s.confirming then return end
            local event, value = str(name), str(arg)
            if event == "search" then search(value)
            elseif event == "shelf" then later(show_shelf, value)
            elseif event == "item" then later(start_ghost, value) end
        end))
        for _, class in ipairs({ LAYOUTS_CLASS, STOREROOM_CLASS, TRANSFORM_CLASS }) do
            register(class .. ":Lua_Event", guarded(function(widget, name, arg)
                if not self.active or s.confirming then return end
                local command = commands[str(name)]
                if command then later(command, str(arg)) end
            end))
        end
    end

    ------------------------------------------------------------------------------------------- settings --
    local settings = ctx.settings or { Get = function(_, fallback) return fallback end }
    local function setting(key, fallback)
        local ok, value = pcall(settings.Get, key, fallback)
        if ok and value ~= nil then return value end
        return fallback
    end

    local function index_of(list, value, fallback)
        for i, x in ipairs(list) do if x == value then return i end end
        return fallback
    end

    -- Read when the editor opens: the MXM menu can change them at any time.
    function apply_settings()
        local rig = s.rig
        rig.Speed = tonumber(setting("fly_speed", 900)) or 900
        rig.FastMultiplier = tonumber(setting("fast_multiplier", 3)) or 3
        rig.LookRate = tonumber(setting("look_speed", 2.5)) or 2.5
        if not self.settings_applied then
            -- The toolbar buttons change these for the rest of the game; the settings are where each game starts.
            self.snap = index_of(M.SNAPS, tonumber(setting("snap", "0")), 1)
            self.reach = index_of(M.REACHES, tonumber(setting("reach", "2000")), 2)
            self.unlocked = setting("unlock_structure", false) == true
            self.settings_applied = true
        end
        self.autosave = setting("autosave", true) ~= false
        thumbs.enabled = setting("thumbnails", true) ~= false
    end

    -- Rewrites the keys of the editor's own mappings from the settings, in place (keeping each mapping's
    -- modifiers). The shipped keys are remembered the first time, so a binding can always be found again.
    function rebind(imc)
        local mappings = imc.Mappings
        local count = mappings:GetArrayNum()
        if not self.shipped_keys then
            self.shipped_keys = {}
            for i = 1, count do
                self.shipped_keys[i] = { action = g.name(mappings[i].Action), key = mappings[i].Key.KeyName:ToString() }
            end
        end
        local names, problems = Keys.plan(function(key) return setting(key, nil) end)
        for _, problem in ipairs(problems) do log("WARNING: keys | %s", problem) end
        local changed = 0
        for _, b in ipairs(Keys.BINDINGS) do
            for i = 1, count do
                local shipped = self.shipped_keys[i]
                if shipped and shipped.action == b[2] and shipped.key == b[3] then
                    local want = names[b[1]]
                    if mappings[i].Key.KeyName:ToString() ~= want then
                        mappings[i].Key.KeyName = FName(want)
                        changed = changed + 1
                    end
                end
            end
        end
        if changed > 0 then log("Editor | %d key%s rebound from the settings", changed, changed == 1 and "" or "s") end
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
        local classes = { catalog = g.load_class(CATALOG_CLASS), layouts = g.load_class(LAYOUTS_CLASS),
                          storeroom = g.load_class(STOREROOM_CLASS), transform = g.load_class(TRANSFORM_CLASS) }
        local item_class = g.load_class(ITEM_CLASS)
        local imc = g.load_object(IMC)
        local complete = rig_class and toolbar_class and item_class and imc
        for _, class in pairs(classes) do complete = complete and class end
        if not complete then
            log("ERROR: editor | kit assets missing (is ~mods/ZComDen_P installed?)")
            return false, "kit assets missing"
        end
        reset_session()
        s.pc, s.classes, s.item_class = pc, classes, item_class
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
        rebind(imc)
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
        s.transform = create(classes.transform, 45)
        -- Every panel exists (hidden) for the whole session: see hook().
        s.panel, s.layouts, s.storeroom = create(classes.catalog, 40), create(classes.layouts, 40), create(classes.storeroom, 40)
        for _, w in ipairs({ s.panel, s.layouts, s.storeroom }) do if w then set_visible(w, false) end end
        hook()
        apply_settings()
        watch.paused = true
        rig.bLuaTick = true
        say("Click a prop to select it; drag to move it. Esc or Exit to leave.")
        log("Editor | opened (%s layout)", watch.scope)
        -- A session that ended without Save or Discard (a crash, a reload) comes back as one undo step.
        local draft, at = store:load_draft(watch.scope, watch.campaign)
        if draft then
            local n, absent = replace_layout("Unsaved session", draft)
            if n > 0 then
                say("Restored your unsaved changes from %s (%d entr%s%s). Save keeps them; Z undoes them.", at, n,
                    n == 1 and "y" or "ies", absent > 0 and string.format(", %d waiting for their objects", absent) or "")
            else
                store:clear_draft(watch.scope, watch.campaign)
            end
        end
        return true
    end

    -- Leaves edit mode. discard: put the Den back as the saved layout has it.
    function self:close(reason, discard)
        if not self.active then return end
        self.active = false
        local dirty = s.history and s.history:dirty()
        actions:cancel_group("den-search", reason)
        actions:cancel_group("den-input", reason)
        actions:cancel_group("den-draft", reason)
        if s.history then
            -- Kept only when the session ends with changes neither saved nor discarded (a reload, a teardown).
            if dirty and not discard then
                self.active = true
                pcall(write_draft)
                self.active = false
            else
                store:clear_draft(watch.scope, watch.campaign)
            end
        end
        thumbs:stop(reason)
        cancel_ghost()
        highlight:clear_all()
        for _, w in ipairs({ s.panel, s.layouts, s.storeroom, s.transform }) do
            pcall(function() if g.valid(w) then w:RemoveFromParent() end end)
        end
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
        unhook()
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
        thumbs:forget()
        pcall(function() s.sub:RemoveMappingContext(s.imc, IMC_OPTIONS) end)
        pcall(function() if g.valid(s.widget) then s.widget:RemoveFromParent() end end)
        for _, w in ipairs({ s.panel, s.layouts, s.storeroom, s.transform }) do
            pcall(function() if g.valid(w) then w:RemoveFromParent() end end)
        end
        actions:cancel_group("den-search", reason)
        actions:cancel_group("den-draft", reason)
        unhook()
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

    -- `zcomden <what>` in the game console (also how tools/dd.py drives the editor in tests):
    --   open | close [save|discard] | do <command> [arg] | select <id or key> | mouse <x> <y> | click <x> <y> | state
    --   | reload
    local function console(words)
        local verb = words[1] or "state"
        if verb == "reload" then
            -- Development: rerun main.lua in this Lua state; the runtime tears this instance down first.
            log("Editor | console: reloading the mod")
            -- io.open, not dofile: UE4SS serves dofile a cached copy of the file.
            local f = assert(io.open(ctx.dir .. "main.lua", "rb"))
            local text = f:read("*a")
            f:close()
            return assert(load(text, "@" .. ctx.dir .. "main.lua"))()
        end
        if verb == "eval" then
            -- Development: run Lua in this mod's own state and log what it returns.
            local code = table.concat(words, " ", 2)
            local chunk, err = load("return " .. code)
            if not chunk then chunk, err = load(code) end
            if not chunk then return log("Editor | eval: %s", tostring(err)) end
            local results = table.pack(pcall(chunk))
            local out = {}
            for i = 1, results.n do out[#out + 1] = tostring(results[i]) end
            return log("Editor | eval: %s", table.concat(out, "  "))
        end
        if verb == "open" then return self:open() end
        if verb == "close" then
            if self.active and words[2] == "save" then commands.save() end
            return self:close(words[2] or "console", words[2] == "discard")
        end
        if not self.active then return log("Editor | console: not open") end
        if verb == "do" then
            local command = commands[words[2] or ""]
            if command then return command(words[3]) end
            if words[2] == "item" then return start_ghost(words[3]) end
            if words[2] == "shelf" then return show_shelf(words[3]) end
            if words[2] == "search" then return search(table.concat(words, " ", 3)) end
            return on_action(words[2] or "", tonumber(words[3]) or 1)
        end
        if verb == "select" then
            -- A placed mesh by id, or a vanilla object by its layout key.
            local record = apply.placed[words[2] or ""]
            if record and g.valid(record.component) then
                return select({ kind = "placed", key = words[2], object = record.actor, mesh = record.mesh,
                                label = Catalog.name_of(record.mesh) }, record.component)
            end
            local edit = apply.edits[words[2] or ""]
            if edit then
                local component = edit.actor and edit.root or edit.object
                return select({ kind = "vanilla", key = words[2], object = edit.object, mesh = edit.mesh,
                                label = Pick.label(edit.mesh, words[2]) }, component)
            end
            return log("Editor | console: nothing called %s", tostring(words[2]))
        end
        if verb == "mouse" or verb == "click" then
            s.pc:SetMouseLocation(math.floor(tonumber(words[2]) or 0), math.floor(tonumber(words[3]) or 0))
            if verb == "click" then
                actions:schedule_after("den-input", 50, function() pcall(on_action, "select", 1) end)
                actions:schedule_after("den-input", 120, function() pcall(on_action, "select", 0) end)
            end
            return
        end
        log("Editor | state: sel=%s ghost=%s drag=%s dirty=%s placed=%d side=%s scope=%s", s.sel and s.sel.key or "-",
            s.ghost and s.ghost.name or "-", tostring(s.drag ~= nil), tostring(s.history and s.history:dirty()),
            apply:placed_count(), tostring(s.side), tostring(watch.scope))
    end
    self.console = console

    function self:install(key, modifiers)
        runtime:register_keybind(key, modifiers, function()
            ExecuteInGameThread(guarded(function() self:toggle() end))
        end)
        local last_line, last_at = nil, -1
        runtime:register_console("zcomden", function(full)
            -- The engine offers one console line to several handlers' owners: run each line once.
            local line = tostring(full or "")
            if line == last_line and os.clock() - last_at < 0.1 then return true end
            last_line, last_at = line, os.clock()
            local words = {}
            for w in tostring(full or ""):gmatch("%S+") do words[#words + 1] = w end
            table.remove(words, 1)
            actions:schedule_after("den-console", 0, guarded(function() console(words) end))
            return true
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
