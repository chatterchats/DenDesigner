#!/usr/bin/env python3
"""Run generated Blueprint functions offline, for logic tests.

Supports the node kinds and engine functions used by string, array and JSON
logic (parsers, builders, page arithmetic). Widgets and world objects are
stand-ins: a test provides them as Python objects. This checks what a graph
computes, not how Unreal compiles it; tools/build/lint_specs.py and the kit
build cover the rest.

    sim = Simulator.load()                       # unreal/generated/runtime
    obj = sim.instance('/DenDesignerGF/Runtime/BP_DenCatalog', PackMounts=[...])
    out = sim.run(obj, 'DeclarePacks', Paths=[...])   # -> {'JSON': '...'}
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / 'unreal/generated/runtime'
STR = '/Script/Engine.KismetStringLibrary:'
KML = '/Script/Engine.KismetMathLibrary:'
ARRAY = '/Script/Engine.KismetArrayLibrary:Array_'


class SimulationError(Exception):
    pass


def boolean(value):
    if isinstance(value, str):
        return value.lower() == 'true'
    return bool(value)


def number(value):
    if isinstance(value, str):
        value = value.strip()
        try:
            return int(value)
        except ValueError:
            return float(value) if value else 0
    return value


def ue_float(value):
    """FString::SanitizeFloat, as used by Conv_DoubleToString."""
    text = '%f' % value
    text = text.rstrip('0')
    return text + '0' if text.endswith('.') else text


def vector(value):
    if isinstance(value, str):
        return tuple(float(x) for x in value.split(','))
    return tuple(value)


def split(source, sep, case, direction):
    hay, needle = (source, sep) if case == 'CaseSensitive' else (source.lower(), sep.lower())
    at = hay.find(needle) if direction != 'FromEnd' else hay.rfind(needle)
    if at < 0 or not sep:
        return {'ReturnValue': False, 'LeftS': '', 'RightS': ''}
    return {'ReturnValue': True, 'LeftS': source[:at], 'RightS': source[at + len(sep):]}


def replace(source, old, new, case):
    if not old:
        return source
    if case == 'CaseSensitive':
        return source.replace(old, new)
    out, i, low, lold = [], 0, source.lower(), old.lower()
    while True:
        j = low.find(lold, i)
        if j < 0:
            out.append(source[i:])
            return ''.join(out)
        out.append(source[i:j] + new)
        i = j + len(old)


def parse_into_array(source, delimiter, cull):
    parts = source.split(delimiter) if delimiter else [source]
    return [p for p in parts if p or not boolean(cull)]


ENGINE = {
    STR + 'Concat_StrStr': lambda A='', B='': {'ReturnValue': str(A) + str(B)},
    STR + 'Len': lambda S='': {'ReturnValue': len(S)},
    STR + 'EqualEqual_StrStr': lambda A='', B='': {'ReturnValue': A == B},
    STR + 'NotEqual_StrStr': lambda A='', B='': {'ReturnValue': A != B},
    STR + 'EqualEqual_StriStri': lambda A='', B='': {'ReturnValue': A.lower() == B.lower()},
    STR + 'NotEqual_StriStri': lambda A='', B='': {'ReturnValue': A.lower() != B.lower()},
    STR + 'StartsWith': lambda SourceString='', InPrefix='', SearchCase='IgnoreCase': {'ReturnValue': SourceString.startswith(InPrefix) if SearchCase == 'CaseSensitive' else SourceString.lower().startswith(InPrefix.lower())},
    STR + 'EndsWith': lambda SourceString='', InSuffix='', SearchCase='IgnoreCase': {'ReturnValue': SourceString.endswith(InSuffix) if SearchCase == 'CaseSensitive' else SourceString.lower().endswith(InSuffix.lower())},
    STR + 'Contains': lambda SearchIn='', Substring='', bUseCase='false', bSearchFromEnd='false': {'ReturnValue': (Substring in SearchIn) if boolean(bUseCase) else (Substring.lower() in SearchIn.lower())},
    STR + 'Replace': lambda SourceString='', From='', To='', SearchCase='IgnoreCase': {'ReturnValue': replace(SourceString, From, To, SearchCase)},
    STR + 'Split': lambda SourceString='', InStr='', SearchCase='IgnoreCase', SearchDir='FromStart': split(SourceString, InStr, SearchCase, SearchDir),
    STR + 'RightChop': lambda SourceString='', Count=0: {'ReturnValue': SourceString[max(0, number(Count)):]},
    STR + 'Left': lambda SourceString='', Count=0: {'ReturnValue': SourceString[:max(0, number(Count))]},
    STR + 'GetSubstring': lambda SourceString='', StartIndex=0, Length=1: {'ReturnValue': SourceString[max(0, number(StartIndex)):max(0, number(StartIndex)) + max(0, number(Length))]},
    STR + 'Conv_IntToString': lambda InInt=0: {'ReturnValue': str(int(number(InInt)))},
    STR + 'Conv_StringToInt': lambda InString='': {'ReturnValue': _to_int(InString)},
    STR + 'Conv_DoubleToString': lambda InDouble=0.0: {'ReturnValue': ue_float(float(number(InDouble)))},
    STR + 'Conv_StringToDouble': lambda InString='': {'ReturnValue': _to_float(InString)},
    STR + 'ParseIntoArray': lambda SourceString='', Delimiter=' ', CullEmptyStrings='true': {'ReturnValue': parse_into_array(SourceString, Delimiter, CullEmptyStrings)},
    STR + 'TrimTrailing': lambda SourceString='': {'ReturnValue': SourceString.rstrip(' \t\r\n')},
    STR + 'Trim': lambda SourceString='': {'ReturnValue': SourceString.lstrip(' \t\r\n')},
    STR + 'ToUpper': lambda SourceString='': {'ReturnValue': SourceString.upper()},
    STR + 'ToLower': lambda SourceString='': {'ReturnValue': SourceString.lower()},
    STR + 'IsNumeric': lambda SourceString='': {'ReturnValue': _numeric(SourceString)},
    STR + 'GetCharacterAsNumber': lambda SourceString='', Index=0: {'ReturnValue': ord(SourceString[number(Index)]) if 0 <= number(Index) < len(SourceString) else 0},
    '/Script/Engine.KismetTextLibrary:Conv_TextToString': lambda InText='': {'ReturnValue': str(InText)},
    '/Script/Engine.KismetTextLibrary:Conv_StringToText': lambda InString='': {'ReturnValue': str(InString)},
    '/Script/Engine.KismetSystemLibrary:IsValid': lambda Object=None: {'ReturnValue': Object is not None},
    KML + 'SelectString': lambda A='', B='', bPickA=False: {'ReturnValue': A if boolean(bPickA) else B},
    KML + 'SelectInt': lambda A=0, B=0, bPickA=False: {'ReturnValue': number(A) if boolean(bPickA) else number(B)},
    KML + 'SelectColor': lambda A=None, B=None, bPickA=False: {'ReturnValue': A if boolean(bPickA) else B},
    KML + 'SelectFloat': lambda A=0, B=0, bPickA=False: {'ReturnValue': number(A) if boolean(bPickA) else number(B)},
    KML + 'BooleanAND': lambda A=False, B=False: {'ReturnValue': boolean(A) and boolean(B)},
    KML + 'BooleanOR': lambda A=False, B=False: {'ReturnValue': boolean(A) or boolean(B)},
    KML + 'Not_PreBool': lambda A=False: {'ReturnValue': not boolean(A)},
    KML + 'Multiply_VectorFloat': lambda A=(0, 0, 0), B=0: {'ReturnValue': tuple(x * float(number(B)) for x in vector(A))},
    KML + 'MakeVector': lambda X=0, Y=0, Z=0: {'ReturnValue': (float(number(X)), float(number(Y)), float(number(Z)))},
    KML + 'BreakVector': lambda InVec=(0, 0, 0): dict(zip('XYZ', vector(InVec))),
    KML + 'FCeil': lambda A=0: {'ReturnValue': int(math.ceil(float(number(A))))},
    KML + 'FTrunc': lambda A=0: {'ReturnValue': int(float(number(A)))},
    KML + 'FFloor': lambda A=0: {'ReturnValue': int(math.floor(float(number(A))))},
    KML + 'Round': lambda A=0: {'ReturnValue': int(math.floor(float(number(A)) + 0.5))},
    KML + 'FMax': lambda A=0, B=0: {'ReturnValue': max(float(number(A)), float(number(B)))},
    KML + 'FMin': lambda A=0, B=0: {'ReturnValue': min(float(number(A)), float(number(B)))},
    KML + 'Max': lambda A=0, B=0: {'ReturnValue': max(number(A), number(B))},
    KML + 'Min': lambda A=0, B=0: {'ReturnValue': min(number(A), number(B))},
    KML + 'Clamp': lambda Value=0, Min=0, Max=0: {'ReturnValue': max(number(Min), min(number(Max), number(Value)))},
}
for _name, _fn in [('Add', lambda a, b: a + b), ('Subtract', lambda a, b: a - b), ('Multiply', lambda a, b: a * b),
                   ('Divide', lambda a, b: int(a / b) if isinstance(a, int) and isinstance(b, int) else a / b),
                   ('Percent', lambda a, b: int(math.fmod(a, b))),
                   ('Less', lambda a, b: a < b), ('LessEqual', lambda a, b: a <= b), ('Greater', lambda a, b: a > b),
                   ('GreaterEqual', lambda a, b: a >= b), ('EqualEqual', lambda a, b: a == b), ('NotEqual', lambda a, b: a != b)]:
    for _suffix, _conv in [('_IntInt', int), ('_Int64Int64', int), ('_DoubleDouble', float)]:
        ENGINE[KML + _name + _suffix] = (lambda f, c: lambda A=0, B=0: {'ReturnValue': f(c(number(A)), c(number(B)))})(_fn, _conv)


def _to_int(text):
    text = str(text).strip()
    sign, digits = 1, ''
    if text[:1] in '+-':
        sign, text = (-1 if text[0] == '-' else 1), text[1:]
    for c in text:
        if not c.isdigit():
            break
        digits += c
    return sign * int(digits) if digits else 0


def _to_float(text):
    try:
        return float(text)
    except ValueError:
        return 0.0


def _numeric(text):
    try:
        float(text)
        return bool(text) and text.strip() == text
    except ValueError:
        return False


class Instance:
    def __init__(self, path, variables):
        self.path = path
        self.vars = variables

    def __repr__(self):
        return f'<{self.path.rsplit("/", 1)[-1]}>'


class Frame:
    def __init__(self, sim, obj, graph, inputs):
        self.sim, self.obj, self.graph = sim, obj, graph
        self.nodes = {n['id']: n for n in graph['nodes']}
        self.locals = {v['name']: self.sim.default(v) for v in graph.get('locals', [])}
        self.inputs = dict(inputs)
        self.outputs = {v['name']: self.sim.default(v) for v in graph.get('outputs', [])}
        self.into = {}
        self.exec_to = {}
        for a, b in graph['links']:
            node, _, pin = b.partition('.')
            if pin == 'execute':
                self.exec_to[a] = node
            else:
                self.into[b] = a
        self.cache = {}
        self.impure = {a.partition('.')[0] for a, b in graph['links'] if b.endswith('.execute') or a.endswith('.then')} | \
                      {b.partition('.')[0] for a, b in graph['links'] if b.endswith('.execute')}

    # ---- data
    def pin(self, node_id, pin, default=None):
        source = self.into.get(node_id + '.' + pin)
        if source is None:
            node = self.nodes.get(node_id, {})
            if pin in node.get('defaults', {}):
                return node['defaults'][pin]
            return default
        return self.value(source)

    def value(self, ref):
        node_id, _, pin = ref.partition('.')
        if node_id == 'entry':
            return self.inputs.get(pin)
        node = self.nodes[node_id]
        if node_id in self.impure:
            if node_id not in self.cache:
                raise SimulationError(f'{ref} read before its node ran')
            return self.cache[node_id].get(pin)
        return self.evaluate(node).get(pin)

    def variable(self, var):
        if var.startswith('local:'):
            return self.locals, var[6:]
        if var in self.inputs and var not in self.obj.vars:
            return self.inputs, var
        return self.obj.vars, var

    def evaluate(self, node):
        kind = node['kind']
        if kind == 'get':
            var = node['var']
            if ':' in var and not var.startswith('local:'):
                owner = self.pin(node['id'], 'self')
                if owner is None:
                    raise SimulationError(f'{node["id"]}: get {var} on None')
                member = var.rpartition(':')[2]
                value = owner.vars.get(member) if isinstance(owner, Instance) else getattr(owner, member)
                return {member: value}
            store, name = self.variable(var)
            if name not in store:
                raise SimulationError(f'{node["id"]}: unknown variable {var}')
            return {name: store[name]}
        if kind == 'self':
            return {'self': self.obj}
        if kind == 'break_struct':
            value = self.pin(node['id'], next(iter(self._pins_in(node['id']))) if self._pins_in(node['id']) else '')
            return dict(value or {})
        if kind == 'make_struct':
            return {node['struct'].rsplit('/', 1)[-1].rsplit('.', 1)[-1]: {p: self.pin(node['id'], p) for p in self._pins_in(node['id'])}}
        if kind in ('call', 'array_call'):
            return self.call(node)
        raise SimulationError(f'cannot evaluate {kind} {node["id"]}')

    def _pins_in(self, node_id):
        return [k.partition('.')[2] for k in self.into if k.partition('.')[0] == node_id]

    def call(self, node):
        fn = node['function']
        names = set(node.get('defaults', {})) | set(self._pins_in(node['id']))
        args = {p: self.pin(node['id'], p) for p in names}
        if node['kind'] == 'array_call':
            return self.array(fn, args)
        if fn.startswith('self:'):
            return self.sim.run(self.obj, fn[5:], **args)
        target, _, member = fn.rpartition(':')
        if target in self.sim.functions_by_path and member in self.sim.functions_by_path[target]:
            owner = args.pop('self', None)
            return self.sim.run(owner, member, **args)
        if fn in self.sim.engine:
            args.pop('self', None) if fn in ENGINE else None
            return self.sim.engine[fn](**args)
        raise SimulationError(f'no simulation for {fn}')

    def array(self, fn, args):
        op = fn[len(ARRAY):]
        target = args.get('TargetArray')
        if target is None:
            raise SimulationError(f'{fn} on missing array')
        if op == 'Length':
            return {'ReturnValue': len(target)}
        if op == 'Get':
            i = number(args.get('Index', 0))
            if not 0 <= i < len(target):
                raise SimulationError(f'Array_Get index {i} out of range {len(target)}')
            return {'Item': target[i]}
        if op == 'Set':
            i = number(args.get('Index', 0))
            if 0 <= i < len(target):
                target[i] = args.get('Item')
            return {}
        if op == 'Add':
            target.append(args.get('NewItem'))
            return {'ReturnValue': len(target) - 1}
        if op == 'AddUnique':
            if args.get('NewItem') in target:
                return {'ReturnValue': -1}
            target.append(args.get('NewItem'))
            return {'ReturnValue': len(target) - 1}
        if op == 'Find':
            item = args.get('ItemToFind')
            return {'ReturnValue': target.index(item) if item in target else -1}
        if op == 'Contains':
            return {'ReturnValue': args.get('ItemToFind') in target}
        if op == 'Clear':
            target.clear()
            return {}
        if op == 'Remove':
            i = number(args.get('IndexToRemove', 0))
            if 0 <= i < len(target):
                target.pop(i)
            return {}
        if op == 'Insert':
            target.insert(number(args.get('Index', 0)), args.get('NewItem'))
            return {'ReturnValue': number(args.get('Index', 0))}
        if op == 'Resize':
            n = number(args.get('Size', 0))
            del target[n:]
            target.extend([None] * (n - len(target)))
            return {}
        raise SimulationError(f'no simulation for {fn}')

    # ---- exec
    def run(self, limit=200000):
        current = self.exec_to.get('entry.then')
        steps = 0
        while current:
            steps += 1
            if steps > limit:
                raise SimulationError('step limit (infinite loop?)')
            if current == 'result':
                for name in self.outputs:
                    source = self.into.get('result.' + name)
                    if source is not None:
                        self.outputs[name] = self.value(source)
                return self.outputs
            node = self.nodes[current]
            kind = node['kind']
            out = 'then'
            if kind == 'branch':
                out = 'then' if boolean(self.pin(current, 'Condition', False)) else 'else'
            elif kind == 'sequence':
                for i in range(node.get('outputs', 1)):
                    target = self.exec_to.get(f'{current}.then_{i}')
                    if target:
                        self.sub(target)
                return self.finish()
            elif kind == 'set':
                store, name = self.variable(node['var']) if not (':' in node['var'] and not node['var'].startswith('local:')) else (None, None)
                member = node['var'].rpartition(':')[2]
                value = self.pin(current, member, None)
                if store is None:
                    owner = self.pin(current, 'self')
                    if isinstance(owner, Instance):
                        owner.vars[member] = value
                    else:
                        setattr(owner, member, value)
                else:
                    store[name] = self.sim.coerce(store.get(name), value)
            elif kind == 'cast':
                obj = self.pin(current, 'Object')
                wanted = node['class']
                ok = isinstance(obj, Instance) and self.sim.is_a(obj.path, wanted)
                label = 'As' + self.sim.display(wanted)
                self.cache[current] = {label: obj if ok else None}
                out = 'then' if ok else 'CastFailed'
            elif kind in ('call', 'array_call'):
                self.cache[current] = self.call(node)
            else:
                raise SimulationError(f'cannot execute {kind} {current}')
            current = self.exec_to.get(f'{current}.{out}')
        return self.finish()

    def sub(self, start):
        saved = self.exec_to.get('entry.then')
        self.exec_to['entry.then'] = start
        try:
            self._result = self.run()
        finally:
            self.exec_to['entry.then'] = saved

    def finish(self):
        return self.outputs


class Widget:
    """A stand-in UMG widget: remembers its text, visibility and list items."""

    def __init__(self, name):
        self.name, self.text, self.visibility, self.items, self.color = name, '', 'Visible', [], None
        self.focused, self.offsets, self.position = False, None, None

    def __repr__(self):
        return f'<{self.name} {self.text!r}>'


def _set_text(self=None, InText=''):
    self.text = str(InText)
    return {}


UMG = {
    '/Script/UMG.TextBlock:SetText': _set_text,
    '/Script/UMG.EditableTextBox:SetText': _set_text,
    '/Script/UMG.EditableTextBox:GetText': lambda self=None: {'ReturnValue': self.text},
    '/Script/UMG.Widget:SetVisibility': lambda self=None, InVisibility='Visible': (setattr(self, 'visibility', InVisibility), {})[1],
    '/Script/UMG.TextBlock:GetText': lambda self=None: {'ReturnValue': self.text},
    '/Script/UMG.Widget:SetKeyboardFocus': lambda self=None: (setattr(self, 'focused', True), {})[1],
    # A canvas slot stands for its widget: the widget records its offsets and position.
    '/Script/UMG.WidgetLayoutLibrary:SlotAsCanvasSlot': lambda Widget=None: {'ReturnValue': Widget},
    '/Script/UMG.CanvasPanelSlot:SetOffsets': lambda self=None, InOffset=None: (setattr(self, 'offsets', InOffset), {})[1],
    '/Script/UMG.CanvasPanelSlot:SetPosition': lambda self=None, InPosition=None: (setattr(self, 'position', InPosition), {})[1],
    '/Script/Engine.KismetMathLibrary:MakeVector2D': lambda X=0, Y=0: {'ReturnValue': (float(X), float(Y))},
    '/Script/UMG.ListView:ClearListItems': lambda self=None: (self.items.clear(), {})[1],
    '/Script/UMG.ListView:AddItem': lambda self=None, Item=None: (self.items.append(Item), {})[1],
    '/Script/UMG.ListViewBase:RegenerateAllEntries': lambda self=None: {},
    '/Script/UMG.Border:SetBrushColor': lambda self=None, InBrushColor=None: (setattr(self, 'color', InBrushColor), {})[1],
    '/Script/UMG.Image:SetColorAndOpacity': lambda self=None, InColorAndOpacity=None: {},
    '/Script/UMG.TextBlock:SetColorAndOpacity': lambda self=None, InColorAndOpacity=None: {},
    '/Script/UMG.Image:SetBrushFromTexture': lambda self=None, Texture=None, bMatchSize=None: {},
    '/Script/Engine.KismetSystemLibrary:LaunchURL': lambda URL='': {},
    '/Script/Engine.KismetSystemLibrary:GetProjectSavedDirectory': lambda: {'ReturnValue': 'C:/Saved/'},
    '/Script/Engine.BlueprintPathsLibrary:FileExists': lambda InPath='': {'ReturnValue': False},
}


class Simulator:
    def __init__(self, specs, engine=None, overrides=None):
        self.specs = specs
        self.engine = dict(ENGINE, **UMG, **(engine or {}))
        self.overrides = dict(overrides or {})
        self.functions_by_path, self.variables_by_path, self.parents = {}, {}, {}
        for spec in specs:
            path = spec.get('path')
            if not path:
                continue
            self.functions_by_path.setdefault(path, {}).update({f['name']: f for f in spec.get('functions', [])})
            self.variables_by_path.setdefault(path, []).extend(spec.get('variables', []))
            if spec.get('parent'):
                self.parents[path] = spec['parent']

    @classmethod
    def load(cls, folder=GENERATED, engine=None, overrides=None):
        return cls([json.loads(p.read_text()) for p in sorted(Path(folder).glob('*.json'))], engine, overrides)

    def chain(self, path):
        while path:
            yield path
            path = self.parents.get(path)

    def is_a(self, path, wanted):
        return any(p == wanted for p in self.chain(path))

    @staticmethod
    def display(path):
        name = path.rsplit('/', 1)[-1].split('.')[0]
        out = ''
        for i, c in enumerate(name):
            if c == '_':
                out += ' '
            elif c.isupper() and i and name[i - 1].islower():
                out += ' ' + c
            else:
                out += c
        return out

    @staticmethod
    def default(var):
        kind = var['type']
        raw = var.get('default')
        if kind.endswith('[]'):
            return [] if raw in (None, '', '()') else json.loads(raw) if raw.startswith('[') else []
        if kind == 'bool':
            return boolean(raw) if raw is not None else False
        if kind in ('int', 'int64'):
            return int(raw) if raw not in (None, '') else 0
        if kind in ('double', 'float'):
            return float(raw) if raw not in (None, '') else 0.0
        if kind == 'string':
            return raw or ''
        if kind == 'vector':
            return vector(raw) if raw else (0.0, 0.0, 0.0)
        return None

    @staticmethod
    def coerce(old, value):
        if isinstance(old, bool):
            return boolean(value)
        if isinstance(old, int) and isinstance(value, str):
            return int(number(value))
        if isinstance(old, float) and isinstance(value, str):
            return float(number(value))
        return value

    def instance(self, path, **values):
        variables = {}
        for p in reversed(list(self.chain(path))):
            for var in self.variables_by_path.get(p, []):
                variables[var['name']] = self.default(var)
        unknown = set(values) - set(variables)
        if unknown:
            raise SimulationError(f'{path} has no variables {sorted(unknown)}')
        variables.update(values)
        return Instance(path, variables)

    def find(self, path, name):
        for p in self.chain(path):
            fn = self.functions_by_path.get(p, {}).get(name)
            if fn:
                return fn
        raise SimulationError(f'{path} has no function {name}')

    def widgets(self, path):
        """An instance of a widget Blueprint whose named widgets are stand-ins."""
        spec = next(s for s in self.specs if s.get('path') == path)
        names = set()

        def walk(node):
            if node.get('variable'):
                names.add(node['name'])
            for child in node.get('children', []):
                walk(child)
        walk(spec['tree'])
        return Instance(path, {name: Widget(name) for name in names})

    def run(self, obj, name, **inputs):
        if name in self.overrides:
            return self.overrides[name](obj, **inputs) or {}
        if not isinstance(obj, Instance):
            raise SimulationError(f'{name} called on {obj!r}')
        graph = self.find(obj.path, name)
        for var in graph.get('inputs', []):
            inputs.setdefault(var['name'], self.default(var))
            if var['type'] in ('int', 'int64') and isinstance(inputs[var['name']], str):
                inputs[var['name']] = int(number(inputs[var['name']]))
            if var['type'] == 'bool' and isinstance(inputs[var['name']], str):
                inputs[var['name']] = boolean(inputs[var['name']])
        return Frame(self, obj, graph, inputs).run()
