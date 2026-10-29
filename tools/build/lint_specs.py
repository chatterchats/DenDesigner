#!/usr/bin/env python3
"""Offline checks for generated Blueprint specs (unreal/generated/runtime).

The Unreal kit is the real compiler. This catches the common authoring
mistakes before a kit build: links to missing nodes or pins that cannot exist,
calls to functions no Blueprint defines, variables nobody declares, an exec
output wired twice, and engine calls or pins never used before (reported
separately as "new", to be checked by hand against the engine). Problems the
baseline already has (and the kit accepts) are not repeated.

  python3 tools/build/lint_specs.py [--baseline <dir>]

--baseline points at a known-good generated folder. By default it is the one in
the commit named in tools/build/spec-baseline.txt: the last commit whose specs
the kit built without errors. Update that file after a successful kit build.
"""
import argparse
import collections
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / 'unreal/generated/runtime'
EXEC_OUT = {'then', 'else', 'CastFailed'}


def load(folder):
    specs = {}
    for path in sorted(Path(folder).glob('*.json')):
        spec = json.loads(path.read_text())
        specs[path.name] = spec
    return specs


BASELINE = ROOT / 'tools/build/spec-baseline.txt'


def head_baseline(ref=None):
    ref = ref or BASELINE.read_text().strip()
    temp = Path(tempfile.mkdtemp())
    listing = subprocess.run(['git', 'ls-tree', '--name-only', ref, 'unreal/generated/runtime/'],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    for name in listing:
        data = subprocess.run(['git', 'show', ref + ':' + name], cwd=ROOT, capture_output=True, check=True).stdout
        (temp / Path(name).name).write_bytes(data)
    return temp


def graphs(spec):
    for fn in spec.get('functions', []):
        yield fn.get('name', '?'), fn
    if 'graph' in spec:
        yield '<event graph>', spec['graph']


def engine_pins(specs):
    """Engine function -> pins seen on it (defaults and links)."""
    pins = collections.defaultdict(set)
    for spec in specs.values():
        for _, graph in graphs(spec):
            nodes = {n['id']: n for n in graph.get('nodes', [])}
            for n in nodes.values():
                if n['kind'] in ('call', 'array_call') and not n['function'].startswith('self:'):
                    pins[n['function']].update(n.get('defaults', {}))
            for a, b in graph.get('links', []):
                for end in (a, b):
                    node, _, pin = end.partition('.')
                    n = nodes.get(node)
                    if n and n['kind'] in ('call', 'array_call') and not n['function'].startswith('self:'):
                        pins[n['function']].add(pin)
    return pins


def tree_variables(tree):
    found = set()
    def walk(node):
        if node.get('variable'):
            found.add(node['name'])
        for child in node.get('children', []):
            walk(child)
    if tree:
        walk(tree)
    return found


def blueprint_index(specs):
    """path -> (functions, variables) including parents defined in the set."""
    own = {}
    parents = {}
    for spec in specs.values():
        path = spec.get('path')
        if not path:
            continue
        fns, vars_ = own.setdefault(path, (set(), set()))
        fns.update(fn['name'] for fn in spec.get('functions', []))
        vars_.update(v['name'] for v in spec.get('variables', []))
        vars_.update(f['name'] for f in spec.get('fields', []) if isinstance(f, dict) and 'name' in f)
        vars_.update(tree_variables(spec.get('tree')))
        vars_.update(c.get('name') for c in spec.get('components', []) if isinstance(c, dict))
        for g in spec.get('graph', {}).get('nodes', []) if isinstance(spec.get('graph'), dict) else []:
            if g['kind'] == 'custom_event':
                fns.add(g.get('name', ''))
        if spec.get('parent'):
            parents[path] = spec['parent']
    full = {}
    for path in own:
        fns, vars_ = set(), set()
        cursor, seen = path, set()
        while cursor in own and cursor not in seen:
            seen.add(cursor)
            fns |= own[cursor][0]
            vars_ |= own[cursor][1]
            cursor = parents.get(cursor)
        full[path] = (fns, vars_)
    return full


def lint(specs, baseline_pins, baseline_tree=None):
    problems, novel = [], []
    index = blueprint_index(specs)
    for name, spec in specs.items():
        path = spec.get('path')
        fns, vars_ = index.get(path, (set(), set()))
        for fname, graph in graphs(spec):
            where = f'{name}:{fname}'
            nodes = {n['id']: n for n in graph.get('nodes', [])}
            ids = set(nodes) | {'entry', 'result'}
            local = {v['name'] for v in graph.get('locals', [])}
            inputs = {v['name'] for v in graph.get('inputs', [])}
            outputs = {v['name'] for v in graph.get('outputs', [])}
            # The kit compares node ids without case.
            dupes = [k for k, c in collections.Counter(n['id'].lower() for n in graph.get('nodes', [])).items() if c > 1]
            if dupes:
                problems.append(f'{where}: duplicate node ids {dupes[:5]}')
            for name in sorted(local & (inputs | outputs | vars_)):
                problems.append(f'{where}: local {name!r} collides with a member or parameter')
            used_exec = collections.Counter()
            for a, b in graph.get('links', []):
                for end in (a, b):
                    node, dot, pin = end.partition('.')
                    if not dot or node not in ids:
                        problems.append(f'{where}: link to missing node {end!r}')
                if a.partition('.')[2] in EXEC_OUT or (a.split('.')[0] in nodes and nodes[a.split('.')[0]]['kind'] == 'sequence' and a.split('.')[1].startswith('then')):
                    used_exec[a] += 1
                if a.startswith('entry.') and a != 'entry.then' and fname != '<event graph>' and a[6:] not in inputs:
                    problems.append(f'{where}: entry has no input {a[6:]!r}')
                if b.startswith('result.') and b != 'result.execute' and b[7:] not in outputs:
                    problems.append(f'{where}: result has no output {b[7:]!r}')
            executes = any(b.endswith('.execute') for _, b in graph.get('links', []))
            if fname != '<event graph>' and executes and not any(a == 'entry.then' for a, _ in graph.get('links', [])):
                problems.append(f'{where}: nothing runs: entry.then is not linked')
            for exec_pin, count in used_exec.items():
                if count > 1:
                    problems.append(f'{where}: exec output {exec_pin} wired {count} times')
            for n in nodes.values():
                kind = n['kind']
                if kind in ('call', 'array_call'):
                    fn = n['function']
                    if fn.startswith('self:'):
                        if fn[5:] not in fns:
                            problems.append(f'{where}: {n["id"]} calls undefined self:{fn[5:]}')
                    elif fn not in baseline_pins:
                        target, _, member = fn.rpartition(':')
                        owner = index.get(target)
                        if owner is not None:
                            if member not in owner[0]:
                                problems.append(f'{where}: {n["id"]} calls undefined {fn}')
                        else:
                            novel.append(f'{where}: {n["id"]} new engine call {fn}')
                    else:
                        used = set(n.get('defaults', {}))
                        used |= {e.partition('.')[2] for l in graph.get('links', []) for e in l if e.partition('.')[0] == n['id']}
                        for pin in sorted(used - baseline_pins[fn] - {'execute', 'then', 'ReturnValue', 'self'}):
                            novel.append(f'{where}: {n["id"]} new pin {fn}.{pin}')
                elif kind in ('get', 'set'):
                    var = n['var']
                    if var.startswith('local:'):
                        if var[6:] not in local:
                            problems.append(f'{where}: {n["id"]} undeclared local {var[6:]}')
                    elif ':' in var:
                        target, _, member = var.rpartition(':')
                        owner = index.get(target)
                        if owner is not None and member not in owner[1]:
                            problems.append(f'{where}: {n["id"]} {target} has no variable {member}')
                    elif var not in vars_ and var not in inputs:
                        problems.append(f'{where}: {n["id"]} undeclared variable {var}')
    problems += tree_problems(specs, baseline_tree)
    return problems, novel


def tree_pairs(specs):
    """(parent class, slot key) and (class, property) pairs used in widget trees."""
    slots, props = set(), set()

    def walk(node, parent):
        slots.update((parent, key) for key in node.get('slot', {}))
        props.update((node['class'], key) for key in node.get('props', {}))
        for child in node.get('children', []):
            walk(child, node['class'])
    for spec in specs.values():
        if spec.get('tree'):
            walk(spec['tree'], None)
    return slots, props


def tree_problems(specs, baseline):
    """Slot settings a parent type never takes in the baseline (a SizeBox slot has
    no Size), and padding that is not text."""
    if baseline is None:
        return []
    slots, _ = baseline
    problems = []

    def walk(name, node, parent, path):
        path = path + '/' + node['name']
        for key, value in node.get('slot', {}).items():
            if (parent, key) not in slots:
                problems.append(f'{name}: {path}: a {parent} slot has no {key!r}')
            if 'Padding' in key and not isinstance(value, str):
                problems.append(f'{name}: {path}: slot {key} is not text')
        for key, value in node.get('props', {}).items():
            if 'Padding' in key and not isinstance(value, str):
                problems.append(f'{name}: {path}: {key} is not text')
        for child in node.get('children', []):
            walk(name, child, node['class'], path)
    for name, spec in specs.items():
        if spec.get('tree'):
            walk(name, spec['tree'], None, '')
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--folder', type=Path, default=GENERATED)
    parser.add_argument('--show-new', action='store_true', help='list new engine calls and pins')
    args = parser.parse_args()
    baseline = load(args.baseline or head_baseline())
    pins = engine_pins(baseline)
    pairs = tree_pairs(baseline)
    # Patterns the kit already accepts in the baseline are not reported again.
    known = set(lint(baseline, pins, pairs)[0])
    problems, novel = lint(load(args.folder), pins, pairs)
    problems = [p for p in problems if p not in known]
    for line in problems:
        print('PROBLEM', line)
    if args.show_new:
        for line in novel:
            print('NEW', line)
    print(f'{len(problems)} problems, {len(novel)} new engine calls/pins to check')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
