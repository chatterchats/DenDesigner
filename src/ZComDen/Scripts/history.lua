-- Den Designer: the editor's working layout plus undo/redo. Pure Lua: the Den itself is reached only through
-- `world`, so tests cover it fully.
--
-- A change sets whole entries: ("vanilla", key) -> edit or nil, ("placed", id) -> entry or nil. Each step keeps
-- the entries before and after, so undo and redo just set them again, in the layout and in the Den.
local Layout = require("layout")
local M = {}

M.LIMIT = 200       -- undo steps kept
M.MERGE_SECONDS = 1 -- wheel turns on one object within this merge into one step

-- doc: a normalised layout (edited in place); world: { vanilla = fn(key, edit|nil), placed = fn(id, entry|nil) }.
function M.new(doc, world, options)
    options = options or {}
    local clock = options.clock or os.clock
    local self = { doc = doc, undos = {}, redos = {}, version = 0, saved = 0 }
    local next_version = 0

    local function placed_index(id)
        for i, e in ipairs(doc.placed) do if e.id == id then return i end end
        return nil
    end

    function self:get(kind, key)
        if kind == "vanilla" then return Layout.copy(doc.vanilla[key]) end
        local i = placed_index(key)
        return i and Layout.copy(doc.placed[i]) or nil
    end

    local function put(kind, key, value)
        if kind == "vanilla" then
            doc.vanilla[key] = Layout.copy(value)
        else
            local i = placed_index(key)
            if value == nil then
                if i then table.remove(doc.placed, i) end
            elseif i then
                doc.placed[i] = Layout.copy(value)
            else
                doc.placed[#doc.placed + 1] = Layout.copy(value)
            end
        end
        return world[kind](key, Layout.copy(value))
    end

    -- Applies changes { { kind, key, value }, ... } as one undo step called `label`. With `merge` set, a change
    -- to the same entries under the same merge name shortly after the last one extends that step instead.
    -- Returns false plus the first failure if the Den refused a change (the layout still records it).
    function self:commit(label, changes, merge)
        local now = clock()
        local top = self.undos[#self.undos]
        local merging = merge and top and top.merge == merge and now - top.time <= M.MERGE_SECONDS
            and #top.changes == #changes and self.version == top.after
        if merging then
            for i, c in ipairs(changes) do
                if top.changes[i].kind ~= c[1] or top.changes[i].key ~= c[2] then merging = false; break end
            end
        end
        local ok, why = true, nil
        local step = merging and top or { label = label, merge = merge, changes = {}, before = self.version }
        for i, c in ipairs(changes) do
            local kind, key, value = c[1], c[2], c[3]
            if not merging then step.changes[i] = { kind = kind, key = key, before = self:get(kind, key) } end
            step.changes[i].after = Layout.copy(value)
            local done, err = put(kind, key, value)
            if done == false and ok then ok, why = false, err end
        end
        step.time = now
        if not merging then
            next_version = next_version + 1
            step.after = next_version
            self.undos[#self.undos + 1] = step
            if #self.undos > M.LIMIT then table.remove(self.undos, 1) end
        end
        self.version = step.after
        self.redos = {}
        return ok, why
    end

    -- Undoes the last step; returns its label, or nil when there's nothing to undo.
    function self:undo()
        local step = table.remove(self.undos)
        if not step then return nil end
        for i = #step.changes, 1, -1 do
            local c = step.changes[i]
            put(c.kind, c.key, c.before)
        end
        self.version = step.before
        self.redos[#self.redos + 1] = step
        return step.label
    end

    function self:redo()
        local step = table.remove(self.redos)
        if not step then return nil end
        for _, c in ipairs(step.changes) do put(c.kind, c.key, c.after) end
        self.version = step.after
        step.time = -math.huge  -- a redone step never merges with what comes next
        self.undos[#self.undos + 1] = step
        return step.label
    end

    function self:dirty() return self.version ~= self.saved end
    function self:mark_saved() self.saved = self.version end

    return self
end

return M
