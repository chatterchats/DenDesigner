-- Den Designer: rebindable editor keys. MXM stores a key as a Windows virtual-key code; the editor's mapping
-- context (IMC_DenEditor) uses Unreal key names. Pure Lua: tested offline.
--
-- A binding rewrites the key of one mapping in place (found by its action and its shipped key), so a key that
-- moves along an axis (WASD, Space/Ctrl) keeps its swizzle and negate modifiers.
local M = {}

-- setting key, input action, shipped key name, shipped virtual-key code, label for the settings menu
M.BINDINGS = {
    { "key_forward", "IA_Den_Move", "W", 0x57, "Fly forward" },
    { "key_back", "IA_Den_Move", "S", 0x53, "Fly back" },
    { "key_left", "IA_Den_Move", "A", 0x41, "Fly left" },
    { "key_right", "IA_Den_Move", "D", 0x44, "Fly right" },
    { "key_up", "IA_Den_Move", "SpaceBar", 0x20, "Fly up" },
    { "key_down", "IA_Den_Move", "LeftControl", 0xA2, "Fly down" },
    { "key_fast", "IA_Den_Fast", "LeftShift", 0xA0, "Fly fast / fine turns / lift while dragging" },
    { "key_turn_left", "IA_Den_Rotate", "Q", 0x51, "Turn left" },
    { "key_turn_right", "IA_Den_Rotate", "E", 0x45, "Turn right" },
    { "key_store", "IA_Den_Store", "X", 0x58, "Store (Delete always works too)" },
    { "key_copy", "IA_Den_Duplicate", "C", 0x43, "Copy" },
    { "key_undo", "IA_Den_Undo", "Z", 0x5A, "Undo" },
    { "key_redo", "IA_Den_Redo", "Y", 0x59, "Redo" },
    { "key_focus", "IA_Den_Focus", "F", 0x46, "Fly to the selection" },
    { "key_reset", "IA_Den_Reset", "R", 0x52, "Reset" },
    { "key_snap", "IA_Den_Snap", "G", 0x47, "Grid snap" },
    { "key_catalog", "IA_Den_Catalog", "Tab", 0x09, "Catalog" },
    { "key_storeroom", "IA_Den_Storeroom", "H", 0x48, "Storeroom" },
    { "key_layouts", "IA_Den_Layouts", "L", 0x4C, "Layouts" },
}

local NAMES = {
    [0x08] = "BackSpace", [0x09] = "Tab", [0x0D] = "Enter", [0x10] = "LeftShift", [0x11] = "LeftControl",
    [0x12] = "LeftAlt", [0x13] = "Pause", [0x14] = "CapsLock", [0x1B] = "Escape", [0x20] = "SpaceBar",
    [0x21] = "PageUp", [0x22] = "PageDown", [0x23] = "End", [0x24] = "Home", [0x25] = "Left", [0x26] = "Up",
    [0x27] = "Right", [0x28] = "Down", [0x2D] = "Insert", [0x2E] = "Delete",
    [0x6A] = "Multiply", [0x6B] = "Add", [0x6D] = "Subtract", [0x6E] = "Decimal", [0x6F] = "Divide",
    [0xA0] = "LeftShift", [0xA1] = "RightShift", [0xA2] = "LeftControl", [0xA3] = "RightControl",
    [0xA4] = "LeftAlt", [0xA5] = "RightAlt", [0xBA] = "Semicolon", [0xBB] = "Equals", [0xBC] = "Comma",
    [0xBD] = "Hyphen", [0xBE] = "Period", [0xBF] = "Slash", [0xC0] = "Tilde", [0xDB] = "LeftBracket",
    [0xDC] = "Backslash", [0xDD] = "RightBracket", [0xDE] = "Apostrophe",
}
local DIGITS = { "Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine" }

-- Unreal's key name for a virtual-key code, or nil for codes the editor can't use.
function M.key_name(vk)
    vk = tonumber(vk)
    if not vk then return nil end
    if vk >= 0x41 and vk <= 0x5A then return string.char(vk) end
    if vk >= 0x30 and vk <= 0x39 then return DIGITS[vk - 0x30 + 1] end
    if vk >= 0x60 and vk <= 0x69 then return "NumPad" .. DIGITS[vk - 0x60 + 1] end
    if vk >= 0x70 and vk <= 0x7B then return "F" .. (vk - 0x6F) end
    return NAMES[vk]
end

-- Keys the editor itself needs whatever the settings say.
M.RESERVED = { Escape = true, Delete = true, Up = true, Down = true, Left = true, Right = true, PageUp = true,
               PageDown = true, Equals = true, Hyphen = true, Add = true, Subtract = true }

-- The wanted key name per binding: { [setting] = name }, from get(setting) -> virtual-key code. Unknown or
-- reserved codes keep the shipped key, and so does every key set twice (both of them), so a clash never leaves
-- an action unreachable. Returns names plus a list of problems for the log.
function M.plan(get)
    local names, problems, used = {}, {}, {}
    for _, b in ipairs(M.BINDINGS) do
        local vk = get(b[1])
        local name = M.key_name(vk)
        if vk ~= nil and vk ~= b[4] and (not name or M.RESERVED[name]) then
            problems[#problems + 1] = string.format("%s: that key can't be used; keeping %s", b[5], b[3])
            name = nil
        end
        names[b[1]] = name or b[3]
        used[names[b[1]]] = (used[names[b[1]]] or 0) + 1
    end
    for _, b in ipairs(M.BINDINGS) do
        if used[names[b[1]]] > 1 and names[b[1]] ~= b[3] then
            problems[#problems + 1] = string.format("%s: %s is already taken; keeping %s", b[5], names[b[1]], b[3])
            names[b[1]] = b[3]
        end
    end
    return names, problems
end

return M
