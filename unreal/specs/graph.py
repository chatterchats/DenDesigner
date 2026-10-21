"""Shared Blueprint graph specification helpers for ZComAuthoring."""

GS = "/Script/Engine.GameplayStatics"
KSL = "/Script/Engine.KismetSystemLibrary"
KML = "/Script/Engine.KismetMathLibrary"
WBL = "/Script/UMG.WidgetBlueprintLibrary"


class Graph:
    def __init__(self):
        self.nodes, self.links = [], []

    def node(self, ident, kind, **fields):
        self.nodes.append(dict(id=ident, kind=kind, **fields))
        return ident

    def call(self, ident, function, **defaults):
        return self.node(ident, "call", function=function, defaults={k: str(v) for k, v in defaults.items()})

    def get(self, ident, var):
        return self.node(ident, "get", var=var)

    def set(self, ident, var, value=None):
        args = {} if value is None else {"defaults": {var.rsplit(":", 1)[-1]: str(value)}}
        return self.node(ident, "set", var=var, **args)

    def wire(self, *pairs):
        self.links.extend([list(p) for p in pairs])

    def chain(self, *steps):
        for a, b in zip(steps, steps[1:]):
            self.wire((a if "." in a else a + ".then", b if "." in b else b + ".execute"))

    def spec(self):
        return {"nodes": self.nodes, "links": self.links}

    def function(self, name, **fields):
        return dict(name=name, **fields, **self.spec())


def variable(name, type_, default=None):
    return dict(name=name, type=type_, **({"default": default} if default is not None else {}))

