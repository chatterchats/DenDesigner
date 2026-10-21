#!/usr/bin/env python3
"""Restricted UE 5.6 GVAS codec for Den Designer's published native schema.

This is an offline migration tool, not a game dependency. Unknown fields, types,
headers and serialization flags are rejected instead of guessed. Schema defaults
matter: Unreal can omit values equal to the Blueprint class/struct defaults.
"""
import json
import math
import struct
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name('den_save_schema.json')
MAX_BYTES = 128 * 1024 * 1024
MAX_ITEMS = 100000


def string(value):
    if not isinstance(value, str) or '\0' in value:
        raise ValueError('Expected a string without NUL characters')
    if not value:
        return struct.pack('<i', 0)
    if value.isascii():
        raw = value.encode('ascii') + b'\0'
        return struct.pack('<i', len(raw)) + raw
    raw = value.encode('utf-16-le') + b'\0\0'
    return struct.pack('<i', -len(raw) // 2) + raw


class Reader:
    def __init__(self, data):
        if len(data) > MAX_BYTES:
            raise ValueError('Save exceeds the migration size limit')
        self.data, self.pos = data, 0

    def take(self, count):
        if count < 0 or count > len(self.data) - self.pos:
            raise ValueError(f'Truncated save at byte {self.pos}')
        result = self.data[self.pos:self.pos + count]
        self.pos += count
        return result

    def number(self, fmt):
        result = struct.unpack('<' + fmt, self.take(struct.calcsize('<' + fmt)))
        return result[0] if len(result) == 1 else list(result)

    def string(self):
        count = self.number('i')
        if count == 0:
            return ''
        value = self.take(abs(count) * (2 if count < 0 else 1)).decode('utf-16-le' if count < 0 else 'ascii')
        if not value.endswith('\0') or '\0' in value[:-1]:
            raise ValueError('Invalid FString termination')
        return value[:-1]

    def typename(self, depth=0):
        if depth > 8:
            raise ValueError('Excessive type nesting')
        name, count = self.string(), self.number('i')
        if not 0 <= count <= 8:
            raise ValueError('Invalid type parameter count')
        return [name, [self.typename(depth + 1) for _ in range(count)]]

    def header(self):
        base = (self.take(4), self.number("iii"), self.number("HHHI"), self.string(), self.number("i"))
        count = self.number("i")
        if base[0] != b"GVAS" or base[1][0] != 3 or base[4] != 3 or not 0 <= count < 1000:
            raise ValueError("Unsupported save header")
        versions = {}
        for _ in range(count):
            guid, version = self.take(16), self.number("i")
            if guid in versions:
                raise ValueError("Duplicate custom version GUID")
            versions[guid] = version
        return base, versions

    def end(self):
        if self.pos != len(self.data):
            raise ValueError(f'Unexpected trailing data at {self.pos}')


class Codec:
    def __init__(self, path=SCHEMA_PATH):
        self.schema = json.loads(Path(path).read_text())
        if self.schema['version'] != 1:
            raise ValueError('Unsupported migration schema')
        self.header = bytes.fromhex(self.schema['header'])
        # Kit and shipping builds register different custom-version sets. Accept
        # only explicitly verified profiles; never ignore unfamiliar versions.
        self.accepted_headers = [Reader(self.header).header()]
        for profile in self.schema.get('compatible_headers', []):
            reader = Reader(bytes.fromhex(profile['header']))
            self.accepted_headers.append(reader.header())
            reader.end()
        self.types = self.schema['types']
        self.classes = self.schema['classes']

    def typename(self, kind):
        if kind.endswith('[]'):
            return ['ArrayProperty', [self.typename(kind[:-2])]]
        primitive = {'int':'IntProperty', 'int64':'Int64Property', 'bool':'BoolProperty', 'string':'StrProperty'}
        if kind in primitive:
            return [primitive[kind], []]
        if kind in ('vector', 'rotator'):
            return ['StructProperty', [[{'vector':'Vector', 'rotator':'Rotator'}[kind], [['/Script/CoreUObject', []]]]]]
        if kind.startswith('struct:'):
            path = kind[7:]
            spec = self.types[path]
            return ['StructProperty', [[path.rsplit('/',1)[1], [[path, []]]], [spec['guid'], []]]]
        raise ValueError('Unsupported type: ' + kind)

    def encode_type(self, tree):
        name, params = tree
        return string(name) + struct.pack('<i', len(params)) + b''.join(self.encode_type(p) for p in params)

    def fields(self, kind):
        return self.types[kind]['fields'] if kind in self.types else self.classes[kind]['fields']

    def default(self, field):
        return json.loads(json.dumps(field['default']))

    def encode_value(self, kind, value):
        if kind.endswith('[]'):
            if not isinstance(value, list) or len(value) > MAX_ITEMS:
                raise ValueError('Invalid or oversized array')
            return struct.pack('<i', len(value)) + b''.join(self.encode_value(kind[:-2], v) for v in value)
        if kind == 'string':
            return string(value)
        if kind == 'bool':
            if type(value) is not bool:
                raise ValueError('Expected boolean')
            return b''
        if kind in ('int','int64'):
            if type(value) is not int:
                raise ValueError('Expected integer')
            return struct.pack('<i' if kind == 'int' else '<q', value)
        if kind in ('vector','rotator'):
            if not isinstance(value, (tuple,list)) or len(value) != 3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in value):
                raise ValueError('Expected three finite numbers')
            return struct.pack('<ddd', *value)
        if kind.startswith('struct:'):
            return self.encode_properties(kind[7:], value)
        raise ValueError('Unsupported value type: ' + kind)

    def encode_properties(self, kind, values):
        fields = self.fields(kind)
        unknown = set(values) - {f['name'] for f in fields}
        if unknown:
            raise ValueError('Unknown fields: ' + ', '.join(sorted(unknown)))
        out = []
        for f in fields:
            value = values.get(f['name'], self.default(f))
            body = self.encode_value(f['type'], value)
            flags = 16 if f['type'] == 'bool' and value else 8 if f['type'] in ('vector','rotator') else 0
            out.append(string(f['serialized']) + self.encode_type(self.typename(f['type'])) + struct.pack('<iB',len(body),flags) + body)
        return b''.join(out) + string('None')

    def decode_value(self, reader, kind, flags=0):
        if kind.endswith('[]'):
            count = reader.number('i')
            if not 0 <= count <= MAX_ITEMS:
                raise ValueError('Invalid array length')
            return [self.decode_value(reader, kind[:-2]) for _ in range(count)]
        if kind == 'string':
            return reader.string()
        if kind == 'bool':
            return bool(flags & 16)
        if kind in ('int','int64'):
            return reader.number('i' if kind == 'int' else 'q')
        if kind in ('vector','rotator'):
            value = reader.number('ddd')
            if not all(math.isfinite(v) for v in value):
                raise ValueError('Nonfinite transform')
            return value
        if kind.startswith('struct:'):
            return self.decode_properties(reader, kind[7:])
        raise ValueError('Unsupported value type: ' + kind)

    def decode_properties(self, reader, kind):
        fields = {f['serialized']:f for f in self.fields(kind)}
        result = {f['name']:self.default(f) for f in fields.values()}
        seen = set()
        while True:
            name = reader.string()
            if name == 'None':
                return result
            if name not in fields or name in seen:
                raise ValueError('Unknown or duplicate property: ' + name)
            seen.add(name)
            f = fields[name]
            if reader.typename() != self.typename(f['type']):
                raise ValueError('Mismatched property type: ' + name)
            size, flags = reader.number('iB')
            allowed = 2 | (16 if f['type'] == 'bool' else 8 if f['type'] in ('vector','rotator') else 0)
            if flags & ~allowed:
                raise ValueError('Unsupported serialization flags: ' + name)
            if flags & 2:
                reader.take(16)  # Optional editor-assigned property GUID; identity is the schema name.
            body = Reader(reader.take(size))
            result[f['name']] = self.decode_value(body, f['type'], flags)
            body.end()

    def encode(self, class_path, values):
        if class_path not in self.classes:
            raise ValueError('Unsupported SaveGame class')
        data = self.header + string(class_path) + b'\0' + self.encode_properties(class_path, values) + b'\0'*4
        if len(data) > MAX_BYTES:
            raise ValueError('Save exceeds the migration size limit')
        return data

    def decode(self, data):
        reader = Reader(data)
        if reader.header() not in self.accepted_headers:
            raise ValueError('Unsupported engine/custom-version header')
        class_path = reader.string()
        if class_path not in self.classes or reader.number('B') != 0:
            raise ValueError('Unsupported class or serialization extension')
        values = self.decode_properties(reader, class_path)
        if reader.take(4) != b'\0'*4:
            raise ValueError('Invalid object trailer')
        reader.end()
        return class_path, values
