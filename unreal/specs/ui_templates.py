"""Native editor widget trees, input actions and camera rig templates.

Runtime editor assets attach the event bus, styling and input focus guards.
Generate the complete spec set with runtime.py.
"""
import json
from pathlib import Path

ROOT = "/DenDesignerGF/Editor/"
EI = "/Script/EnhancedInput."



def negate():
    return {"class": EI + "InputModifierNegate"}


def swizzle(order):
    return {"class": EI + "InputModifierSwizzleAxis", "props": {"Order": order}}


def chord(action):
    return {"class": EI + "InputTriggerChordAction", "props": {"ChordAction": ROOT + action}}


def repeat(interval):
    """Fires on press, then every `interval` seconds while held."""
    return {"class": EI + "InputTriggerPulse", "props": {"Interval": interval, "bTriggerOnStart": "true"}}


# (name, value type)
ACTIONS = [
    ("IA_Den_Move", "Axis3D"), ("IA_Den_Look", "Axis2D"), ("IA_Den_LookHold", "Boolean"),
    ("IA_Den_Fast", "Boolean"), ("IA_Den_Alt", "Boolean"), ("IA_Den_Select", "Boolean"),
    ("IA_Den_Rotate", "Axis1D"), ("IA_Den_RotateFine", "Axis1D"), ("IA_Den_Scale", "Axis1D"),
    ("IA_Den_Nudge", "Axis3D"),
]

# Discrete commands: (action, event name, keys). Each sends Native_Action(name, 1) when its key goes down.
COMMANDS = [
    ("IA_Den_Store", "store", ["Delete", "X"]),
    ("IA_Den_Duplicate", "duplicate", ["C"]),
    ("IA_Den_Undo", "undo", ["Z"]),
    ("IA_Den_Redo", "redo", ["Y"]),
    ("IA_Den_Focus", "focus", ["F"]),
    ("IA_Den_Reset", "reset", ["R"]),
    ("IA_Den_Snap", "snap", ["G"]),
    ("IA_Den_Back", "back", ["Escape"]),
    ("IA_Den_Catalog", "catalog", ["Tab"]),
    ("IA_Den_Layouts", "layouts", ["L"]),
    ("IA_Den_Storeroom", "storeroom", ["H"]),
    ("IA_Den_Gimbal", "gimbal", ["T"]),
]

NUDGE_REPEAT = 0.12
ROTATE_REPEAT = 0.15

MAPPINGS = [
    {"action": "IA_Den_Move", "key": "W"},
    {"action": "IA_Den_Move", "key": "S", "modifiers": [negate()]},
    {"action": "IA_Den_Move", "key": "D", "modifiers": [swizzle("YXZ")]},
    {"action": "IA_Den_Move", "key": "A", "modifiers": [swizzle("YXZ"), negate()]},
    {"action": "IA_Den_Move", "key": "SpaceBar", "modifiers": [swizzle("ZYX")]},
    {"action": "IA_Den_Move", "key": "LeftControl", "modifiers": [swizzle("ZYX"), negate()]},
    {"action": "IA_Den_LookHold", "key": "RightMouseButton"},
    {"action": "IA_Den_Look", "key": "Mouse2D", "triggers": [chord("IA_Den_LookHold")]},
    {"action": "IA_Den_Fast", "key": "LeftShift"},
    {"action": "IA_Den_Alt", "key": "LeftAlt"},
    {"action": "IA_Den_Select", "key": "LeftMouseButton"},
    # Fine rotation blocks plain rotation while the fast-flight key is held.
    # Keep scaling on +/- only: the Alt+wheel scale chord has fired without Alt in game.
    {"action": "IA_Den_RotateFine", "key": "MouseWheelAxis", "triggers": [chord("IA_Den_Fast")]},
    {"action": "IA_Den_Rotate", "key": "MouseWheelAxis"},
    {"action": "IA_Den_Rotate", "key": "Q", "modifiers": [negate()], "triggers": [repeat(ROTATE_REPEAT)]},
    {"action": "IA_Den_Rotate", "key": "E", "triggers": [repeat(ROTATE_REPEAT)]},
    # +/- and their keypad equivalents scale, with repeat while held.
    {"action": "IA_Den_Scale", "key": "Equals", "triggers": [repeat(ROTATE_REPEAT)]},
    {"action": "IA_Den_Scale", "key": "Hyphen", "modifiers": [negate()], "triggers": [repeat(ROTATE_REPEAT)]},
    {"action": "IA_Den_Scale", "key": "Add", "triggers": [repeat(ROTATE_REPEAT)]},
    {"action": "IA_Den_Scale", "key": "Subtract", "modifiers": [negate()], "triggers": [repeat(ROTATE_REPEAT)]},
    {"action": "IA_Den_Nudge", "key": "Up", "triggers": [repeat(NUDGE_REPEAT)]},
    {"action": "IA_Den_Nudge", "key": "Down", "modifiers": [negate()], "triggers": [repeat(NUDGE_REPEAT)]},
    {"action": "IA_Den_Nudge", "key": "Right", "modifiers": [swizzle("YXZ")], "triggers": [repeat(NUDGE_REPEAT)]},
    {"action": "IA_Den_Nudge", "key": "Left", "modifiers": [swizzle("YXZ"), negate()], "triggers": [repeat(NUDGE_REPEAT)]},
    {"action": "IA_Den_Nudge", "key": "PageUp", "modifiers": [swizzle("ZYX")], "triggers": [repeat(NUDGE_REPEAT)]},
    {"action": "IA_Den_Nudge", "key": "PageDown", "modifiers": [swizzle("ZYX"), negate()], "triggers": [repeat(NUDGE_REPEAT)]},
] + [{"action": action, "key": key} for action, _, keys in COMMANDS for key in keys]


def input_actions():
    specs = [{"kind": "input_action", "path": ROOT + name, "value_type": value} for name, value in ACTIONS]
    specs += [{"kind": "input_action", "path": ROOT + action, "value_type": "Boolean"} for action, _, _ in COMMANDS]
    return specs


def mapping_context():
    mappings = []
    for m in MAPPINGS:
        m = dict(m, action=ROOT + m["action"])
        mappings.append(m)
    return {"kind": "mapping_context", "path": ROOT + "IMC_DenEditor", "mappings": mappings}


def rig():
    """The flying camera. A CameraActor: the Den's camera manager rejects view targets that aren't camera-rooted.
    Flight and look run in Blueprint; other actions are connected to the native event bus."""
    nodes, links = [], []

    def node(id_, kind, **fields):
        nodes.append(dict({"id": id_, "kind": kind}, **fields))

    def link(a, b):
        links.append([a, b])

    def emit(id_, name, value="1"):
        node(id_, "call", function="self:Native_Action", defaults={"Name": name, "Value": value})

    # Flight: ActionValue (x forward, y right, z up) turned by the camera's yaw, times speed and frame time.
    node("move", "input_action", action=ROOT + "IA_Den_Move")
    node("dt", "call", function="/Script/Engine.GameplayStatics:GetWorldDeltaSeconds")
    node("speed", "get", var="Speed")
    node("fastmul", "get", var="FastMultiplier")
    node("fast", "get", var="bFast")
    node("mul", "call", function="/Script/Engine.KismetMathLibrary:SelectFloat", defaults={"B": "1.0"})
    node("speed2", "call", function="/Script/Engine.KismetMathLibrary:Multiply_DoubleDouble")
    node("step", "call", function="/Script/Engine.KismetMathLibrary:Multiply_DoubleDouble")
    node("rot", "call", function="self:K2_GetActorRotation")
    node("brk", "call", function="/Script/Engine.KismetMathLibrary:BreakRotator")
    node("planar", "call", function="/Script/Engine.KismetMathLibrary:RotateAngleAxis", defaults={"Axis": "0,0,1"})
    node("scaled", "call", function="/Script/Engine.KismetMathLibrary:Multiply_VectorFloat")
    node("offset", "call", function="self:K2_AddActorWorldOffset")
    for a, b in [("move.Triggered", "offset.execute"), ("fastmul.FastMultiplier", "mul.A"), ("fast.bFast", "mul.bPickA"),
                 ("speed.Speed", "speed2.A"), ("mul.ReturnValue", "speed2.B"), ("speed2.ReturnValue", "step.A"),
                 ("dt.ReturnValue", "step.B"), ("rot.ReturnValue", "brk.InRot"), ("move.ActionValue", "planar.InVect"),
                 ("brk.Yaw", "planar.AngleDeg"), ("planar.ReturnValue", "scaled.A"), ("step.ReturnValue", "scaled.B"),
                 ("scaled.ReturnValue", "offset.DeltaLocation")]:
        link(a, b)

    # Look (only while RMB is held, by the mapping's chord): yaw around world up, pitch around the camera's right.
    node("look", "input_action", action=ROOT + "IA_Den_Look")
    node("split", "call", function="/Script/Engine.KismetMathLibrary:BreakVector2D")
    node("rate", "get", var="LookRate")
    node("yaw", "call", function="/Script/Engine.KismetMathLibrary:Multiply_DoubleDouble")
    node("pitch", "call", function="/Script/Engine.KismetMathLibrary:Multiply_DoubleDouble")
    node("yawrot", "call", function="/Script/Engine.KismetMathLibrary:MakeRotator")
    node("turn", "call", function="self:K2_AddActorWorldRotation")
    node("pitchrot", "call", function="/Script/Engine.KismetMathLibrary:MakeRotator")
    node("tilt", "call", function="self:K2_AddActorLocalRotation")
    for a, b in [("look.Triggered", "turn.execute"), ("look.ActionValue", "split.InVec"), ("split.X", "yaw.A"),
                 ("rate.LookRate", "yaw.B"), ("split.Y", "pitch.A"), ("rate.LookRate", "pitch.B"),
                 ("yaw.ReturnValue", "yawrot.Yaw"), ("yawrot.ReturnValue", "turn.DeltaRotation"),
                 ("turn.then", "tilt.execute"), ("pitch.ReturnValue", "pitchrot.Pitch"),
                 ("pitchrot.ReturnValue", "tilt.DeltaRotation")]:
        link(a, b)

    # Shift: fast flight (the drag service also reads bFast for vertical movement).
    node("fastkey", "input_action", action=ROOT + "IA_Den_Fast")
    node("fast_on", "set", var="bFast", defaults={"bFast": "true"})
    node("fast_off", "set", var="bFast", defaults={"bFast": "false"})
    # Alt: held, a move ignores neighbour snapping (runtime_snap reads bAlt).
    node("altkey", "input_action", action=ROOT + "IA_Den_Alt")
    node("alt_on", "set", var="bAlt", defaults={"bAlt": "true"})
    node("alt_off", "set", var="bAlt", defaults={"bAlt": "false"})
    link("altkey.Started", "alt_on.execute")
    link("altkey.Completed", "alt_off.execute")
    link("fastkey.Started", "fast_on.execute")
    link("fastkey.Completed", "fast_off.execute")

    # Held buttons: 1 on press, 0 on release.
    for action, name in [("IA_Den_LookHold", "look_hold"), ("IA_Den_Select", "select")]:
        node(name, "input_action", action=ROOT + action)
        emit(name + "_on", name, "1")
        emit(name + "_off", name, "0")
        link(name + ".Started", name + "_on.execute")
        link(name + ".Completed", name + "_off.execute")

    # Wheel and Q/E: the step count (wheel notches, or +-1 per key repeat).
    for action, name in [("IA_Den_Rotate", "rotate"), ("IA_Den_RotateFine", "rotate_fine"), ("IA_Den_Scale", "scale")]:
        node(name, "input_action", action=ROOT + action)
        node(name + "_event", "call", function="self:Native_Action", defaults={"Name": name})
        link(name + ".Triggered", name + "_event.execute")
        link(name + ".ActionValue", name + "_event.Value")

    node("nudge", "input_action", action=ROOT + "IA_Den_Nudge")
    node("nudge_event", "call", function="self:Native_Vector", defaults={"Name": "nudge"})
    link("nudge.Triggered", "nudge_event.execute")
    link("nudge.ActionValue", "nudge_event.Value")

    for action, name, _ in COMMANDS:
        node(name, "input_action", action=ROOT + action)
        emit(name + "_event", name)
        link(name + ".Started", name + "_event.execute")

    return {
        "kind": "blueprint", "path": ROOT + "BP_DenEditorRig", "parent": "/Script/Engine.CameraActor",
        "variables": [
            {"name": "bFast", "type": "bool", "default": "false"},
            {"name": "bAlt", "type": "bool", "default": "false"},
            {"name": "Speed", "type": "float", "default": "900.0"},
            {"name": "FastMultiplier", "type": "float", "default": "3.0"},
            {"name": "LookRate", "type": "float", "default": "2.5"},
            # TraceLine's results (read by the native picking service).
            {"name": "TraceHit", "type": "bool", "default": "false"},
            {"name": "TracePoint", "type": "vector"},
            {"name": "TraceNormal", "type": "vector"},
            {"name": "TraceComponent", "type": "object:/Script/Engine.PrimitiveComponent"},
        ],
        "functions": [
            {"name": "Native_Action", "inputs": [{"name": "Name", "type": "string"}, {"name": "Value", "type": "float"}]},
            {"name": "Native_Vector", "inputs": [{"name": "Name", "type": "string"}, {"name": "Value", "type": "vector"}]},
            trace_line(),
        ],
        "graph": {"nodes": nodes, "links": links},
    }


def trace_line():
    """TraceLine(Start, End): a visibility trace (complex collision) whose hit lands in the rig's Trace* variables.
    The picking service reads the result fields directly."""
    nodes = [  # "entry" (the function's entry node) is predefined
        {"id": "trace", "kind": "call", "function": "/Script/Engine.KismetSystemLibrary:LineTraceSingle",
         "defaults": {"TraceChannel": "TraceTypeQuery1", "bTraceComplex": "true", "DrawDebugType": "None", "bIgnoreSelf": "true"}},
        {"id": "brk", "kind": "call", "function": "/Script/Engine.GameplayStatics:BreakHitResult"},
        {"id": "hit", "kind": "set", "var": "TraceHit"},
        {"id": "point", "kind": "set", "var": "TracePoint"},
        {"id": "normal", "kind": "set", "var": "TraceNormal"},
        {"id": "comp", "kind": "set", "var": "TraceComponent"},
    ]
    links = [["entry.then", "trace.execute"], ["entry.Start", "trace.Start"], ["entry.End", "trace.End"],
             ["trace.OutHit", "brk.Hit"],
             ["trace.then", "hit.execute"], ["trace.ReturnValue", "hit.TraceHit"],
             ["hit.then", "point.execute"], ["brk.ImpactPoint", "point.TracePoint"],
             ["point.then", "normal.execute"], ["brk.ImpactNormal", "normal.TraceNormal"],
             ["normal.then", "comp.execute"], ["brk.HitComponent", "comp.TraceComponent"]]
    return {"name": "TraceLine", "inputs": [{"name": "Start", "type": "vector"}, {"name": "End", "type": "vector"}],
            "nodes": nodes, "links": links}


# The editor's look: translucent dark panels with thin outlines and an amber accent. The layout has a menu bar,
# a library dock on the left (one panel at a time beside its side tabs), an inspector dock on the right and a status bar.
# Colours are linear, as UMG stores them.
ACCENT = (0.888, 0.479, 0.070)
SOFT_RGB = (0.584, 0.611, 0.651)
ICONS = ROOT + "Icons/"
ICON_NAMES = sorted(p.stem for p in (Path(__file__).resolve().parents[1] / "icons").glob("*.svg"))


def rgba(r, g, b, a=1):
    return f"(R={r},G={g},B={b},A={a})"


def slate(r, g, b, a=1):
    return f"(SpecifiedColor={rgba(r, g, b, a)},ColorUseRule=UseColor_Specified)"


def icon(name):
    """An icon texture, imported by build_gf.py from unreal/icons/<name>.svg."""
    assert name in ICON_NAMES, "No icon source for " + name
    return ICONS + "T_Icon_" + name


PANEL = rgba(0.0027, 0.003, 0.004, 0.88)
EDGE = rgba(1, 1, 1, 0.10)
CLEAR = rgba(1, 1, 1, 0)
BUTTON = rgba(1, 1, 1)  # the brushes below carry the colours
WHITE = slate(0.84, 0.81, 0.75)
SOFT = slate(*SOFT_RGB)
DIM = slate(0.386, 0.423, 0.479)
INK = slate(0.0075, 0.006, 0.0035)
GOLD = slate(*ACCENT)
# The runtime tints a tool, tab or filter's backing with ACTIVE_BACK while it's on (runtime_editor_commands).
ACTIVE_BACK = rgba(*ACCENT, 0.16)
AXES = {"X": (0.584, 0.045, 0.052), "Y": (0.042, 0.254, 0.07), "Z": (0.028, 0.178, 0.552)}
# Catalog, Storeroom and composition cards: two to a row in the library dock, so names and sizes fit.
TILE_WIDTH, TILE_HEIGHT, PICTURE = 212, 250, 136
LIBRARY_WIDTH, INSPECTOR_WIDTH = 470, 370
# The library tabs are a rail down the left edge, so wide windows such as the HoloNet clear them.
RAIL_WIDTH = 96
LIBRARY_LEFT = 12 + RAIL_WIDTH + 6


def rounded(fill, edge=None, radius=6, corners=None):
    """A RoundedBox brush; `corners` overrides the radii (top-left, top-right, bottom-right, bottom-left)."""
    tl, tr, br, bl = corners or (radius,) * 4
    return {"DrawAs": "RoundedBox", "TintColor": f"(SpecifiedColor={fill})",
            "OutlineSettings": f"(CornerRadii=(X={tl},Y={tr},Z={br},W={bl}),Color=(SpecifiedColor={edge or CLEAR}),"
                               f"Width={1.0 if edge else 0.0},RoundingType=FixedRadius)"}


def surface(fill=PANEL, edge=EDGE, radius=8, padding=None, corners=None, tint=BUTTON):
    """Border props: a rounded background, multiplied by BrushColor (`tint`), which the runtime may recolour."""
    props = {"BrushColor": tint, **{"Background." + key: value for key, value in rounded(fill, edge, radius, corners).items()}}
    if padding:
        props["Padding"] = padding
    return props


def button_style(normal, hovered, pressed, disabled=None, padding=(12, 7), radius=6):
    props = {}
    for state, (fill, edge) in (("Normal", normal), ("Hovered", hovered), ("Pressed", pressed), ("Disabled", disabled or normal)):
        for key, value in rounded(fill, edge, radius).items():
            props[f"WidgetStyle.{state}.{key}"] = value
    x, y = padding
    props["WidgetStyle.NormalPadding"] = f"(Left={x},Top={y},Right={x},Bottom={y})"
    props["WidgetStyle.PressedPadding"] = f"(Left={x},Top={y + 1},Right={x},Bottom={y - 1})"
    return props


HOVER_EDGE = rgba(*ACCENT, 0.6)
STYLES = {
    # Panel actions: a faint fill and outline; hover picks out the accent.
    "plain": button_style((rgba(1, 1, 1, 0.04), rgba(1, 1, 1, 0.16)), (rgba(1, 1, 1, 0.09), HOVER_EDGE), (rgba(0, 0, 0, 0.2), HOVER_EDGE)),
    # Tools, tabs and icon buttons: only hovering and pressing show a fill.
    "ghost": button_style((CLEAR, None), (rgba(1, 1, 1, 0.08), None), (rgba(1, 1, 1, 0.04), None), padding=(10, 7), radius=4),
    "primary": button_style((rgba(*ACCENT), None), (rgba(1, 0.62, 0.16), None), (rgba(0.7, 0.36, 0.05), None),
                            (rgba(*ACCENT, 0.35), None), padding=(16, 9)),
    "outline": button_style((CLEAR, rgba(1, 1, 1, 0.22)), (rgba(1, 1, 1, 0.07), rgba(1, 1, 1, 0.36)),
                            (rgba(0, 0, 0, 0.2), rgba(1, 1, 1, 0.36)), padding=(14, 9)),
}
BUTTON_STYLE = STYLES["plain"]


def scrollbar(thickness=4):
    """List props for a thin, quiet scrollbar with no track."""
    props = {"ScrollBarStyle.Thickness": thickness}
    for part in ("Horizontal", "Vertical"):
        for image in ("BackgroundImage", "TopSlotImage", "BottomSlotImage"):
            props[f"ScrollBarStyle.{part}{image}.DrawAs"] = "NoDrawType"
    for state, alpha in (("Normal", 0.18), ("Hovered", 0.32), ("Dragged", 0.45)):
        for key, value in rounded(rgba(1, 1, 1, alpha), None, thickness / 2).items():
            props[f"ScrollBarStyle.{state}ThumbImage.{key}"] = value
    return props

# Menu bar: (widget name, label, event, icon). Widget names are runtime identities; labels may change.
LIBRARY = [("Catalog", "Catalog", "catalog", "catalog"), ("Storeroom", "Storeroom", "storeroom", "storeroom"),
           ("Compositions", "Compositions", "compositions", "compositions"), ("Community", "HoloNet", "community", "community"), ("Layouts", "Layouts", "layouts", "layouts")]
TOOLS = [("SelectMode", "Select", "mode_select", "select"), ("Move", "Move", "mode_move", "move"),
         ("Rotate", "Rotate", "mode_rotate", "rotate"), ("ScaleMode", "Scale", "mode_scale", "scale")]
QUICK_CONTROLS = [("Magnet", "Snap", "neighbour_snap", "magnet"), ("Snap", "Off", "snap", "grid"), ("Reach", "20 m", "reach", "range")]
LAYERS = [("Floors", "Floors", "floors", "floors"), ("Walls", "Walls", "walls", "walls"), ("Lock", "Structure", "lock", "structure")]
# Icon-only buttons: (widget name, event, icon, tooltip).
MENU = [("Undo", "undo", "undo", "Undo"), ("Redo", "redo", "redo", "Redo"),
        ("Settings", "settings", "settings", "Settings"), ("Help", "help", "help", "Controls")]
CONFIRM = [("ConfirmSave", "Save", "confirm_save", "primary"), ("ConfirmDiscard", "Discard", "confirm_discard", "outline"),
           ("ConfirmCancel", "Keep editing", "confirm_cancel", "ghost")]
# Status bar reminders of the fixed controls; rebindable keys are listed under Help.
SHORTCUTS = [("Drag", "LMB drag", "Move on surface"), ("Height", "Shift", "Height"), ("Free", "Alt", "No snapping"),
             ("Turn", "Wheel", "Rotate"), ("Back", "Esc", "Back")]


def text(name, value, size, color=WHITE, variable=True, slot=None, wrap=False, role=None):
    """Every text block is a variable: the runtime style service assigns the game's fonts by `role` (title, heading,
    label, button, body or hint; otherwise inferred from size and colour). Labels and buttons are capitals."""
    w = {"class": "/Script/UMG.TextBlock", "name": name, "props": {"Text": value, "Font.Size": size, "ColorAndOpacity": color}}
    if role:
        w["role"] = role
    if role in ("label", "button"):
        w["props"]["TextTransformPolicy"] = "ToUpper"
    if wrap:
        w["props"]["AutoWrapText"] = "true"
    if variable:
        w["variable"] = True
    if slot:
        w["slot"] = slot
    return w


def label(name, value, size=13, color=DIM, slot=None):
    """A section label in condensed capitals."""
    return text(name, value, size, color, role="label", slot=slot)


def image(name, icon_name, size=20, color=SOFT_RGB, slot=None):
    return {"class": "/Script/UMG.Image", "name": name, "variable": True,
            "props": {"Brush.ResourceObject": icon(icon_name), "Brush.ImageSize": f"(X={size},Y={size})",
                      "ColorAndOpacity": rgba(*color), "Visibility": "HitTestInvisible"},
            "slot": slot or {"VerticalAlignment": "VAlign_Center"}}


def button(name, label, size=13, style="plain", icon_name=None, color=WHITE, tooltip=None):
    """A button with an optional icon (`<name>Icon`) and caption (`<name>Label`); `label=None` makes it icon-only."""
    tint = {"primary": (0.0075, 0.006, 0.0035)}.get(style, SOFT_RGB if color == SOFT else (0.84, 0.81, 0.75))
    parts = []
    if icon_name:
        gap = "(Left=0,Top=0,Right=0,Bottom=0)" if label is None else "(Left=0,Top=0,Right=7,Bottom=0)"
        parts.append(image(name + "Icon", icon_name, 20, tint, {"HorizontalAlignment": "HAlign_Center", "VerticalAlignment": "VAlign_Center", "Padding": gap}))
    if label is not None:
        caption = text(name + "Label", label, size, INK if style == "primary" else color, role="button",
                       slot={"HorizontalAlignment": "HAlign_Center", "VerticalAlignment": "VAlign_Center"})
        caption["props"]["Justification"] = "Center"
        parts.append(caption)
    content = parts[0] if len(parts) == 1 else {
        "class": "/Script/UMG.HorizontalBox", "name": name + "Content",
        "slot": {"HorizontalAlignment": "HAlign_Center", "VerticalAlignment": "VAlign_Center"}, "children": parts}
    props = dict({"BackgroundColor": BUTTON, "IsFocusable": "false"}, **STYLES[style])
    if tooltip:
        props["ToolTipText"] = tooltip
    # Not focusable: a focused button would take Space (fly up) as a click.
    return {"class": "/Script/UMG.Button", "name": name, "variable": True, "props": props,
            "slot": {"Padding": "(Left=0,Top=0,Right=6,Bottom=6)"}, "children": [content]}


def toggle(name, label, icon_name, fill=False):
    """A tool, tab or filter button inside `<name>Back`, a border the runtime tints while it's on."""
    inner = button(name, label, 15, "ghost", icon_name, SOFT)
    inner["slot"] = {"HorizontalAlignment": "HAlign_Fill", "VerticalAlignment": "VAlign_Fill"}
    slot = {"Padding": "(Left=0,Top=0,Right=2,Bottom=0)", "VerticalAlignment": "VAlign_Fill"}
    if fill:
        slot["Size"] = "(SizeRule=Fill,Value=1)"
    return {"class": "/Script/UMG.Border", "name": name + "Back", "variable": True,
            "props": surface(rgba(1, 1, 1), None, 4, "(Left=0,Top=0,Right=0,Bottom=0)", tint=CLEAR),
            "slot": slot, "children": [inner]}


def side_tab(name, label, icon_name):
    """A library tab in the rail: a toggle with its caption under its icon."""
    tab = toggle(name, label, icon_name)
    tab["slot"] = {"Padding": "(Left=0,Top=0,Right=0,Bottom=2)"}
    inner = tab["children"][0]
    inner["props"]["WidgetStyle.NormalPadding"] = "(Left=4,Top=10,Right=4,Bottom=8)"
    inner["props"]["WidgetStyle.PressedPadding"] = "(Left=4,Top=11,Right=4,Bottom=7)"
    content = inner["children"][0]
    content["class"] = "/Script/UMG.VerticalBox"
    icon_part, caption = content["children"]
    icon_part["slot"]["Padding"] = "(Left=0,Top=0,Right=0,Bottom=5)"
    caption["props"]["Font.Size"] = 11
    return tab


def divider(name, vertical=True, slot=None):
    size = {"WidthOverride": 1, "bOverride_WidthOverride": "true", "HeightOverride": 28, "bOverride_HeightOverride": "true"} if vertical \
        else {"HeightOverride": 1, "bOverride_HeightOverride": "true"}
    return {"class": "/Script/UMG.Border", "name": name, "props": surface(rgba(1, 1, 1, 0.14), None, 0, "(Left=0,Top=0,Right=0,Bottom=0)"),
            "slot": slot or ({"Padding": "(Left=4,Top=0,Right=10,Bottom=0)", "VerticalAlignment": "VAlign_Center"} if vertical
                             else {"Padding": "(Left=0,Top=12,Right=0,Bottom=12)"}),
            "children": [{"class": "/Script/UMG.SizeBox", "name": name + "Size", "props": size}]}


def group(name, children):
    """Related menu-bar controls on a darker inset."""
    return {"class": "/Script/UMG.Border", "name": name,
            "props": surface(rgba(0, 0, 0, 0.35), EDGE, 6, "(Left=3,Top=3,Right=1,Bottom=3)"),
            "slot": {"Padding": "(Left=0,Top=0,Right=10,Bottom=0)", "VerticalAlignment": "VAlign_Center"},
            "children": [{"class": "/Script/UMG.HorizontalBox", "name": name + "Row", "children": children}]}


def shortcut(name, key, meaning):
    chip = {"class": "/Script/UMG.Border", "name": name + "Key",
            "props": surface(rgba(1, 1, 1, 0.1), rgba(1, 1, 1, 0.16), 4, "(Left=6,Top=2,Right=6,Bottom=2)"),
            "slot": {"VerticalAlignment": "VAlign_Center"}, "children": [label(name + "KeyText", key, 12, WHITE)]}
    return {"class": "/Script/UMG.HorizontalBox", "name": name, "slot": {"Padding": "(Left=16,Top=0,Right=0,Bottom=0)", "VerticalAlignment": "VAlign_Center"},
            "children": [chip, text(name + "Text", meaning, 13, DIM, role="hint", slot={"Padding": "(Left=6,Top=0,Right=0,Bottom=0)", "VerticalAlignment": "VAlign_Center"})]}


def toolbar():
    middle = {"VerticalAlignment": "VAlign_Center"}
    identity = {"class": "/Script/UMG.HorizontalBox", "name": "Identity", "slot": {"Padding": "(Left=0,Top=0,Right=10,Bottom=0)", "VerticalAlignment": "VAlign_Center"},
                "children": [image("Logo", "logo", 28, ACCENT, {"VerticalAlignment": "VAlign_Center", "Padding": "(Left=0,Top=0,Right=12,Bottom=0)"}),
                             {"class": "/Script/UMG.VerticalBox", "name": "IdentityText", "slot": middle, "children": [
                                 text("Title", "Den Designer", 16, GOLD, role="label"),
                                 text("Status", "", 13, DIM, role="hint", slot={"Padding": "(Left=0,Top=3,Right=0,Bottom=0)"})]}]}
    right = [button(n, None, style="ghost", icon_name=i, tooltip=tip) for n, _, i, tip in MENU]
    for widget in right:
        widget["slot"] = {"Padding": "(Left=0,Top=0,Right=2,Bottom=0)", "VerticalAlignment": "VAlign_Center"}
    save = button("Save", "Save", 15, "primary", "save")
    done = button("Exit", "Done", 15, "outline", "done", WHITE)
    save["slot"] = {"Padding": "(Left=0,Top=0,Right=6,Bottom=0)", "VerticalAlignment": "VAlign_Center"}
    done["slot"] = {"Padding": "(Left=0,Top=0,Right=0,Bottom=0)", "VerticalAlignment": "VAlign_Center"}
    panel = {"class": "/Script/UMG.Border", "name": "Panel",
             "props": surface(PANEL, rgba(*ACCENT, 0.22), 8, "(Left=14,Top=6,Right=10,Bottom=6)"),
             "slot": {"LayoutData": "(Anchors=(Minimum=(X=0,Y=0),Maximum=(X=1,Y=0)),Offsets=(Left=12,Top=12,Right=12,Bottom=60))"},
             "children": [{"class": "/Script/UMG.HorizontalBox", "name": "Navigation", "children": [
                 identity, divider("IdentityDivider"),
                 group("Tools", [toggle(n, label_, i) for n, label_, _, i in TOOLS]),
                 group("QuickControls", [toggle(n, label_, i) for n, label_, _, i in QUICK_CONTROLS]),
                 group("Layers", [toggle(n, label_, i) for n, label_, _, i in LAYERS]),
                 {"class": "/Script/UMG.Spacer", "name": "Gap", "slot": {"Size": "(SizeRule=Fill,Value=1)"}},
                 {"class": "/Script/UMG.HorizontalBox", "name": "NavigationRight", "slot": middle,
                  "children": right + [divider("SaveDivider"), save, done]}]}]}
    tabs = {"class": "/Script/UMG.Border", "name": "LibraryTabs",
            "props": surface(PANEL, EDGE, 8, "(Left=4,Top=4,Right=4,Bottom=2)"),
            "slot": {"LayoutData": "(Anchors=(Minimum=(X=0,Y=0),Maximum=(X=0,Y=0)),Offsets=(Left=12,Top=80,Right=0,Bottom=0))", "bAutoSize": "true"},
            "children": [{"class": "/Script/UMG.SizeBox", "name": "LibraryRailWidth", "props": {"WidthOverride": RAIL_WIDTH - 8, "bOverride_WidthOverride": "true"},
                          "children": [{"class": "/Script/UMG.VerticalBox", "name": "LibraryRail",
                                        "children": [side_tab(n, label_, i) for n, label_, _, i in LIBRARY]}]}]}

    help_panel = {"class": "/Script/UMG.SizeBox", "name": "HelpPanel", "variable": True,
                  "props": {"WidthOverride": 600, "bOverride_WidthOverride": "true", "Visibility": "Collapsed"},
                  "slot": {"LayoutData": "(Anchors=(Minimum=(X=0.5,Y=0.5),Maximum=(X=0.5,Y=0.5)),Alignment=(X=0.5,Y=0.5))", "bAutoSize": "true"},
                  "children": [{"class": "/Script/UMG.Border", "name": "HelpPanelFrame",
                                "props": surface(PANEL, rgba(*ACCENT, 0.3), 8, "(Left=22,Top=18,Right=22,Bottom=18)"),
                                "children": [{"class": "/Script/UMG.VerticalBox", "name": "HelpPanelColumn", "children": [
                                    text("HelpPanelTitle", "Controls", 20, GOLD, role="title"),
                                    {"class": "/Script/UMG.SizeBox", "name": "HelpBody", "props": {"HeightOverride": 480, "bOverride_HeightOverride": "true"},
                                     "slot": {"Padding": "(Left=0,Top=14,Right=0,Bottom=16)"},
                                     "children": [{"class": "/Script/UMG.ScrollBox", "name": "HelpScroll", "children": [text("HelpText", "", 14, WHITE, wrap=True)]}]},
                                    button("CloseHelp", "Back to editing", 14)]}]}]}
    feedback = {"class": "/Script/UMG.Border", "name": "Feedback",
                "props": surface(PANEL, EDGE, 6, "(Left=14,Top=0,Right=14,Bottom=0)"),
                "slot": {"LayoutData": "(Anchors=(Minimum=(X=0,Y=1),Maximum=(X=1,Y=1)),Offsets=(Left=12,Top=-46,Right=12,Bottom=34))"},
                "children": [{"class": "/Script/UMG.HorizontalBox", "name": "FeedbackLines", "children": [
                    text("Hints", "Select a prop to edit it, or open the Catalog to add something.", 13, WHITE,
                         slot={"Size": "(SizeRule=Fill,Value=1)", "VerticalAlignment": "VAlign_Center"}),
                    *[shortcut(*item) for item in SHORTCUTS]]}]}
    # Messages may quote a long preset or composition name: wrap them rather than widen the dialog.
    # Placed beside the cursor by RefreshSnapBadge while a neighbour snap holds.
    badge = {"class": "/Script/UMG.Border", "name": "SnapBadge", "variable": True,
             "props": dict(surface(PANEL, rgba(*ACCENT, 0.5), 4, "(Left=8,Top=4,Right=8,Bottom=4)"), Visibility="Collapsed"),
             "slot": {"LayoutData": "(Offsets=(Left=0,Top=0,Right=0,Bottom=0))", "bAutoSize": "true"},
             "children": [label("SnapBadgeText", "", 13, GOLD)]}
    confirm_text = text("ConfirmText", "", 14, DIM, variable=True, wrap=True, slot={"Padding": "(Left=0,Top=8,Right=0,Bottom=14)"})
    confirm_text["props"].update(WrapTextAt=560, WrappingPolicy="AllowPerCharacterWrapping")
    confirm = {"class": "/Script/UMG.Border", "name": "Confirm", "variable": True,
               "props": dict(surface(PANEL, rgba(*ACCENT, 0.35), 8, "(Left=24,Top=18,Right=24,Bottom=14)"), Visibility="Collapsed"),
               "slot": {"LayoutData": "(Anchors=(Minimum=(X=0.5,Y=0.4),Maximum=(X=0.5,Y=0.4)),Alignment=(X=0.5,Y=0.5))",
                        "bAutoSize": "true"},
               "children": [{"class": "/Script/UMG.VerticalBox", "name": "ConfirmColumn", "children": [
                   text("ConfirmTitle", "Save your Den changes?", 20, GOLD, role="title"),
                   confirm_text,
                   {"class": "/Script/UMG.HorizontalBox", "name": "ConfirmRow",
                    "children": [button(n, label_, 15, style) for n, label_, _, style in CONFIRM]},
               ]}]}
    nodes, links = [], []
    events = [(n, e) for n, _, e, _ in LIBRARY + TOOLS + QUICK_CONTROLS + LAYERS] + [(n, e) for n, e, _, _ in MENU] \
        + [("Save", "save"), ("Exit", "exit"), ("CloseHelp", "help")] + [(n, e) for n, _, e, _ in CONFIRM]
    for name, event in events:
        nodes.append({"id": name, "kind": "bound_event", "widget": name, "delegate": "OnClicked"})
        nodes.append({"id": name + "_event", "kind": "call", "function": "self:Native_Event", "defaults": {"Name": event}})
        links.append([name + ".then", name + "_event.execute"])
    return {
        "kind": "widget", "path": ROOT + "WBP_DenToolbar",
        "tree": {"class": "/Script/UMG.CanvasPanel", "name": "Root", "children": [panel, tabs, feedback, badge, help_panel, confirm]},
        "functions": [{"name": "Native_Event", "inputs": [{"name": "Name", "type": "string"}, {"name": "Arg", "type": "string"}]}],
        "graph": {"nodes": nodes, "links": links},
    }


ITEM = ROOT + "BP_DenCatalogItem"


def catalog_item():
    """One row of a catalog list. Metadata is carried in string fields."""
    return {"kind": "blueprint", "path": ITEM, "parent": "/Script/CoreUObject.Object",
            "variables": [{"name": n, "type": "string", "default": ""} for n in ("Key", "Title", "Detail", "Preview")]
            # The thumbnail (a texture imported from Saved\ZComDen\thumbs), or none yet.
            + [{"name": "Thumb", "type": "object:/Script/Engine.Texture2D"}]}


# Entry backings, multiplied over a white rounded brush: chosen, hovered and idle.
ENTRY_COLORS = (("gold", rgba(*ACCENT, 0.30)), ("over", rgba(1, 1, 1, 0.10)), ("idle", rgba(1, 1, 1, 0.045)))


def list_entry(name, tree, fields, picture=None):
    """A ListView/TileView entry: copies the item's strings into its text blocks when it's assigned, and with
    `picture` (an Image widget) shows the item's Thumb there, or hides the image while there's none."""
    nodes = [{"id": "set", "kind": "event", "name": "OnListItemObjectSet"},
             {"id": "cast", "kind": "cast", "class": ITEM}]
    links = [["set.then", "cast.execute"], ["set.ListItemObject", "cast.Object"]]
    last = "cast.then"
    for i, (field, widget) in enumerate(fields):
        nodes += [{"id": f"get{i}", "kind": "get", "var": f"{ITEM}:{field}"},
                  {"id": f"w{i}", "kind": "get", "var": widget},
                  {"id": f"text{i}", "kind": "call", "function": "/Script/UMG.TextBlock:SetText"}]
        links += [[last, f"text{i}.execute"], ["cast.AsBP Den Catalog Item", f"get{i}.self"],
                  [f"get{i}.{field}", f"text{i}.InText"], [f"w{i}.{widget}", f"text{i}.self"]]
        last = f"text{i}.then"
    if picture:
        nodes += [{"id": "thumb", "kind": "get", "var": f"{ITEM}:Thumb"},
                  {"id": "has", "kind": "call", "function": "/Script/Engine.KismetSystemLibrary:IsValid"},
                  {"id": "if", "kind": "branch"},
                  {"id": "pic", "kind": "get", "var": picture},
                  {"id": "brush", "kind": "call", "function": "/Script/UMG.Image:SetBrushFromTexture", "defaults": {"bMatchSize": "false"}},
                  {"id": "show", "kind": "call", "function": "/Script/UMG.Widget:SetVisibility", "defaults": {"InVisibility": "Visible"}},
                  {"id": "hide", "kind": "call", "function": "/Script/UMG.Widget:SetVisibility", "defaults": {"InVisibility": "Hidden"}}]
        links += [["cast.AsBP Den Catalog Item", "thumb.self"], ["thumb.Thumb", "has.Object"],
                  [last, "if.execute"], ["has.ReturnValue", "if.Condition"],
                  ["if.then", "brush.execute"], ["thumb.Thumb", "brush.Texture"], [f"pic.{picture}", "brush.self"],
                  ["brush.then", "show.execute"], [f"pic.{picture}", "show.self"],
                  ["if.else", "hide.execute"], [f"pic.{picture}", "hide.self"]]
    if picture:
        nodes += [{"id": "placeholder", "kind": "get", "var": "Placeholder"},
                  {"id": "placeholderhide", "kind": "call", "function": "/Script/UMG.Widget:SetVisibility", "defaults": {"InVisibility": "Hidden"}},
                  {"id": "placeholdershow", "kind": "call", "function": "/Script/UMG.Widget:SetVisibility", "defaults": {"InVisibility": "Visible"}}]
        links += [["show.then", "placeholderhide.execute"], ["hide.then", "placeholdershow.execute"],
                  ["placeholder.Placeholder", "placeholderhide.self"], ["placeholder.Placeholder", "placeholdershow.self"]]
    nodes += [{"id": "tooltip", "kind": "call", "function": "/Script/UMG.Widget:SetToolTipText"}]
    # The assigned title is also available in full when a label has to clip.
    links = [["tooltip.then" if source == "cast.then" and target == "text0.execute" else source, target] for source, target in links]
    links += [["cast.then", "tooltip.execute"], ["get0.Title", "tooltip.InToolTipText"]]
    # Entry selection/hover feedback stays in Blueprint; recycled tiles use their assigned item.
    tree["variable"] = True
    refresh_nodes = [
        {"id": "selected", "kind": "get", "var": "Chosen"},
        {"id": "hovered", "kind": "get", "var": "Hovered"},
        {"id": "frame", "kind": "get", "var": "Frame"},
        {"id": "chosen", "kind": "branch"}, {"id": "hover", "kind": "branch"},
    ]
    refresh_links = [["entry.then", "chosen.execute"], ["selected.Chosen", "chosen.Condition"],
                     ["chosen.else", "hover.execute"], ["hovered.Hovered", "hover.Condition"]]
    for (ident, color), pin in zip(ENTRY_COLORS, ("chosen.then", "hover.then", "hover.else")):
        refresh_nodes.append({"id": ident, "kind": "call", "function": "/Script/UMG.Border:SetBrushColor", "defaults": {"InBrushColor": color}})
        refresh_links += [[pin, ident+".execute"], ["frame.Frame", ident+".self"]]
    for ident, event, var, value in (("selected", "BP_OnItemSelectionChanged", "Chosen", None),
                                     ("enter", "OnMouseEnter", "Hovered", "true"), ("leave", "OnMouseLeave", "Hovered", "false")):
        nodes += [{"id": ident, "kind": "event", "name": event},
                  {"id": ident+"set", "kind": "set", "var": var, "defaults": {var: value} if value else {}},
                  {"id": ident+"refresh", "kind": "call", "function": "self:RefreshAppearance"}]
        links += [[ident+".then", ident+"set.execute"], [ident+"set.then", ident+"refresh.execute"]]
        if value is None: links.append([ident+".bIsSelected", ident+"set."+var])
    # ListView recycles widgets without sending a false selection event first.
    # Clear visual state at release so a later category cannot inherit a gold row.
    nodes += [{"id": "released", "kind": "event", "name": "BP_OnEntryReleased"},
              {"id": "releasechosen", "kind": "set", "var": "Chosen", "defaults": {"Chosen": "false"}},
              {"id": "releasehover", "kind": "set", "var": "Hovered", "defaults": {"Hovered": "false"}},
              {"id": "releaserefresh", "kind": "call", "function": "self:RefreshAppearance"}]
    links += [["released.then", "releasechosen.execute"], ["releasechosen.then", "releasehover.execute"],
              ["releasehover.then", "releaserefresh.execute"]]
    return {"kind": "widget", "path": ROOT + name, "interfaces": ["/Script/UMG.UserObjectListEntry"],
            "variables": [{"name": "Chosen", "type": "bool", "default": "false"}, {"name": "Hovered", "type": "bool", "default": "false"}],
            "functions": [{"name": "RefreshAppearance", "nodes": refresh_nodes, "links": refresh_links}],
            "tree": tree, "graph": {"nodes": nodes, "links": links}}


def entry_frame(children, padding, radius=6):
    return {"class": "/Script/UMG.Border", "name": "Frame", "variable": True,
            "props": surface(rgba(1, 1, 1), None, radius, padding, tint=ENTRY_COLORS[2][1]), "children": children}


def catalog_entry():
    picture = {"class": "/Script/UMG.SizeBox", "name": "PictureBox",
               "props": {"WidthOverride": PICTURE, "bOverride_WidthOverride": "true", "HeightOverride": PICTURE, "bOverride_HeightOverride": "true"},
               "slot": {"HorizontalAlignment": "HAlign_Center", "Padding": "(Left=0,Top=0,Right=0,Bottom=6)"},
               "children": [{"class": "/Script/UMG.Overlay", "name": "PreviewLayers", "children": [
                   text("Placeholder", "Loading preview…", 11, DIM, wrap=True, slot={"HorizontalAlignment": "HAlign_Center", "VerticalAlignment": "VAlign_Center"}),
                   {"class": "/Script/UMG.Image", "name": "Picture", "variable": True, "slot": {"HorizontalAlignment": "HAlign_Fill", "VerticalAlignment": "VAlign_Fill"}, "props": {"Visibility": "Hidden"}}]}]}
    tree = entry_frame([{"class": "/Script/UMG.VerticalBox", "name": "Lines", "children": [
        picture,
        {"class": "/Script/UMG.SizeBox", "name": "NameBox", "props": {"HeightOverride": 44, "bOverride_HeightOverride": "true", "Clipping": "ClipToBounds"},
         "slot": {"Padding": "(Left=0,Top=0,Right=0,Bottom=4)"},
         "children": [text("Name", "", 13, variable=True, wrap=True)]},
        {"class": "/Script/UMG.SizeBox", "name": "SizeBox", "props": {"HeightOverride": 40, "bOverride_HeightOverride": "true", "Clipping": "ClipToBounds"},
         "children": [text("Size", "", 11, DIM, variable=True, wrap=True)]}]}], "(Left=5,Top=5,Right=5,Bottom=5)")
    tree["variable"] = True
    tree = {"class": "/Script/UMG.Border", "name": "CardMargin", "props": {"BrushColor": "(R=0,G=0,B=0,A=0)",
            "Padding": "(Left=3,Top=3,Right=3,Bottom=3)"}, "children": [tree]}
    return list_entry("WBP_DenCatalogEntry", tree, [("Title", "Name"), ("Detail", "Size"), ("Preview", "Placeholder")], picture="Picture")


def catalog_shelf():
    """A row of a vertical list: presets and unavailable props."""
    tree = entry_frame([text("Label", "", 13, variable=True, wrap=True)], "(Left=10,Top=7,Right=10,Bottom=7)")
    tree = {"class": "/Script/UMG.Border", "name": "RowMargin", "props": {"BrushColor": "(R=0,G=0,B=0,A=0)",
            "Padding": "(Left=0,Top=0,Right=0,Bottom=3)"}, "children": [tree]}
    return list_entry("WBP_DenCatalogShelf", tree, [("Title", "Label")])


def catalog_chip():
    """A catalog collection in the horizontal strip above the cards."""
    tree = entry_frame([text("Label", "", 13, variable=True)], "(Left=11,Top=5,Right=11,Bottom=5)", 13)
    tree = {"class": "/Script/UMG.Border", "name": "ChipMargin", "props": {"BrushColor": "(R=0,G=0,B=0,A=0)",
            "Padding": "(Left=0,Top=0,Right=6,Bottom=0)"}, "children": [tree]}
    return list_entry("WBP_DenCatalogChip", tree, [("Title", "Label")])


def cards(name):
    """A TileView of catalog-style cards filling the rest of a library panel."""
    return {"class": "/Script/UMG.TileView", "name": name, "variable": True,
            "props": {"bIsFocusable": "false", "SelectionMode": "Single", "EntryWidgetClass": ROOT + "WBP_DenCatalogEntry",
                      "EntryWidth": TILE_WIDTH, "EntryHeight": TILE_HEIGHT, **scrollbar()},
            "slot": {"Size": "(SizeRule=Fill,Value=1.0)", "Padding": "(Left=0,Top=4,Right=0,Bottom=4)"}}


def library_panel(title, children):
    """A panel in the library dock beside the tabs (only one shows at a time)."""
    panel = {"class": "/Script/UMG.Border", "name": "Panel",
             "props": surface(PANEL, EDGE, 8, "(Left=14,Top=14,Right=14,Bottom=12)"),
             # Pinned to the left edge, stretched top to bottom: Left is the x position and Right is the width;
             # Top and Bottom are margins (below the menu bar, above the status bar).
             "slot": {"LayoutData": f"(Anchors=(Minimum=(X=0,Y=0),Maximum=(X=0,Y=1)),Offsets=(Left={LIBRARY_LEFT},Top=80,Right={LIBRARY_WIDTH},Bottom=58))"},
             "children": [{"class": "/Script/UMG.VerticalBox", "name": "Column", "children": [
                 text("Title", title, 20, GOLD, role="title", slot={"Padding": "(Left=0,Top=0,Right=0,Bottom=10)"})] + children}]}
    return {"class": "/Script/UMG.CanvasPanel", "name": "Root", "children": [panel]}


def inspector_panel(name, children, visibility=None):
    """A panel in the inspector dock on the right."""
    props = {"WidthOverride": INSPECTOR_WIDTH, "bOverride_WidthOverride": "true"}
    if visibility:
        props["Visibility"] = visibility
    return {"class": "/Script/UMG.SizeBox", "name": name, "variable": True, "props": props,
            "slot": {"LayoutData": f"(Anchors=(Minimum=(X=1,Y=0),Maximum=(X=1,Y=1)),Offsets=(Left={-12 - INSPECTOR_WIDTH},Top=80,Right={INSPECTOR_WIDTH},Bottom=58))"},
            "children": [{"class": "/Script/UMG.Border", "name": "Frame", "props": dict(surface(PANEL, EDGE, 8, "(Left=18,Top=16,Right=18,Bottom=16)"), Clipping="ClipToBounds"),
                          "children": [{"class": "/Script/UMG.VerticalBox", "name": "Column", "children": children}]}]}


def catalog():
    """The catalog panel: search, a strip of collections (folders), and the meshes in the chosen one."""
    lists = {"bIsFocusable": "false", "SelectionMode": "Single"}
    # Room for the chips plus a thin scrollbar under them when the strip overflows.
    shelves = {"class": "/Script/UMG.SizeBox", "name": "ShelfBox", "props": {"HeightOverride": 42, "bOverride_HeightOverride": "true"},
               "slot": {"Padding": "(Left=0,Top=0,Right=0,Bottom=12)"},
               "children": [{"class": "/Script/UMG.ListView", "name": "Shelves", "variable": True,
                             "props": dict(lists, EntryWidgetClass=ROOT + "WBP_DenCatalogChip", Orientation="Orient_Horizontal", **scrollbar(3))}]}
    tree = library_panel("Catalog", [
        {"class": "/Script/UMG.EditableTextBox", "name": "Search", "variable": True,
         "props": dict(field_style(), HintText="Search props, packs, tags…"),
         "slot": {"Padding": "(Left=0,Top=0,Right=0,Bottom=10)"}},
        shelves,
        text("Empty", "", 14, DIM, variable=True, wrap=True),
        cards("Items"),
        text("Footer", "", 12, DIM, variable=True, wrap=True, slot={"Padding": "(Left=0,Top=6,Right=0,Bottom=0)"}),
    ])
    nodes = [{"id": "search", "kind": "bound_event", "widget": "Search", "delegate": "OnTextChanged"},
             {"id": "search_event", "kind": "call", "function": "self:Native_Event", "defaults": {"Name": "search"}}]
    links = [["search.then", "search_event.execute"], ["search.Text", "search_event.Arg"]]
    for widget, event in (("Shelves", "shelf"), ("Items", "item")):
        w = widget.lower()
        nodes += [{"id": w, "kind": "bound_event", "widget": widget, "delegate": "BP_OnItemClicked"},
                  {"id": w + "_cast", "kind": "cast", "class": ITEM},
                  {"id": w + "_key", "kind": "get", "var": f"{ITEM}:Key"},
                  {"id": w + "_event", "kind": "call", "function": "self:Native_Event", "defaults": {"Name": event}}]
        links += [[w + ".then", w + "_cast.execute"], [w + ".Item", w + "_cast.Object"],
                  [w + "_cast.then", w + "_event.execute"], [w + "_cast.AsBP Den Catalog Item", w + "_key.self"],
                  [w + "_key.Key", w + "_event.Arg"]]
    return {"kind": "widget", "path": ROOT + "WBP_DenCatalog", "tree": tree,
            "functions": [{"name": "Native_Event", "inputs": [{"name": "Name", "type": "string"}, {"name": "Arg", "type": "string"}]}],
            "graph": {"nodes": nodes, "links": links}}


NATIVE_EVENT = [{"name": "Native_Event", "inputs": [{"name": "Name", "type": "string"}, {"name": "Arg", "type": "string"}]}]


class Graph:
    """Bound events that call Native_Event(name, arg)."""

    def __init__(self):
        self.nodes, self.links = [], []

    def click(self, widget, event):
        """A button: Native_Event(event, "")."""
        self.nodes += [{"id": widget, "kind": "bound_event", "widget": widget, "delegate": "OnClicked"},
                       {"id": widget + "_event", "kind": "call", "function": "self:Native_Event", "defaults": {"Name": event}}]
        self.links.append([widget + ".then", widget + "_event.execute"])

    def click_with_text(self, widget, event, box):
        """A button that sends the text of an EditableTextBox along."""
        self.click(widget, event)
        self.nodes += [{"id": widget + "_box", "kind": "get", "var": box},
                       {"id": widget + "_text", "kind": "call", "function": "/Script/UMG.EditableTextBox:GetText"}]
        self.links += [[widget + "_box." + box, widget + "_text.self"], [widget + "_text.ReturnValue", widget + "_event.Arg"]]

    def commit(self, box, event):
        """An EditableTextBox: Native_Event(event, text) when Enter is pressed or it loses focus."""
        self.nodes += [{"id": box, "kind": "bound_event", "widget": box, "delegate": "OnTextCommitted"},
                       {"id": box + "_event", "kind": "call", "function": "self:Native_Event", "defaults": {"Name": event}}]
        self.links += [[box + ".then", box + "_event.execute"], [box + ".Text", box + "_event.Arg"]]

    def item(self, view, event):
        """A ListView/TileView: Native_Event(event, item.Key) for a clicked item."""
        w = view.lower()
        self.nodes += [{"id": w, "kind": "bound_event", "widget": view, "delegate": "BP_OnItemClicked"},
                       {"id": w + "_cast", "kind": "cast", "class": ITEM},
                       {"id": w + "_key", "kind": "get", "var": f"{ITEM}:Key"},
                       {"id": w + "_event", "kind": "call", "function": "self:Native_Event", "defaults": {"Name": event}}]
        self.links += [[w + ".then", w + "_cast.execute"], [w + ".Item", w + "_cast.Object"],
                       [w + "_cast.then", w + "_event.execute"], [w + "_cast.AsBP Den Catalog Item", w + "_key.self"],
                       [w + "_key.Key", w + "_event.Arg"]]

    def spec(self):
        return {"nodes": self.nodes, "links": self.links}


def field_style(left=12, right=10, size=14):
    props = {"WidgetStyle.ForegroundColor": WHITE, "WidgetStyle.FocusedForegroundColor": WHITE,
             "WidgetStyle.TextStyle.ColorAndOpacity": WHITE, "WidgetStyle.TextStyle.Font.Size": size,
             "WidgetStyle.Padding": f"(Left={left},Top=8,Right={right},Bottom=8)"}
    for state in ("Normal", "Hovered", "Focused", "ReadOnly"):
        edge = rgba(*ACCENT, 0.8) if state == "Focused" else rgba(1, 1, 1, 0.2 if state == "Hovered" else 0.12)
        for key, value in rounded(rgba(0, 0, 0, 0.35), edge, 4).items():
            props[f"WidgetStyle.BackgroundImage{state}.{key}"] = value
    return props


def box(name, hint, width=None, select_all=False, slot=None):
    w = {"class": "/Script/UMG.EditableTextBox", "name": name, "variable": True,
         "props": dict(field_style(), HintText=hint)}
    if select_all:
        w["props"]["SelectAllTextWhenFocused"] = "true"
    if width:
        w = {"class": "/Script/UMG.SizeBox", "name": name + "Box",
             "props": {"WidthOverride": width, "bOverride_WidthOverride": "true"}, "children": [w]}
    if slot:
        w["slot"] = slot
    return w


def row(name, children, padding="(Left=0,Top=6,Right=0,Bottom=6)"):
    return {"class": "/Script/UMG.HorizontalBox", "name": name, "slot": {"Padding": padding}, "children": children}


def entry_row(name, field, action, padding="(Left=0,Top=6,Right=0,Bottom=6)"):
    """A text field that takes the remaining width, then its button."""
    field["slot"] = {"Size": "(SizeRule=Fill,Value=1)", "Padding": "(Left=0,Top=0,Right=6,Bottom=0)", "VerticalAlignment": "VAlign_Center"}
    action["slot"] = {"VerticalAlignment": "VAlign_Center"}
    return row(name, [field, action], padding)


def layouts():
    g = Graph()
    tree = library_panel("Layouts", [
        text("ScopeText", "", 14, variable=True, wrap=True, slot={"Padding": "(Left=0,Top=0,Right=0,Bottom=6)"}),
        row("ScopeRow", [button("ScopeButton", "Create campaign layout", 14)]),
        text("ScopeHint", "Start with a copy of your current Den. Returning to Home removes the campaign copy; a backup is kept.", 12, DIM, wrap=True),
        divider("PresetsDivider", vertical=False),
        label("PresetsTitle", "Presets", slot={"Padding": "(Left=0,Top=0,Right=0,Bottom=6)"}),
        text("PresetsHint", "Keep a named version of your Den. Apply a preset to preview it, then Save to keep it. Undo brings back the previous layout.", 12, DIM, wrap=True),
        entry_row("SaveRow", box("PresetName", "New preset name"), button("SavePreset", "Create", 14)),
        {"class": "/Script/UMG.ListView", "name": "Presets", "variable": True,
         "props": {"bIsFocusable": "false", "SelectionMode": "Single", "EntryWidgetClass": ROOT + "WBP_DenCatalogShelf", **scrollbar()},
         "slot": {"Size": "(SizeRule=Fill,Value=1.0)", "Padding": "(Left=0,Top=4,Right=0,Bottom=4)"}},
        row("PresetRow", [button("LoadPreset", "Load selected", 14), button("DeletePreset", "Delete selected", 14)]),
        text("Footer", "", 12, DIM, variable=True, wrap=True),
    ])
    g.click("ScopeButton", "scope")
    g.click_with_text("SavePreset", "save_preset", "PresetName")
    g.commit("PresetName", "save_preset")
    g.item("Presets", "preset")
    g.click("LoadPreset", "load_preset")
    g.click("DeletePreset", "delete_preset")
    return {"kind": "widget", "path": ROOT + "WBP_DenLayouts", "tree": tree, "functions": NATIVE_EVENT, "graph": g.spec()}


def storeroom():
    g = Graph()
    tree = library_panel("Storeroom", [
        text("StoredText", "", 14, variable=True, wrap=True, slot={"Padding": "(Left=0,Top=0,Right=0,Bottom=8)"}),
        box("StoredSearch", "Search stored props…"),
        cards("Stored"),
        row("StoredRow", [button("RestoreAll", "Restore everything", 14)]),
        divider("DormantDivider", vertical=False),
        label("DormantTitle", "Unavailable props", slot={"Padding": "(Left=0,Top=0,Right=0,Bottom=4)"}),
        text("DormantText", "", 12, DIM, variable=True, wrap=True),
        {"class": "/Script/UMG.SizeBox", "name": "DormantBox",
         "props": {"HeightOverride": 150, "bOverride_HeightOverride": "true"},
         "slot": {"Padding": "(Left=0,Top=6,Right=0,Bottom=6)"},
         "children": [{"class": "/Script/UMG.ListView", "name": "Dormant", "variable": True,
                       "props": {"bIsFocusable": "false", "SelectionMode": "Single",
                                 "EntryWidgetClass": ROOT + "WBP_DenCatalogShelf", **scrollbar()}}]},
        text("Footer", "", 12, DIM, variable=True, wrap=True),
    ])
    g.nodes += [{"id": "storedsearch", "kind": "bound_event", "widget": "StoredSearch", "delegate": "OnTextChanged"},
                {"id": "storedsearchcall", "kind": "call", "function": "self:Native_Event", "defaults": {"Name": "stored_search"}}]
    g.links += [["storedsearch.then", "storedsearchcall.execute"], ["storedsearch.Text", "storedsearchcall.Arg"]]
    g.item("Stored", "restore")
    g.click("RestoreAll", "restore_all")
    g.item("Dormant", "forget")
    return {"kind": "widget", "path": ROOT + "WBP_DenStoreroom", "tree": tree, "functions": NATIVE_EVENT, "graph": g.spec()}


FIELDS = [("X", "set_x"), ("Y", "set_y"), ("Z", "set_z"), ("Pitch", "set_pitch"), ("Yaw", "set_yaw"), ("Roll", "set_roll"),
          ("Scale", "set_scale")]
FIELD_TAGS = {"X": "X", "Y": "Y", "Z": "Z", "Pitch": "P", "Yaw": "Y", "Roll": "R", "Scale": "×"}


def axis_field(name, gap=6):
    """A numeric field with its axis letter on a tag at the left: coloured for X/Y/Z."""
    color = AXES.get(name)
    tag = {"class": "/Script/UMG.Border", "name": name + "Tag",
           "props": dict(surface(rgba(*color) if color else CLEAR, None, 4, "(Left=0,Top=0,Right=0,Bottom=0)", (4, 0, 0, 4)),
                         Visibility="HitTestInvisible", HorizontalAlignment="HAlign_Center", VerticalAlignment="VAlign_Center"),
           "slot": {"HorizontalAlignment": "HAlign_Left", "VerticalAlignment": "VAlign_Fill"},
           "children": [{"class": "/Script/UMG.SizeBox", "name": name + "TagSize", "props": {"WidthOverride": 20, "bOverride_WidthOverride": "true"},
                         "slot": {"HorizontalAlignment": "HAlign_Center", "VerticalAlignment": "VAlign_Center"},
                         "children": [label(name + "Label", FIELD_TAGS[name], 13, WHITE if color else DIM,
                                            slot={"HorizontalAlignment": "HAlign_Center", "VerticalAlignment": "VAlign_Center"})]}]}
    field = {"class": "/Script/UMG.EditableTextBox", "name": "Field" + name, "variable": True,
             "props": dict(field_style(26, 6, 13), HintText=name, SelectAllTextWhenFocused="true"),
             "slot": {"HorizontalAlignment": "HAlign_Fill", "VerticalAlignment": "VAlign_Fill"}}
    return {"class": "/Script/UMG.Overlay", "name": name + "Cell",
            "slot": {"Size": "(SizeRule=Fill,Value=1)", "Padding": f"(Left=0,Top=0,Right={gap},Bottom=0)"},
            "children": [field, tag]}


def transform():
    """Selection inspector; grouped fields keep their existing commit events."""
    g = Graph()
    groups = []
    for title, fields in (("Position · cm", FIELDS[:3]), ("Rotation · degrees", FIELDS[3:6]), ("Scale", FIELDS[6:])):
        for name, event in fields:
            g.commit("Field" + name, event)
        groups.append(label("Group" + fields[0][0], title, slot={"Padding": "(Left=0,Top=12,Right=0,Bottom=6)"}))
        if title.startswith("Position"):  # world coordinates can be long: one full-width row per axis
            groups += [row("Fields" + name, [axis_field(name, 0)], "(Left=0,Top=0,Right=0,Bottom=6)") for name, _ in fields]
            continue
        if title.startswith("Rotation"):
            pivot = button("RotationPivot", "Pivot: Centre", 13)
            pivot["props"]["ToolTipText"] = "Rotate around the bottom, centre or top of the prop. Original uses the mesh's authored origin."
            groups.append(pivot)
            g.click("RotationPivot", "rotation_pivot")
        cells = [axis_field(name) for name, _ in fields]
        if len(cells) == 1:  # keep a single field the width of one column
            cells += [{"class": "/Script/UMG.Spacer", "name": "ScaleGap", "slot": {"Size": "(SizeRule=Fill,Value=2)"}}]
        groups.append(row("Fields" + fields[0][0], cells, "(Left=0,Top=0,Right=0,Bottom=0)"))
    edits = [("Copy", "Duplicate", "duplicate", "duplicate"), ("Store", "Store", "store", "store"),
             ("Reset", "Reset", "reset", "reset"), ("Focus", "Focus", "focus", "focus")]
    actions = []
    for i, (name, caption, event, icon_name) in enumerate(edits):
        g.click(name, event)
        widget = button(name, caption, 14, "plain", icon_name)
        widget["slot"] = {"Row": i // 2, "Column": i % 2, "HorizontalAlignment": "HAlign_Fill", "VerticalAlignment": "VAlign_Fill"}
        actions.append(widget)
    selection = text("Selection", "", 18, GOLD, role="title", wrap=True, slot={"Padding": "(Left=0,Top=4,Right=0,Bottom=0)"})
    selection["props"]["WrappingPolicy"] = "AllowPerCharacterWrapping"  # asset names are one long "word"
    # Closing the inspector deselects the prop, as Esc does.
    close = button("CloseInspector", "Close", 13, "ghost", color=SOFT, tooltip="Deselect this prop")
    close["slot"] = {"VerticalAlignment": "VAlign_Center"}
    g.click("CloseInspector", "deselect")
    tree = inspector_panel("Panel", [
        row("Header", [label("Title", "Selected prop", 12, slot={"Size": "(SizeRule=Fill,Value=1)", "VerticalAlignment": "VAlign_Center"}), close],
            "(Left=0,Top=0,Right=0,Bottom=0)"),
        selection,
        divider("FieldsDivider", vertical=False),
    ] + groups + [
        text("ApplyHint", "Press Enter to apply a value.", 12, DIM, slot={"Padding": "(Left=0,Top=10,Right=0,Bottom=0)"}),
        divider("ActionsDivider", vertical=False),
        {"class": "/Script/UMG.UniformGridPanel", "name": "Actions", "props": {"SlotPadding": "(Left=0,Top=0,Right=6,Bottom=6)"}, "children": actions},
    ], "Collapsed")
    return {"kind": "widget", "path": ROOT + "WBP_DenTransform",
            "tree": {"class": "/Script/UMG.CanvasPanel", "name": "Root", "children": [tree]},
            "functions": NATIVE_EVENT, "graph": g.spec()}
