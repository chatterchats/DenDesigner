-- Den Designer: outlines through the game's own custom-depth post-process. In the Den, stencil 32 draws a gold
-- outline and 15 a blue one (found by screenshot 2026-10-17); it works on Nanite meshes, where overlay
-- materials don't draw. Each component's own custom-depth settings come back when the outline goes.
local M = {}

M.SELECTED = 32
M.HOVER = 15

function M.new(g)
    local self = { lit = {} }  -- path -> { component, render, stencil }

    function self:set(component, stencil)
        if not g.valid(component) then return end
        local path = g.path(component)
        local entry = self.lit[path]
        if not entry then
            entry = { component = component, render = component.bRenderCustomDepth == true,
                      stencil = tonumber(component.CustomDepthStencilValue) or 0 }
            self.lit[path] = entry
        end
        entry.value = stencil
        component:SetRenderCustomDepth(true)
        component:SetCustomDepthStencilValue(stencil)
    end

    function self:clear(component)
        if component == nil then return end
        local path = g.path(component)
        local entry = self.lit[path]
        if not entry then return end
        self.lit[path] = nil
        if g.valid(entry.component) then
            pcall(function()
                entry.component:SetCustomDepthStencilValue(entry.stencil)
                entry.component:SetRenderCustomDepth(entry.render)
            end)
        end
    end

    function self:clear_all()
        for _, entry in pairs(self.lit) do self:clear(entry.component) end
        self.lit = {}
    end

    -- Forget without touching (the world is gone).
    function self:forget() self.lit = {} end

    return self
end

return M
