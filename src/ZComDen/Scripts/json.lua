-- Den Designer: JSON for layout files. Decodes any JSON; encodes with sorted keys, two-space indents and
-- numbers trimmed to 3 decimals, so saved layouts diff cleanly. Pure Lua (5.4 in game, LuaJIT in tests).
local M = {}

-- Arrays carry this metatable so an empty one still encodes as [] (an empty plain table is an object).
M.array_mt = { __jsontype = "array" }
function M.array(t) return setmetatable(t or {}, M.array_mt) end

local function is_array(t)
    if getmetatable(t) == M.array_mt then return true end
    local n = #t
    if n == 0 then return false end
    for k in pairs(t) do
        if type(k) ~= "number" or k < 1 or k > n or k ~= math.floor(k) then return false end
    end
    return true
end

local ESCAPES = { ['"'] = '\\"', ["\\"] = "\\\\", ["\b"] = "\\b", ["\f"] = "\\f", ["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t" }
local function quote(s)
    return '"' .. s:gsub('[%c"\\]', function(c) return ESCAPES[c] or string.format("\\u%04x", c:byte()) end) .. '"'
end

local function number(n)
    if n ~= n or n == math.huge or n == -math.huge then error("can't encode " .. tostring(n) .. " in JSON") end
    if n == math.floor(n) and math.abs(n) < 1e15 then return string.format("%.0f", n) end
    local s = string.format("%.3f", n):gsub("0+$", ""):gsub("%.$", "")
    return s == "-0" and "0" or s
end

local function encode(value, indent, out)
    local t = type(value)
    if t == "nil" then out[#out + 1] = "null"
    elseif t == "boolean" then out[#out + 1] = tostring(value)
    elseif t == "number" then out[#out + 1] = number(value)
    elseif t == "string" then out[#out + 1] = quote(value)
    elseif t == "table" then
        local inner = indent .. "  "
        if is_array(value) then
            if #value == 0 then out[#out + 1] = "[]"; return end
            -- Short arrays of plain numbers (vectors) stay on one line.
            local flat = #value <= 4
            for _, v in ipairs(value) do if type(v) ~= "number" then flat = false end end
            if flat then
                local parts = {}
                for i, v in ipairs(value) do parts[i] = number(v) end
                out[#out + 1] = "[" .. table.concat(parts, ", ") .. "]"
                return
            end
            out[#out + 1] = "[\n"
            for i, v in ipairs(value) do
                out[#out + 1] = inner
                encode(v, inner, out)
                out[#out + 1] = i < #value and ",\n" or "\n"
            end
            out[#out + 1] = indent .. "]"
        else
            local keys = {}
            for k in pairs(value) do
                if type(k) ~= "string" then error("JSON object keys must be strings, got " .. type(k)) end
                keys[#keys + 1] = k
            end
            if #keys == 0 then out[#out + 1] = "{}"; return end
            table.sort(keys)
            out[#out + 1] = "{\n"
            for i, k in ipairs(keys) do
                out[#out + 1] = inner .. quote(k) .. ": "
                encode(value[k], inner, out)
                out[#out + 1] = i < #keys and ",\n" or "\n"
            end
            out[#out + 1] = indent .. "}"
        end
    else
        error("can't encode a " .. t .. " in JSON")
    end
end

function M.encode(value)
    local out = {}
    encode(value, "", out)
    return table.concat(out) .. "\n"
end

-- Returns the value, or nil and "line N: why".
function M.decode(text)
    if type(text) ~= "string" then return nil, "not a string" end
    local i = 1
    local function fail(why)
        local line = 1
        for _ in text:sub(1, i):gmatch("\n") do line = line + 1 end
        error({ msg = string.format("line %d: %s", line, why) }, 0)
    end
    local function skip() i = text:find("[^ \t\r\n]", i) or #text + 1 end
    local value
    local function str()
        local out, j = {}, i + 1
        while true do
            local c = text:sub(j, j)
            if c == "" then fail("unterminated string") end
            if c == '"' then break end
            if c == "\\" then
                local e = text:sub(j + 1, j + 1)
                local simple = ({ ['"'] = '"', ["\\"] = "\\", ["/"] = "/", b = "\b", f = "\f", n = "\n", r = "\r", t = "\t" })[e]
                if simple then out[#out + 1] = simple; j = j + 2
                elseif e == "u" then
                    local hex = text:sub(j + 2, j + 5)
                    if not hex:match("^%x%x%x%x$") then fail("bad \\u escape") end
                    local code = tonumber(hex, 16)
                    if code < 0x80 then out[#out + 1] = string.char(code)
                    elseif code < 0x800 then out[#out + 1] = string.char(0xC0 + math.floor(code / 64), 0x80 + code % 64)
                    else out[#out + 1] = string.char(0xE0 + math.floor(code / 4096), 0x80 + math.floor(code / 64) % 64, 0x80 + code % 64) end
                    j = j + 6
                else fail("bad escape \\" .. e) end
            else
                local k = text:find('["\\]', j) or #text + 1
                out[#out + 1] = text:sub(j, k - 1)
                j = k
            end
        end
        i = j + 1
        return table.concat(out)
    end
    function value()
        skip()
        local c = text:sub(i, i)
        if c == "{" then
            i = i + 1
            local obj = {}
            skip()
            if text:sub(i, i) == "}" then i = i + 1; return obj end
            while true do
                skip()
                if text:sub(i, i) ~= '"' then fail("expected a key") end
                local k = str()
                skip()
                if text:sub(i, i) ~= ":" then fail("expected ':'") end
                i = i + 1
                obj[k] = value()
                skip()
                local d = text:sub(i, i)
                i = i + 1
                if d == "}" then return obj end
                if d ~= "," then fail("expected ',' or '}'") end
            end
        elseif c == "[" then
            i = i + 1
            local arr = M.array()
            skip()
            if text:sub(i, i) == "]" then i = i + 1; return arr end
            while true do
                arr[#arr + 1] = value()
                skip()
                local d = text:sub(i, i)
                i = i + 1
                if d == "]" then return arr end
                if d ~= "," then fail("expected ',' or ']'") end
            end
        elseif c == '"' then return str()
        elseif text:sub(i, i + 3) == "true" then i = i + 4; return true
        elseif text:sub(i, i + 4) == "false" then i = i + 5; return false
        elseif text:sub(i, i + 3) == "null" then i = i + 4; return nil
        else
            local num = text:match("^-?%d+%.?%d*[eE]?[-+]?%d*", i)
            if not num or num == "" or not tonumber(num) then fail("unexpected '" .. c .. "'") end
            i = i + #num
            return tonumber(num)
        end
    end
    local ok, result = pcall(function()
        local v = value()
        skip()
        if i <= #text then fail("trailing data") end
        return v
    end)
    if ok then return result end
    if type(result) == "table" and result.msg then return nil, result.msg end
    return nil, tostring(result)
end

return M
