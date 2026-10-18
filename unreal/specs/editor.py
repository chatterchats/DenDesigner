#!/usr/bin/env python3
"""Writes the editor spec set (unreal/specs/editor/*.json) for ZComAuthoring.

The editor's input actions, mapping context, camera rig and toolbar are repetitive, so they're generated from
the tables below. tools/build_plugin.sh runs this before authoring; the JSON output is committed for review.

Controls (confirmed in game with the Phase 0 probe rig, 2026-10-17): WASD flies in the yaw plane, Space up,
Left Ctrl down, Shift x3, RMB held turns the camera in place. Ctrl is a flight key, so no command uses a Ctrl
chord (Ctrl+Z would sink the camera while undoing).
"""
import json
import shutil
from pathlib import Path

ROOT = "/ZComDen/ZComDen/Editor/"
EI = "/Script/EnhancedInput."
OUT = Path(__file__).with_name("editor")


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

# Discrete commands: (action, Lua name, keys). Each sends Lua_Action(name, 1) when its key goes down.
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
    Flight and look run in Blueprint; everything else goes to Lua through the empty Lua_* functions."""
    nodes, links = [], []

    def node(id_, kind, **fields):
        nodes.append(dict({"id": id_, "kind": kind}, **fields))

    def link(a, b):
        links.append([a, b])

    def lua(id_, name, value="1"):
        node(id_, "call", function="self:Lua_Action", defaults={"Name": name, "Value": value})

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

    # Shift: fast flight (Lua also reads bFast to lift a dragged object vertically).
    node("fastkey", "input_action", action=ROOT + "IA_Den_Fast")
    node("fast_on", "set", var="bFast", defaults={"bFast": "true"})
    node("fast_off", "set", var="bFast", defaults={"bFast": "false"})
    link("fastkey.Started", "fast_on.execute")
    link("fastkey.Completed", "fast_off.execute")

    # Held buttons: 1 on press, 0 on release.
    for action, name in [("IA_Den_LookHold", "look_hold"), ("IA_Den_Select", "select")]:
        node(name, "input_action", action=ROOT + action)
        lua(name + "_on", name, "1")
        lua(name + "_off", name, "0")
        link(name + ".Started", name + "_on.execute")
        link(name + ".Completed", name + "_off.execute")

    # Wheel and Q/E: the step count (wheel notches, or +-1 per key repeat).
    for action, name in [("IA_Den_Rotate", "rotate"), ("IA_Den_RotateFine", "rotate_fine"), ("IA_Den_Scale", "scale")]:
        node(name, "input_action", action=ROOT + action)
        node(name + "_lua", "call", function="self:Lua_Action", defaults={"Name": name})
        link(name + ".Triggered", name + "_lua.execute")
        link(name + ".ActionValue", name + "_lua.Value")

    node("nudge", "input_action", action=ROOT + "IA_Den_Nudge")
    node("nudge_lua", "call", function="self:Lua_Vector", defaults={"Name": "nudge"})
    link("nudge.Triggered", "nudge_lua.execute")
    link("nudge.ActionValue", "nudge_lua.Value")

    for action, name, _ in COMMANDS:
        node(name, "input_action", action=ROOT + action)
        lua(name + "_lua", name)
        link(name + ".Started", name + "_lua.execute")

    # Per-frame Lua work (hover, drag) only while Lua asks for it.
    node("tick", "event", name="ReceiveTick")
    node("ticking", "get", var="bLuaTick")
    node("if", "branch")
    node("luatick", "call", function="self:Lua_Tick")
    link("tick.then", "if.execute")
    link("ticking.bLuaTick", "if.Condition")
    link("if.then", "luatick.execute")
    link("tick.DeltaSeconds", "luatick.DeltaSeconds")

    return {
        "kind": "blueprint", "path": ROOT + "BP_DenEditorRig", "parent": "/Script/Engine.CameraActor",
        "variables": [
            {"name": "bLuaTick", "type": "bool", "default": "false"},
            {"name": "bFast", "type": "bool", "default": "false"},
            {"name": "Speed", "type": "float", "default": "900.0"},
            {"name": "FastMultiplier", "type": "float", "default": "3.0"},
            {"name": "LookRate", "type": "float", "default": "2.5"},
        ],
        "functions": [
            {"name": "Lua_Action", "inputs": [{"name": "Name", "type": "string"}, {"name": "Value", "type": "float"}]},
            {"name": "Lua_Vector", "inputs": [{"name": "Name", "type": "string"}, {"name": "Value", "type": "vector"}]},
            {"name": "Lua_Tick", "inputs": [{"name": "DeltaSeconds", "type": "float"}]},
        ],
        "graph": {"nodes": nodes, "links": links},
    }


PANEL = "(R=0.015,G=0.02,B=0.03,A=0.86)"
BUTTON = "(R=0.16,G=0.2,B=0.27,A=1)"
WHITE = "(SpecifiedColor=(R=0.92,G=0.94,B=0.97,A=1),ColorUseRule=UseColor_Specified)"
DIM = "(SpecifiedColor=(R=0.62,G=0.67,B=0.74,A=1),ColorUseRule=UseColor_Specified)"
INK = "(SpecifiedColor=(R=0.02,G=0.025,B=0.035,A=1),ColorUseRule=UseColor_Specified)"
GOLD = "(SpecifiedColor=(R=1,G=0.78,B=0.35,A=1),ColorUseRule=UseColor_Specified)"

HINTS = ("WASD fly, Space/Ctrl up/down, Shift fast, hold RMB to look\n"
         "LMB select and drag (Shift: up/down), wheel or Q/E rotate (Shift: fine), +/- scale\n"
         "Arrows/PgUp/PgDn nudge, G snap, X store, C copy, R reset, Z/Y undo/redo, F focus, Esc back\n"
         "Tab catalog: click an item, then click in the Den to place it (Shift+click places more)\n"
         "H storeroom (stored props), L layouts (this campaign's own layout, presets)")

# Toolbar buttons: (widget name, label, Lua event)
TOOLBAR = [("Catalog", "Catalog", "catalog"), ("Storeroom", "Storeroom", "storeroom"), ("Layouts", "Layouts", "layouts"),
           ("Undo", "Undo", "undo"), ("Redo", "Redo", "redo"), ("Store", "Store", "store"), ("Copy", "Copy", "duplicate"),
           ("Reset", "Reset", "reset"), ("Snap", "Snap: off", "snap"), ("Reach", "Reach: 20 m", "reach"), ("Lock", "Structure: locked", "lock"),
           ("Save", "Save", "save"), ("Exit", "Exit", "exit")]
CONFIRM = [("ConfirmSave", "Save", "confirm_save"), ("ConfirmDiscard", "Discard", "confirm_discard"),
           ("ConfirmCancel", "Keep editing", "confirm_cancel")]


def text(name, value, size, color=WHITE, variable=False, slot=None, wrap=False):
    w = {"class": "/Script/UMG.TextBlock", "name": name, "props": {"Text": value, "Font.Size": size, "ColorAndOpacity": color}}
    if wrap:
        w["props"]["AutoWrapText"] = "true"
    if variable:
        w["variable"] = True
    if slot:
        w["slot"] = slot
    return w


def button(name, label, size=13):
    return {"class": "/Script/UMG.Button", "name": name, "variable": True,
            # Not focusable: a focused button would take Space (fly up) as a click.
            "props": {"BackgroundColor": BUTTON, "IsFocusable": "false"},
            "slot": {"Padding": "(Left=0,Top=0,Right=6,Bottom=6)"},
            "children": [text(name + "Label", label, size, variable=True)]}


def toolbar():
    rows = [TOOLBAR[:3], TOOLBAR[3:8], TOOLBAR[8:]]  # panels / edits / settings and file
    panel = {"class": "/Script/UMG.SizeBox", "name": "Frame", "props": {"WidthOverride": 660, "bOverride_WidthOverride": "true"},
             "slot": {"LayoutData": "(Offsets=(Left=24,Top=24,Right=660,Bottom=200))", "bAutoSize": "true"},
             "children": [{"class": "/Script/UMG.Border", "name": "Panel",
                           "props": {"BrushColor": PANEL, "Padding": "(Left=16,Top=12,Right=16,Bottom=12)"},
                           "children": [{"class": "/Script/UMG.VerticalBox", "name": "Column", "children": [
                               text("Title", "Den Designer", 20, GOLD),
                               text("Scope", "", 12, DIM, variable=True),
                               text("Selection", "Nothing selected", 15, variable=True, wrap=True,
                                    slot={"Padding": "(Left=0,Top=8,Right=0,Bottom=0)"}),
                               text("Status", "", 12, DIM, variable=True, wrap=True,
                                    slot={"Padding": "(Left=0,Top=2,Right=0,Bottom=10)"}),
                           ] + [{"class": "/Script/UMG.WrapBox", "name": "Row%d" % i,
                                 "children": [button(n, label) for n, label, _ in row]} for i, row in enumerate(rows)] + [
                               text("Hints", HINTS, 11, DIM, slot={"Padding": "(Left=0,Top=6,Right=0,Bottom=0)"}),
                           ]}]}]}
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
    for name, _, event in TOOLBAR + CONFIRM:
        nodes.append({"id": name, "kind": "bound_event", "widget": name, "delegate": "OnClicked"})
        nodes.append({"id": name + "_lua", "kind": "call", "function": "self:Lua_Event", "defaults": {"Name": event}})
        links.append([name + ".then", name + "_lua.execute"])
    return {
        "kind": "widget", "path": ROOT + "WBP_DenToolbar",
        "tree": {"class": "/Script/UMG.CanvasPanel", "name": "Root", "children": [panel, confirm]},
        "functions": [{"name": "Lua_Event", "inputs": [{"name": "Name", "type": "string"}, {"name": "Arg", "type": "string"}]}],
        "graph": {"nodes": nodes, "links": links},
    }


ITEM = ROOT + "BP_DenCatalogItem"


def catalog_item():
    """One row of a catalog list. Lua writes only FString fields (never FText properties)."""
    return {"kind": "blueprint", "path": ITEM, "parent": "/Script/CoreUObject.Object",
            "variables": [{"name": n, "type": "string", "default": ""} for n in ("Key", "Title", "Detail")]
            # The thumbnail (a texture Lua imported from Saved\ZComDen\thumbs), or none yet.
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
    return {"kind": "widget", "path": ROOT + name, "interfaces": ["/Script/UMG.UserObjectListEntry"],
            "tree": tree, "graph": {"nodes": nodes, "links": links}}


def catalog_entry():
    picture = {"class": "/Script/UMG.SizeBox", "name": "PictureBox",
               "props": {"WidthOverride": 112, "bOverride_WidthOverride": "true", "HeightOverride": 112, "bOverride_HeightOverride": "true"},
               "slot": {"HorizontalAlignment": "HAlign_Center", "Padding": "(Left=0,Top=0,Right=0,Bottom=4)"},
               "children": [{"class": "/Script/UMG.Image", "name": "Picture", "variable": True, "props": {"Visibility": "Hidden"}}]}
    tree = {"class": "/Script/UMG.Border", "name": "Frame",
            "props": {"BrushColor": "(R=0.07,G=0.09,B=0.13,A=0.95)", "Padding": "(Left=6,Top=6,Right=6,Bottom=6)"},
            "children": [{"class": "/Script/UMG.VerticalBox", "name": "Lines", "children": [
                picture,
                text("Name", "", 11, variable=True, wrap=True),
                text("Size", "", 10, DIM, variable=True, wrap=True)]}]}
    return list_entry("WBP_DenCatalogEntry", tree, [("Title", "Name"), ("Detail", "Size")], picture="Picture")


def catalog_shelf():
    tree = {"class": "/Script/UMG.Border", "name": "Frame",
            "props": {"BrushColor": "(R=0,G=0,B=0,A=0)", "Padding": "(Left=6,Top=3,Right=6,Bottom=3)"},
            "children": [text("Label", "", 12, variable=True)]}
    return list_entry("WBP_DenCatalogShelf", tree, [("Title", "Label")])


def catalog():
    """The catalog panel: search, shelves (folders) on the left, meshes on the right."""
    lists = {"bIsFocusable": "false", "SelectionMode": "Single"}
    shelves = {"class": "/Script/UMG.SizeBox", "name": "ShelfBox", "props": {"WidthOverride": 230, "bOverride_WidthOverride": "true"},
               "slot": {"Padding": "(Left=0,Top=0,Right=8,Bottom=0)"},
               "children": [{"class": "/Script/UMG.ListView", "name": "Shelves", "variable": True,
                             "props": dict(lists, EntryWidgetClass=ROOT + "WBP_DenCatalogShelf")}]}
    items = {"class": "/Script/UMG.TileView", "name": "Items", "variable": True,
             "props": dict(lists, EntryWidgetClass=ROOT + "WBP_DenCatalogEntry", EntryWidth=128, EntryHeight=184),
             "slot": {"Size": "(SizeRule=Fill,Value=1.0)"}}
    panel = {"class": "/Script/UMG.Border", "name": "Panel",
             "props": {"BrushColor": PANEL, "Padding": "(Left=14,Top=12,Right=14,Bottom=12)"},
             # Pinned to the right edge, stretched top to bottom: Left is the x position (from the right edge) and
             # Right is the width; Top and Bottom are margins.
             "slot": {"LayoutData": "(Anchors=(Minimum=(X=1,Y=0),Maximum=(X=1,Y=1)),Offsets=(Left=-814,Top=24,Right=790,Bottom=24))"},
             "children": [{"class": "/Script/UMG.VerticalBox", "name": "Column", "children": [
                 text("Title", "Catalog", 20, GOLD),
                 {"class": "/Script/UMG.EditableTextBox", "name": "Search", "variable": True,
                  # The default box is light grey: dark text reads on it (the default text was too pale).
                  "props": {"HintText": "Search every mesh (type, then pick from the list)",
                            "WidgetStyle.ForegroundColor": INK, "WidgetStyle.FocusedForegroundColor": INK,
                            "WidgetStyle.TextStyle.ColorAndOpacity": INK},
                  "slot": {"Padding": "(Left=0,Top=8,Right=0,Bottom=8)"}},
                 {"class": "/Script/UMG.HorizontalBox", "name": "Lists", "slot": {"Size": "(SizeRule=Fill,Value=1.0)"},
                  "children": [shelves, items]},
                 text("Footer", "", 11, DIM, variable=True, wrap=True, slot={"Padding": "(Left=0,Top=8,Right=0,Bottom=0)"}),
             ]}]}
    nodes = [{"id": "search", "kind": "bound_event", "widget": "Search", "delegate": "OnTextChanged"},
             {"id": "search_lua", "kind": "call", "function": "self:Lua_Event", "defaults": {"Name": "search"}}]
    links = [["search.then", "search_lua.execute"], ["search.Text", "search_lua.Arg"]]
    for widget, event in (("Shelves", "shelf"), ("Items", "item")):
        w = widget.lower()
        nodes += [{"id": w, "kind": "bound_event", "widget": widget, "delegate": "BP_OnItemClicked"},
                  {"id": w + "_cast", "kind": "cast", "class": ITEM},
                  {"id": w + "_key", "kind": "get", "var": f"{ITEM}:Key"},
                  {"id": w + "_lua", "kind": "call", "function": "self:Lua_Event", "defaults": {"Name": event}}]
        links += [[w + ".then", w + "_cast.execute"], [w + ".Item", w + "_cast.Object"],
                  [w + "_cast.then", w + "_lua.execute"], [w + "_cast.AsBP Den Catalog Item", w + "_key.self"],
                  [w + "_key.Key", w + "_lua.Arg"]]
    return {"kind": "widget", "path": ROOT + "WBP_DenCatalog",
            "tree": {"class": "/Script/UMG.CanvasPanel", "name": "Root", "children": [panel]},
            "functions": [{"name": "Lua_Event", "inputs": [{"name": "Name", "type": "string"}, {"name": "Arg", "type": "string"}]}],
            "graph": {"nodes": nodes, "links": links}}


LUA_EVENT = [{"name": "Lua_Event", "inputs": [{"name": "Name", "type": "string"}, {"name": "Arg", "type": "string"}]}]


class Graph:
    """Bound events that call Lua_Event(name, arg)."""

    def __init__(self):
        self.nodes, self.links = [], []

    def click(self, widget, event):
        """A button: Lua_Event(event, "")."""
        self.nodes += [{"id": widget, "kind": "bound_event", "widget": widget, "delegate": "OnClicked"},
                       {"id": widget + "_lua", "kind": "call", "function": "self:Lua_Event", "defaults": {"Name": event}}]
        self.links.append([widget + ".then", widget + "_lua.execute"])

    def click_with_text(self, widget, event, box):
        """A button that sends the text of an EditableTextBox along."""
        self.click(widget, event)
        self.nodes += [{"id": widget + "_box", "kind": "get", "var": box},
                       {"id": widget + "_text", "kind": "call", "function": "/Script/UMG.EditableTextBox:GetText"}]
        self.links += [[widget + "_box." + box, widget + "_text.self"], [widget + "_text.ReturnValue", widget + "_lua.Arg"]]

    def commit(self, box, event):
        """An EditableTextBox: Lua_Event(event, text) when Enter is pressed or it loses focus."""
        self.nodes += [{"id": box, "kind": "bound_event", "widget": box, "delegate": "OnTextCommitted"},
                       {"id": box + "_lua", "kind": "call", "function": "self:Lua_Event", "defaults": {"Name": event}}]
        self.links += [[box + ".then", box + "_lua.execute"], [box + ".Text", box + "_lua.Arg"]]

    def item(self, view, event):
        """A ListView/TileView: Lua_Event(event, item.Key) for a clicked item."""
        w = view.lower()
        self.nodes += [{"id": w, "kind": "bound_event", "widget": view, "delegate": "BP_OnItemClicked"},
                       {"id": w + "_cast", "kind": "cast", "class": ITEM},
                       {"id": w + "_key", "kind": "get", "var": f"{ITEM}:Key"},
                       {"id": w + "_lua", "kind": "call", "function": "self:Lua_Event", "defaults": {"Name": event}}]
        self.links += [[w + ".then", w + "_cast.execute"], [w + ".Item", w + "_cast.Object"],
                       [w + "_cast.then", w + "_lua.execute"], [w + "_cast.AsBP Den Catalog Item", w + "_key.self"],
                       [w + "_key.Key", w + "_lua.Arg"]]

    def spec(self):
        return {"nodes": self.nodes, "links": self.links}


def box(name, hint, width=None, select_all=False):
    w = {"class": "/Script/UMG.EditableTextBox", "name": name, "variable": True,
         "props": {"HintText": hint, "WidgetStyle.ForegroundColor": INK, "WidgetStyle.FocusedForegroundColor": INK,
                   "WidgetStyle.TextStyle.ColorAndOpacity": INK}}
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
             "slot": {"LayoutData": "(Anchors=(Minimum=(X=1,Y=0),Maximum=(X=1,Y=1)),Offsets=(Left=-814,Top=24,Right=790,Bottom=24))"},
             "children": [{"class": "/Script/UMG.VerticalBox", "name": "Column", "children": [text("Title", title, 20, GOLD)] + children}]}
    return {"class": "/Script/UMG.CanvasPanel", "name": "Root", "children": [panel]}


def row(name, children, padding="(Left=0,Top=6,Right=0,Bottom=6)"):
    return {"class": "/Script/UMG.HorizontalBox", "name": name, "slot": {"Padding": padding}, "children": children}


def layouts():
    g = Graph()
    tree = side_panel(ROOT + "WBP_DenLayouts", "Layouts", [
        text("ScopeText", "", 13, variable=True, wrap=True, slot={"Padding": "(Left=0,Top=8,Right=0,Bottom=6)"}),
        row("ScopeRow", [button("ScopeButton", "Give this campaign its own layout", 14)]),
        text("ScopeHint", "Its own layout starts as a copy of what you see now. Going back to the home layout deletes the "
             "campaign's copy (a backup is kept in Saved\\ZComDen\\backups).", 11, DIM, wrap=True),
        text("PresetsTitle", "Presets", 17, GOLD, slot={"Padding": "(Left=0,Top=16,Right=0,Bottom=4)"}),
        text("PresetsHint", "Named snapshots of a whole layout, in Saved\\ZComDen\\presets. Loading one replaces what you see "
             "(Z undoes it); Save keeps it.", 11, DIM, wrap=True),
        row("SaveRow", [box("PresetName", "New preset name", width=360), button("SavePreset", "Save current as preset", 14)]),
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
    return {"kind": "widget", "path": ROOT + "WBP_DenLayouts", "tree": tree, "functions": LUA_EVENT, "graph": g.spec()}


def storeroom():
    g = Graph()
    tree = side_panel(ROOT + "WBP_DenStoreroom", "Storeroom", [
        text("StoredText", "", 13, variable=True, wrap=True, slot={"Padding": "(Left=0,Top=8,Right=0,Bottom=6)"}),
        {"class": "/Script/UMG.TileView", "name": "Stored", "variable": True,
         "props": {"bIsFocusable": "false", "SelectionMode": "Single", "EntryWidgetClass": ROOT + "WBP_DenCatalogEntry",
                   "EntryWidth": 128, "EntryHeight": 184},
         "slot": {"Size": "(SizeRule=Fill,Value=1.0)"}},
        row("StoredRow", [button("RestoreAll", "Restore everything", 14)]),
        text("DormantTitle", "Waiting for their objects", 17, GOLD, slot={"Padding": "(Left=0,Top=12,Right=0,Bottom=4)"}),
        text("DormantText", "", 11, DIM, variable=True, wrap=True),
        {"class": "/Script/UMG.SizeBox", "name": "DormantBox",
         "props": {"HeightOverride": 150, "bOverride_HeightOverride": "true"},
         "children": [{"class": "/Script/UMG.ListView", "name": "Dormant", "variable": True,
                       "props": {"bIsFocusable": "false", "SelectionMode": "Single",
                                 "EntryWidgetClass": ROOT + "WBP_DenCatalogShelf"}}]},
        text("Footer", "", 12, DIM, variable=True, wrap=True),
    ])
    g.item("Stored", "restore")
    g.click("RestoreAll", "restore_all")
    g.item("Dormant", "forget")
    return {"kind": "widget", "path": ROOT + "WBP_DenStoreroom", "tree": tree, "functions": LUA_EVENT, "graph": g.spec()}


FIELDS = [("X", "set_x"), ("Y", "set_y"), ("Z", "set_z"), ("Pitch", "set_pitch"), ("Yaw", "set_yaw"), ("Roll", "set_roll"),
          ("Scale", "set_scale")]


def transform():
    """Exact numbers for the selection, under the toolbar (FFXIV's advanced placement)."""
    g = Graph()
    cells = []
    for name, event in FIELDS:
        cells.append({"class": "/Script/UMG.VerticalBox", "name": name + "Cell", "slot": {"Padding": "(Left=0,Top=0,Right=6,Bottom=0)"},
                      "children": [text(name + "Label", name, 11, DIM), box("Field" + name, name, width=96, select_all=True)]})
        g.commit("Field" + name, event)
    panel = {"class": "/Script/UMG.Border", "name": "Panel", "variable": True,
             "props": {"BrushColor": PANEL, "Padding": "(Left=16,Top=10,Right=16,Bottom=12)", "Visibility": "Collapsed"},
             "slot": {"LayoutData": "(Anchors=(Minimum=(X=0,Y=1),Maximum=(X=0,Y=1)),Alignment=(X=0,Y=1),"
                                    "Offsets=(Left=24,Top=-24,Right=660,Bottom=0))", "bAutoSize": "true"},
             "children": [{"class": "/Script/UMG.VerticalBox", "name": "Column", "children": [
                 text("Title", "Exact placement (cm, degrees; Enter applies)", 12, DIM),
                 row("Fields", cells, padding="(Left=0,Top=4,Right=0,Bottom=0)")]}]}
    return {"kind": "widget", "path": ROOT + "WBP_DenTransform",
            "tree": {"class": "/Script/UMG.CanvasPanel", "name": "Root", "children": [panel]},
            "functions": LUA_EVENT, "graph": g.spec()}


def main():
    specs = input_actions() + [mapping_context(), rig(), toolbar(), catalog_item(), catalog_entry(), catalog_shelf(), catalog(),
                               layouts(), storeroom(), transform()]
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for i, spec in enumerate(specs, 1):
        name = spec["path"].rsplit("/", 1)[1]
        (OUT / ("%02d_%s.json" % (i, name))).write_text(json.dumps(spec, indent=1) + "\n")
    print("wrote %d specs to %s" % (len(specs), OUT))


if __name__ == "__main__":
    main()
