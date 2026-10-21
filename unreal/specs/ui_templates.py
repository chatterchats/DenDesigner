"""Native editor widget trees, input actions and camera rig templates.

Runtime editor assets attach the event bus, styling and input focus guards.
Generate the complete spec set with runtime.py.
"""
import json

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
    # Chorded wheel mappings come first: they block the plain wheel mapping listed after them.
    {"action": "IA_Den_RotateFine", "key": "MouseWheelAxis", "triggers": [chord("IA_Den_Fast")]},
    {"action": "IA_Den_Scale", "key": "MouseWheelAxis", "triggers": [chord("IA_Den_Alt")]},
    {"action": "IA_Den_Rotate", "key": "MouseWheelAxis"},
    {"action": "IA_Den_Rotate", "key": "Q", "modifiers": [negate()], "triggers": [repeat(ROTATE_REPEAT)]},
    {"action": "IA_Den_Rotate", "key": "E", "triggers": [repeat(ROTATE_REPEAT)]},
    # Alt+wheel didn't scale in game (2026-10-18), so +/- (and the keypad's) scale too.
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


PANEL = "(R=0.012,G=0.016,B=0.024,A=1)"
BUTTON = "(R=1,G=1,B=1,A=1)"  # the brushes below carry the colours


def brush(r, g, b, outline):
    return {"DrawAs": "RoundedBox", "TintColor": f"(SpecifiedColor=(R={r},G={g},B={b},A=1))",
            "OutlineSettings": f"(CornerRadii=(X=3,Y=3,Z=3,W=3),Color=(SpecifiedColor=(R={outline[0]},G={outline[1]},B={outline[2]},A=1)),"
                               "Width=1.0,RoundingType=FixedRadius)"}


# Flat rounded buttons in the game's dark slate, with a lighter edge; hover lifts them, press darkens them.
BUTTON_STYLE = {}
for state, (rgb, edge) in {"Normal": ((0.055, 0.07, 0.095), (0.22, 0.27, 0.34)),
                           "Hovered": ((0.11, 0.14, 0.19), (0.75, 0.6, 0.3)),
                           "Pressed": ((0.03, 0.04, 0.055), (0.75, 0.6, 0.3))}.items():
    for key, value in brush(*rgb, edge).items():
        BUTTON_STYLE[f"WidgetStyle.{state}.{key}"] = value
BUTTON_STYLE["WidgetStyle.NormalPadding"] = "(Left=12,Top=7,Right=12,Bottom=7)"
BUTTON_STYLE["WidgetStyle.PressedPadding"] = "(Left=12,Top=8,Right=12,Bottom=6)"
WHITE = "(SpecifiedColor=(R=0.92,G=0.94,B=0.97,A=1),ColorUseRule=UseColor_Specified)"
DIM = "(SpecifiedColor=(R=0.62,G=0.67,B=0.74,A=1),ColorUseRule=UseColor_Specified)"
INK = "(SpecifiedColor=(R=0.02,G=0.025,B=0.035,A=1),ColorUseRule=UseColor_Specified)"
GOLD = "(SpecifiedColor=(R=1,G=0.78,B=0.35,A=1),ColorUseRule=UseColor_Specified)"

HINTS = ("WASD fly, Space/Ctrl up/down, Shift fast, hold RMB to look\n"
         "LMB select and drag (Shift: up/down), wheel or Q/E rotate (Shift: fine), +/- scale\n"
         "Arrows/PgUp/PgDn nudge, G snap, X store, C copy, R reset, Z/Y undo/redo, F focus, Esc back\n"
         "Tab catalog: click an item, then click in the Den to place it (Shift+click places more)\n"
         "H storeroom (stored props), L layouts (this campaign's own layout, presets), T gimbal: move / rotate / scale / off")

# Toolbar buttons: (widget name, label, event)
TOOLBAR = [("Catalog", "Catalog", "catalog"), ("Storeroom", "Storeroom", "storeroom"), ("Layouts", "Layouts", "layouts"),
           ("Undo", "Undo", "undo"), ("Redo", "Redo", "redo"), ("Help", "Help", "help"),
           ("Save", "Save", "save"), ("Exit", "Done", "exit")]
QUICK_CONTROLS = [("Snap", "Grid: Off", "snap"), ("Reach", "Range: 20m", "reach"),
           ("Floors", "Floors: On", "floors"), ("Walls", "Walls: Off", "walls"), ("Lock", "Structure: Off", "lock")]

CONFIRM = [("ConfirmSave", "Save", "confirm_save"), ("ConfirmDiscard", "Discard", "confirm_discard"),
           ("ConfirmCancel", "Keep editing", "confirm_cancel")]


def text(name, value, size, color=WHITE, variable=True, slot=None, wrap=False):
    """Every text block is a variable: the runtime style service assigns the game's fonts."""
    w = {"class": "/Script/UMG.TextBlock", "name": name, "props": {"Text": value, "Font.Size": size, "ColorAndOpacity": color}}
    if wrap:
        w["props"]["AutoWrapText"] = "true"
    if variable:
        w["variable"] = True
    if slot:
        w["slot"] = slot
    return w


def button(name, label, size=13):
    caption = text(name + "Label", label, size, variable=True,
                   slot={"HorizontalAlignment": "HAlign_Center", "VerticalAlignment": "VAlign_Center"})
    caption["props"]["Justification"] = "Center"
    return {"class": "/Script/UMG.Button", "name": name, "variable": True,
            # Not focusable: a focused button would take Space (fly up) as a click.
            "props": dict({"BackgroundColor": BUTTON, "IsFocusable": "false"}, **BUTTON_STYLE),
            "slot": {"Padding": "(Left=0,Top=0,Right=6,Bottom=6)"},
            "children": [caption]}


def toolbar():
    def toolbar_button(name, label):
        widget = button(name, label, 14)
        widget["slot"] = {"Padding": "(Left=0,Top=0,Right=6,Bottom=0)", "VerticalAlignment": "VAlign_Center"}
        for state in ("NormalPadding", "PressedPadding"):
            widget["props"]["WidgetStyle." + state] = "(Left=12,Top=4,Right=12,Bottom=4)"
        return widget

    identity = {"class": "/Script/UMG.VerticalBox", "name": "Identity", "slot": {"Padding": "(Left=0,Top=0,Right=28,Bottom=0)", "VerticalAlignment": "VAlign_Center"},
                "children": [text("Title", "DEN DESIGNER", 20, GOLD)]}
    panel = {"class": "/Script/UMG.Border", "name": "Panel",
             "props": {"BrushColor": PANEL, "Padding": "(Left=20,Top=8,Right=14,Bottom=8)"},
             "slot": {"LayoutData": "(Anchors=(Minimum=(X=0,Y=0),Maximum=(X=1,Y=0)),Offsets=(Left=20,Top=16,Right=20,Bottom=56))"},
             "children": [{"class": "/Script/UMG.HorizontalBox", "name": "Navigation", "children":
                           [{"class": "/Script/UMG.HorizontalBox", "name": "NavigationLeft",
                             "slot": {"Size": "(SizeRule=Fill,Value=1)", "HorizontalAlignment": "HAlign_Left"},
                             "children": [identity] + [toolbar_button(n, label) for n, label, _ in TOOLBAR[:3]]},
                            {"class": "/Script/UMG.HorizontalBox", "name": "QuickControls",
                             "children": [toolbar_button(n, label) for n, label, _ in QUICK_CONTROLS]},
                            {"class": "/Script/UMG.HorizontalBox", "name": "NavigationRight",
                             "slot": {"Size": "(SizeRule=Fill,Value=1)", "HorizontalAlignment": "HAlign_Right"},
                             "children": [toolbar_button(n, label) for n, label, _ in TOOLBAR[3:]]}]}]}
    def overlay(name, title, children):
        return {"class": "/Script/UMG.SizeBox", "name": name, "variable": True,
                "props": {"WidthOverride": 380, "bOverride_WidthOverride": "true", "Visibility": "Collapsed"},
                "slot": {"LayoutData": "(Offsets=(Left=20,Top=88,Right=380,Bottom=0))", "bAutoSize": "true"},
                "children": [{"class": "/Script/UMG.Border", "name": name+"Frame",
                              "props": {"BrushColor": PANEL, "Padding": "(Left=20,Top=18,Right=20,Bottom=18)"},
                              "children": [{"class": "/Script/UMG.VerticalBox", "name": name+"Column", "children":
                                            [text(name+"Title", title, 20, GOLD)] + children}]}]}
    help_panel = overlay("HelpPanel", "Controls", [
        {"class": "/Script/UMG.SizeBox", "name": "HelpBody", "props": {"HeightOverride": 480, "bOverride_HeightOverride": "true"},
         "slot": {"Padding": "(Left=0,Top=14,Right=0,Bottom=16)"},
         "children": [{"class": "/Script/UMG.ScrollBox", "name": "HelpScroll", "children": [text("HelpText", "", 13, WHITE, wrap=True)]}]},
        button("CloseHelp", "Back to editing", 14)])
    feedback = {"class": "/Script/UMG.Border", "name": "Feedback",
                "props": {"BrushColor": PANEL, "Padding": "(Left=18,Top=10,Right=18,Bottom=10)"},
                "slot": {"LayoutData": "(Anchors=(Minimum=(X=0,Y=1),Maximum=(X=1,Y=1)),Offsets=(Left=20,Top=-72,Right=20,Bottom=56))"},
                "children": [{"class": "/Script/UMG.VerticalBox", "name": "FeedbackLines", "children": [
                    text("Status", "", 13, WHITE), text("Hints", "Select a prop to edit it, or open the Catalog to add something.", 12, DIM)]}]}
    confirm = {"class": "/Script/UMG.Border", "name": "Confirm", "variable": True,
               "props": {"BrushColor": PANEL, "Padding": "(Left=24,Top=18,Right=24,Bottom=14)", "Visibility": "Collapsed"},
               "slot": {"LayoutData": "(Anchors=(Minimum=(X=0.5,Y=0.4),Maximum=(X=0.5,Y=0.4)),Alignment=(X=0.5,Y=0.5))",
                        "bAutoSize": "true"},
               "children": [{"class": "/Script/UMG.VerticalBox", "name": "ConfirmColumn", "children": [
                   text("ConfirmTitle", "Save your Den changes?", 18, GOLD),
                   text("ConfirmText", "", 13, DIM, variable=True, slot={"Padding": "(Left=0,Top=6,Right=0,Bottom=12)"}),
                   {"class": "/Script/UMG.HorizontalBox", "name": "ConfirmRow",
                    "children": [button(n, label, 15) for n, label, _ in CONFIRM]},
               ]}]}
    nodes, links = [], []
    for name, _, event in TOOLBAR + QUICK_CONTROLS + CONFIRM + [("CloseHelp", "", "help")]:
        nodes.append({"id": name, "kind": "bound_event", "widget": name, "delegate": "OnClicked"})
        nodes.append({"id": name + "_event", "kind": "call", "function": "self:Native_Event", "defaults": {"Name": event}})
        links.append([name + ".then", name + "_event.execute"])
    return {
        "kind": "widget", "path": ROOT + "WBP_DenToolbar",
        "tree": {"class": "/Script/UMG.CanvasPanel", "name": "Root", "children": [panel, help_panel, feedback, confirm]},
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
    for ident, color, pin in (("gold", "(R=0.24,G=0.17,B=0.065,A=1)", "chosen.then"),
                               ("over", "(R=0.10,G=0.13,B=0.18,A=1)", "hover.then"),
                               ("idle", "(R=0.018,G=0.024,B=0.034,A=1)", "hover.else")):
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



def catalog_entry():
    picture = {"class": "/Script/UMG.SizeBox", "name": "PictureBox",
               "props": {"WidthOverride": 136, "bOverride_WidthOverride": "true", "HeightOverride": 136, "bOverride_HeightOverride": "true"},
               "slot": {"HorizontalAlignment": "HAlign_Center", "Padding": "(Left=0,Top=0,Right=0,Bottom=4)"},
               "children": [{"class": "/Script/UMG.Overlay", "name": "PreviewLayers", "children": [
                   text("Placeholder", "Loading preview…", 12, DIM, wrap=True, slot={"HorizontalAlignment": "HAlign_Center", "VerticalAlignment": "VAlign_Center"}),
                   {"class": "/Script/UMG.Image", "name": "Picture", "variable": True, "slot": {"HorizontalAlignment": "HAlign_Fill", "VerticalAlignment": "VAlign_Fill"}, "props": {"Visibility": "Hidden"}}]}]}
    tree = {"class": "/Script/UMG.Border", "name": "Frame",
            "props": {"BrushColor": "(R=0.018,G=0.024,B=0.034,A=1)", "Padding": "(Left=6,Top=6,Right=6,Bottom=6)"},
            "children": [{"class": "/Script/UMG.VerticalBox", "name": "Lines", "children": [
                picture,
                {"class": "/Script/UMG.SizeBox", "name": "NameBox", "props": {"HeightOverride": 44, "bOverride_HeightOverride": "true", "Clipping": "ClipToBounds"},
                 "children": [text("Name", "", 13, variable=True, wrap=True)]},
                text("Size", "", 11, DIM, variable=True, wrap=True)]}]}
    tree["variable"] = True
    tree = {"class": "/Script/UMG.Border", "name": "CardMargin", "props": {"BrushColor": "(R=0,G=0,B=0,A=0)",
            "Padding": "(Left=3,Top=3,Right=3,Bottom=3)"}, "children": [tree]}
    return list_entry("WBP_DenCatalogEntry", tree, [("Title", "Name"), ("Detail", "Size"), ("Preview", "Placeholder")], picture="Picture")


def catalog_shelf():
    tree = {"class": "/Script/UMG.Border", "name": "Frame",
            "props": {"BrushColor": "(R=0,G=0,B=0,A=0)", "Padding": "(Left=10,Top=8,Right=10,Bottom=8)"},
            "children": [text("Label", "", 13, variable=True, wrap=True)]}
    return list_entry("WBP_DenCatalogShelf", tree, [("Title", "Label")])


def catalog():
    """The catalog panel: search, shelves (folders) on the left, meshes on the right."""
    lists = {"bIsFocusable": "false", "SelectionMode": "Single"}
    shelves = {"class": "/Script/UMG.SizeBox", "name": "ShelfBox", "props": {"WidthOverride": 200, "bOverride_WidthOverride": "true"},
               "slot": {"Padding": "(Left=0,Top=0,Right=8,Bottom=0)"},
               "children": [{"class": "/Script/UMG.ListView", "name": "Shelves", "variable": True,
                             "props": dict(lists, EntryWidgetClass=ROOT + "WBP_DenCatalogShelf")}]}
    items = {"class": "/Script/UMG.TileView", "name": "Items", "variable": True,
             "props": dict(lists, EntryWidgetClass=ROOT + "WBP_DenCatalogEntry", EntryWidth=160, EntryHeight=226),
             "slot": {"Size": "(SizeRule=Fill,Value=1.0)"}}
    panel = {"class": "/Script/UMG.Border", "name": "Panel",
             "props": {"BrushColor": PANEL, "Padding": "(Left=14,Top=12,Right=14,Bottom=12)"},
             # Pinned to the right edge, stretched top to bottom: Left is the x position (from the right edge) and
             # Right is the width; Top and Bottom are margins.
             "slot": {"LayoutData": "(Anchors=(Minimum=(X=1,Y=0),Maximum=(X=1,Y=1)),Offsets=(Left=-756,Top=88,Right=736,Bottom=88))"},
             "children": [{"class": "/Script/UMG.VerticalBox", "name": "Column", "children": [
                 text("Title", "Catalog", 20, GOLD),
                 {"class": "/Script/UMG.EditableTextBox", "name": "Search", "variable": True,
                  "props": dict(field_style(), HintText="Search props…"),
                  "slot": {"Padding": "(Left=0,Top=14,Right=0,Bottom=14)"}},
                 text("Empty", "", 14, DIM, variable=True, wrap=True),
                 {"class": "/Script/UMG.HorizontalBox", "name": "Lists", "slot": {"Size": "(SizeRule=Fill,Value=1.0)"},
                  "children": [shelves, items]},
                 text("Footer", "", 11, DIM, variable=True, wrap=True, slot={"Padding": "(Left=0,Top=8,Right=0,Bottom=0)"}),
             ]}]}
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
    return {"kind": "widget", "path": ROOT + "WBP_DenCatalog",
            "tree": {"class": "/Script/UMG.CanvasPanel", "name": "Root", "children": [panel]},
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



def field_style():
    props = {"WidgetStyle.ForegroundColor": WHITE, "WidgetStyle.FocusedForegroundColor": WHITE,
             "WidgetStyle.TextStyle.ColorAndOpacity": WHITE, "WidgetStyle.TextStyle.Font.Size": 14,
             "WidgetStyle.Padding": "(Left=12,Top=8,Right=12,Bottom=8)"}
    for state in ("Normal", "Hovered", "Focused", "ReadOnly"):
        edge = (0.65, 0.48, 0.18) if state == "Focused" else (0.13, 0.16, 0.21)
        for key, value in brush(0.025, 0.033, 0.046, edge).items():
            props[f"WidgetStyle.BackgroundImage{state}.{key}"] = value
    return props

def box(name, hint, width=None, select_all=False):
    w = {"class": "/Script/UMG.EditableTextBox", "name": name, "variable": True,
         "props": dict(field_style(), HintText=hint)}
    if select_all:
        w["props"]["SelectAllTextWhenFocused"] = "true"
    if width:
        return {"class": "/Script/UMG.SizeBox", "name": name + "Box",
                "props": {"WidthOverride": width, "bOverride_WidthOverride": "true"}, "children": [w]}
    return w


def side_panel(path, title, children):
    """A panel on the right of the screen, where the catalog sits (only one of them shows at a time)."""
    panel = {"class": "/Script/UMG.Border", "name": "Panel",
             "props": {"BrushColor": PANEL, "Padding": "(Left=14,Top=12,Right=14,Bottom=12)"},
             "slot": {"LayoutData": "(Anchors=(Minimum=(X=1,Y=0),Maximum=(X=1,Y=1)),Offsets=(Left=-756,Top=88,Right=736,Bottom=88))"},
             "children": [{"class": "/Script/UMG.VerticalBox", "name": "Column", "children": [text("Title", title, 20, GOLD)] + children}]}
    return {"class": "/Script/UMG.CanvasPanel", "name": "Root", "children": [panel]}


def row(name, children, padding="(Left=0,Top=6,Right=0,Bottom=6)"):
    return {"class": "/Script/UMG.HorizontalBox", "name": name, "slot": {"Padding": padding}, "children": children}


def layouts():
    g = Graph()
    tree = side_panel(ROOT + "WBP_DenLayouts", "Layouts", [
        text("ScopeText", "", 13, variable=True, wrap=True, slot={"Padding": "(Left=0,Top=8,Right=0,Bottom=6)"}),
        row("ScopeRow", [button("ScopeButton", "Create campaign layout", 14)]),
        text("ScopeHint", "Start with a copy of your current Den. Returning to Home removes the campaign copy; a backup is kept.", 11, DIM, wrap=True),
        text("PresetsTitle", "Presets", 17, GOLD, slot={"Padding": "(Left=0,Top=16,Right=0,Bottom=4)"}),
        text("PresetsHint", "Keep a named version of your Den. Apply a preset to preview it, then Save to keep it. Undo brings back the previous layout.", 11, DIM, wrap=True),
        row("SaveRow", [box("PresetName", "New preset name", width=360), button("SavePreset", "Create preset", 14)]),
        {"class": "/Script/UMG.ListView", "name": "Presets", "variable": True,
         "props": {"bIsFocusable": "false", "SelectionMode": "Single", "EntryWidgetClass": ROOT + "WBP_DenCatalogShelf"},
         "slot": {"Size": "(SizeRule=Fill,Value=1.0)"}},
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
    tree = side_panel(ROOT + "WBP_DenStoreroom", "Storeroom", [
        text("StoredText", "", 13, variable=True, wrap=True, slot={"Padding": "(Left=0,Top=8,Right=0,Bottom=6)"}),
        box("StoredSearch", "Search stored props…"),
        {"class": "/Script/UMG.TileView", "name": "Stored", "variable": True,
         "props": {"bIsFocusable": "false", "SelectionMode": "Single", "EntryWidgetClass": ROOT + "WBP_DenCatalogEntry",
                   "EntryWidth": 160, "EntryHeight": 226},
         "slot": {"Size": "(SizeRule=Fill,Value=1.0)"}},
        row("StoredRow", [button("RestoreAll", "Restore everything", 14)]),
        text("DormantTitle", "Unavailable props", 17, GOLD, slot={"Padding": "(Left=0,Top=12,Right=0,Bottom=4)"}),
        text("DormantText", "", 11, DIM, variable=True, wrap=True),
        {"class": "/Script/UMG.SizeBox", "name": "DormantBox",
         "props": {"HeightOverride": 150, "bOverride_HeightOverride": "true"},
         "children": [{"class": "/Script/UMG.ListView", "name": "Dormant", "variable": True,
                       "props": {"bIsFocusable": "false", "SelectionMode": "Single",
                                 "EntryWidgetClass": ROOT + "WBP_DenCatalogShelf"}}]},
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


def transform():
    """Selection inspector; grouped fields keep their existing commit events."""
    g = Graph()
    groups = []
    for title, fields in (("Position · cm", FIELDS[:3]), ("Rotation · degrees", FIELDS[3:6]), ("Scale", FIELDS[6:])):
        cells = []
        for name, event in fields:
            cells.append({"class": "/Script/UMG.VerticalBox", "name": name + "Cell",
                          "slot": {"Padding": "(Left=0,Top=0,Right=6,Bottom=0)"},
                          "children": [text(name + "Label", name, 12, DIM), box("Field" + name, name, width=98, select_all=True)]})
            g.commit("Field" + name, event)
        groups += [text("Group" + fields[0][0], title, 14, GOLD,
                       slot={"Padding": "(Left=0,Top=16,Right=0,Bottom=6)"}), row("Fields" + fields[0][0], cells)]
    modes = [("Move", "Move", "mode_move"), ("Rotate", "Rotate", "mode_rotate"), ("ScaleMode", "Scale", "mode_scale")]
    edits = [("Copy", "Duplicate", "duplicate"), ("Store", "Store", "store"), ("Reset", "Reset", "reset")]
    for name, _, event in modes + edits: g.click(name, event)
    g.click("Focus", "focus")
    panel = {"class": "/Script/UMG.SizeBox", "name": "Panel", "variable": True,
             "props": {"WidthOverride": 360, "bOverride_WidthOverride": "true", "Visibility": "Collapsed"},
             "slot": {"LayoutData": "(Offsets=(Left=20,Top=88,Right=360,Bottom=0))", "bAutoSize": "true"},
             "children": [{"class": "/Script/UMG.Border", "name": "Frame",
                           "props": {"BrushColor": PANEL, "Padding": "(Left=20,Top=18,Right=20,Bottom=18)"},
                           "children": [{"class": "/Script/UMG.VerticalBox", "name": "Column", "children": [
                               text("Title", "Selected prop", 20, GOLD),
                               text("Selection", "", 15, WHITE, wrap=True, slot={"Padding": "(Left=0,Top=10,Right=0,Bottom=14)"}),
                               row("Modes", [button(n, label, 14) for n, label, _ in modes]),
                           ] + groups + [
                               text("ApplyHint", "Press Enter to apply a value.", 12, DIM),
                               row("Actions", [button(n, label, 13) for n, label, _ in edits], "(Left=0,Top=18,Right=0,Bottom=0)"),
                               button("Focus", "Focus camera", 13),
                           ]}]}]}
    return {"kind": "widget", "path": ROOT + "WBP_DenTransform",
            "tree": {"class": "/Script/UMG.CanvasPanel", "name": "Root", "children": [panel]},
            "functions": NATIVE_EVENT, "graph": g.spec()}

