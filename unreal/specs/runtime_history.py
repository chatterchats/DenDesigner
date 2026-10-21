"""Blueprint session history. Data mutations are atomic; world application is the coordinator's job."""
from graph import Graph, variable as v, KML, KSL


def spec(root, layout, entry, mutation, change, step, arr, unpack):
    def guard(g):
        g.get('doc', 'Working')
        g.call('valid', KSL + ':IsValid')
        g.node('guard', 'branch')
        g.wire(('doc.Working', 'valid.Object'), ('valid.ReturnValue', 'guard.Condition'))
        g.chain('entry', 'guard')
        g.chain('guard.else', 'result')

    def initialize():
        g = Graph()
        g.set('working', 'Working')
        g.get('undos', 'UndoSteps')
        g.get('redos', 'RedoSteps')
        arr(g, 'clearundo', 'Clear', 'undos.UndoSteps')
        arr(g, 'clearredo', 'Clear', 'redos.RedoSteps')
        for name in ['Version', 'SavedVersion', 'NextVersion']:
            g.set(name, name, '0')
        g.wire(('entry.Document', 'working.Working'))
        g.chain('entry', 'working', 'clearundo', 'clearredo', 'Version', 'SavedVersion', 'NextVersion')
        return g.function('Initialize', inputs=[v('Document', 'object:' + layout)])

    def merge_candidate():
        g = Graph()
        g.set('default', 'local:OutputStep')
        g.get('out', 'local:OutputStep')
        g.get('merged', 'local:DidMerge')
        g.get('undos', 'UndoSteps')
        g.get('version', 'Version')
        g.get('saved', 'SavedVersion')
        arr(g, 'length', 'Length', 'undos.UndoSteps')
        g.call('nonempty', KML + ':Greater_IntInt', B=0)
        g.node('has', 'branch')
        g.call('last', KML + ':Subtract_IntInt', B=1)
        arr(g, 'top', 'Get', 'undos.UndoSteps')
        unpack(g, 'old', step, 'top.Item')
        unpack(g, 'new', step, 'entry.Candidate')
        checks = []

        def compare(name, fn, a, b=None, constant=None):
            g.call(name, fn, **({'B': constant} if constant is not None else {}))
            g.wire((a, name + '.A'))
            if b:
                g.wire((b, name + '.B'))
            checks.append(name + '.ReturnValue')

        string = '/Script/Engine.KismetStringLibrary:'
        compare('keynonempty', string + 'NotEqual_StrStr', 'new.MergeKey', constant='')
        compare('samekey', string + 'EqualEqual_StrStr', 'old.MergeKey', 'new.MergeKey')
        compare('sameversion', KML + ':EqualEqual_IntInt', 'old.AfterVersion', 'version.Version')
        compare('unsaved', KML + ':NotEqual_IntInt', 'saved.SavedVersion', 'version.Version')
        g.call('elapsed', KML + ':Subtract_DoubleDouble')
        g.wire(('new.Time', 'elapsed.A'), ('old.Time', 'elapsed.B'))
        compare('notredone', KML + ':GreaterEqual_DoubleDouble', 'old.Time', constant=0)
        compare('forwardtime', KML + ':GreaterEqual_DoubleDouble', 'elapsed.ReturnValue', constant=0)
        compare('recent', KML + ':LessEqual_DoubleDouble', 'elapsed.ReturnValue', constant=1)
        arr(g, 'oldcount', 'Length', 'old.Changes')
        arr(g, 'newcount', 'Length', 'new.Changes')
        compare('samecount', KML + ':EqualEqual_IntInt', 'oldcount.ReturnValue', 'newcount.ReturnValue')
        condition = checks[0]
        for i, pin in enumerate(checks[1:]):
            node = 'all' + str(i)
            g.call(node, KML + ':BooleanAND')
            g.wire((condition, node + '.A'), (pin, node + '.B'))
            condition = node + '.ReturnValue'
        g.node('eligible', 'branch')
        g.get('i', 'local:Cursor')
        g.call('within', KML + ':Less_IntInt')
        g.node('loop', 'branch')
        arr(g, 'olditem', 'Get', 'old.Changes')
        arr(g, 'newitem', 'Get', 'new.Changes')
        unpack(g, 'oldchange', change, 'olditem.Item')
        unpack(g, 'newchange', change, 'newitem.Item')
        unpack(g, 'oldentry', entry, 'oldchange.After')
        unpack(g, 'newentry', entry, 'newchange.After')
        g.call('kindmatch', KML + ':EqualEqual_IntInt')
        g.call('idmatch', string + 'EqualEqual_StrStr')
        g.call('same', KML + ':BooleanAND')
        g.node('match', 'branch')
        g.node('combined', 'make_struct', struct=change)
        g.get('changes', 'local:MergedChanges')
        arr(g, 'append', 'Add', 'changes.MergedChanges')
        g.call('next', KML + ':Add_IntInt', B=1)
        g.set('advance', 'local:Cursor')
        g.node('step', 'make_struct', struct=step)
        g.set('output', 'local:OutputStep')
        g.set('success', 'local:DidMerge', 'true')
        g.wire(('entry.Candidate', 'default.OutputStep'), ('out.OutputStep', 'result.Step'),
               ('merged.DidMerge', 'result.Merged'), ('length.ReturnValue', 'nonempty.A'),
               ('nonempty.ReturnValue', 'has.Condition'), ('length.ReturnValue', 'last.A'),
               ('last.ReturnValue', 'top.Index'), (condition, 'eligible.Condition'),
               ('i.Cursor', 'within.A'), ('newcount.ReturnValue', 'within.B'),
               ('within.ReturnValue', 'loop.Condition'), ('i.Cursor', 'olditem.Index'), ('i.Cursor', 'newitem.Index'),
               ('oldentry.Kind', 'kindmatch.A'), ('newentry.Kind', 'kindmatch.B'),
               ('oldentry.Key', 'idmatch.A'), ('newentry.Key', 'idmatch.B'),
               ('kindmatch.ReturnValue', 'same.A'), ('idmatch.ReturnValue', 'same.B'),
               ('same.ReturnValue', 'match.Condition'),
               ('oldchange.BeforeExists', 'combined.BeforeExists'), ('oldchange.Before', 'combined.Before'),
               ('newchange.AfterExists', 'combined.AfterExists'), ('newchange.After', 'combined.After'),
               ('combined.ST_DenChange', 'append.NewItem'), ('i.Cursor', 'next.A'), ('next.ReturnValue', 'advance.Cursor'),
               ('new.Label', 'step.Label'), ('new.MergeKey', 'step.MergeKey'), ('new.Time', 'step.Time'),
               ('old.BeforeVersion', 'step.BeforeVersion'), ('new.AfterVersion', 'step.AfterVersion'),
               ('changes.MergedChanges', 'step.Changes'), ('step.ST_DenStep', 'output.OutputStep'))
        g.chain('entry', 'default', 'has', 'eligible', 'loop', 'match', 'append', 'advance', 'loop')
        for node in ['has', 'eligible', 'match']:
            g.chain(node + '.else', 'result')
        g.chain('loop.else', 'output', 'success', 'result')
        return g.function('MergeCandidate', inputs=[v('Candidate', 'struct:' + step)],
                          outputs=[v('Step', 'struct:' + step), v('Merged', 'bool')],
                          locals=[v('OutputStep', 'struct:' + step), v('DidMerge', 'bool', 'false'),
                                  v('Cursor', 'int', '0'), v('MergedChanges', 'struct:' + change + '[]')])

    def commit():
        g = Graph()
        guard(g)
        g.call('apply', layout + ':ApplyBatch')
        g.node('accepted', 'branch')
        g.get('version', 'Version')
        g.get('nextversion', 'NextVersion')
        g.call('next', KML + ':Add_IntInt', B=1)
        g.node('step', 'make_struct', struct=step)
        g.set('cache', 'local:NewStep')
        g.get('cached', 'local:NewStep')
        unpack(g, 'stepdata', step, 'cached.NewStep')
        g.set('versionup', 'Version')
        g.set('nextup', 'NextVersion')
        g.get('undos', 'UndoSteps')
        g.get('redos', 'RedoSteps')
        arr(g, 'push', 'Add', 'undos.UndoSteps')
        arr(g, 'clearredo', 'Clear', 'redos.RedoSteps')
        arr(g, 'length', 'Length', 'undos.UndoSteps')
        g.call('over', KML + ':Greater_IntInt', B=200)
        g.node('trim', 'branch')
        g.call('merge', 'self:MergeCandidate')
        g.set('choose', 'local:NewStep')
        g.node('merged', 'branch')
        g.call('lastundo', KML + ':Subtract_IntInt', B=1)
        arr(g, 'popmerged', 'Remove', 'undos.UndoSteps')
        arr(g, 'removeoldest', 'Remove', 'undos.UndoSteps', IndexToRemove=0)
        g.set('ok', 'local:DidSucceed', 'true')
        g.get('okout', 'local:DidSucceed')
        g.wire(('doc.Working', 'apply.self'), ('entry.Mutations', 'apply.Mutations'),
               ('apply.Accepted', 'accepted.Condition'), ('entry.Label', 'step.Label'),
               ('entry.MergeKey', 'step.MergeKey'), ('entry.Time', 'step.Time'),
               ('apply.Changes', 'step.Changes'), ('version.Version', 'step.BeforeVersion'),
               ('nextversion.NextVersion', 'next.A'), ('next.ReturnValue', 'step.AfterVersion'),
               ('step.ST_DenStep', 'cache.NewStep'), ('stepdata.AfterVersion', 'versionup.Version'),
               ('stepdata.AfterVersion', 'nextup.NextVersion'), ('cached.NewStep', 'push.NewItem'),
               ('length.ReturnValue', 'over.A'), ('over.ReturnValue', 'trim.Condition'),
               ('okout.DidSucceed', 'result.Accepted'),
               ('cached.NewStep', 'merge.Candidate'), ('merge.Step', 'choose.NewStep'),
               ('merge.Merged', 'merged.Condition'), ('length.ReturnValue', 'lastundo.A'),
               ('lastundo.ReturnValue', 'popmerged.IndexToRemove'))
        g.chain('guard', 'apply', 'accepted', 'cache', 'merge', 'choose', 'merged', 'popmerged', 'versionup', 'nextup', 'push', 'clearredo', 'ok', 'trim', 'removeoldest', 'result')
        g.chain('accepted.else', 'result')
        g.chain('trim.else', 'result')
        g.chain('merged.else', 'versionup')
        return g.function('Commit', inputs=[v('Mutations', 'struct:' + mutation + '[]'),
                          v('Label', 'string'), v('MergeKey', 'string'), v('Time', 'double')],
                          outputs=[v('Accepted', 'bool')],
                          locals=[v('NewStep', 'struct:' + step), v('DidSucceed', 'bool', 'false')])

    def travel(redo=False):
        name = 'Redo' if redo else 'Undo'
        source, target = ('RedoSteps', 'UndoSteps') if redo else ('UndoSteps', 'RedoSteps')
        side = 'After' if redo else 'Before'
        g = Graph()
        guard(g)
        g.get('source', source)
        g.get('target', target)
        arr(g, 'length', 'Length', 'source.' + source)
        g.call('last', KML + ':Subtract_IntInt', B=1)
        g.call('nonempty', KML + ':Greater_IntInt', B=0)
        g.node('has', 'branch')
        arr(g, 'top', 'Get', 'source.' + source)
        g.set('cache', 'local:CachedStep')
        g.get('cached', 'local:CachedStep')
        unpack(g, 'fields', step, 'cached.CachedStep')
        arr(g, 'count', 'Length', 'fields.Changes')
        g.call('lastchange', KML + ':Subtract_IntInt', B=1)
        g.set('startindex', 'local:Cursor', '0' if redo else None)
        g.get('i', 'local:Cursor')
        g.call('within', KML + (':Less_IntInt' if redo else ':GreaterEqual_IntInt'), **({} if redo else {'B': 0}))
        g.node('loop', 'branch')
        arr(g, 'item', 'Get', 'fields.Changes')
        unpack(g, 'change', change, 'item.Item')
        g.node('mutation', 'make_struct', struct=mutation)
        g.get('mutations', 'local:Edits')
        arr(g, 'append', 'Add', 'mutations.Edits')
        g.call('next', KML + ':Add_IntInt', B=1 if redo else -1)
        g.set('advance', 'local:Cursor')
        g.call('apply', layout + ':ApplyBatch')
        g.node('accepted', 'branch')
        arr(g, 'pop', 'Remove', 'source.' + source)
        arr(g, 'push', 'Add', 'target.' + target)
        g.set('version', 'Version')
        g.set('ok', 'local:DidSucceed', 'true')
        g.get('okout', 'local:DidSucceed')
        g.wire(('length.ReturnValue', 'nonempty.A'), ('nonempty.ReturnValue', 'has.Condition'),
               ('length.ReturnValue', 'last.A'), ('last.ReturnValue', 'top.Index'),
               ('top.Item', 'cache.CachedStep'), ('count.ReturnValue', 'lastchange.A'),
               ('i.Cursor', 'within.A'), ('within.ReturnValue', 'loop.Condition'),
               ('i.Cursor', 'item.Index'), ('change.' + side, 'mutation.Value'),
               ('change.' + side + 'Exists', 'mutation.Present'), ('mutation.ST_DenMutation', 'append.NewItem'),
               ('i.Cursor', 'next.A'), ('next.ReturnValue', 'advance.Cursor'),
               ('doc.Working', 'apply.self'), ('mutations.Edits', 'apply.Mutations'),
               ('apply.Accepted', 'accepted.Condition'), ('last.ReturnValue', 'pop.IndexToRemove'),
               ('cached.CachedStep', 'push.NewItem'), ('fields.' + side + 'Version', 'version.Version'),
               ('okout.DidSucceed', 'result.Succeeded'), ('cached.CachedStep', 'result.Step'))
        if redo:
            g.node('redonestep', 'make_struct', struct=step, defaults={'Time': '-1'})
            # Redo must not coalesce with a later wheel adjustment.
            g.links.remove(['cached.CachedStep', 'push.NewItem'])
            for field in ['Label', 'MergeKey', 'BeforeVersion', 'AfterVersion', 'Changes']:
                g.wire(('fields.' + field, 'redonestep.' + field))
            g.wire(('redonestep.ST_DenStep', 'push.NewItem'))
            g.wire(('count.ReturnValue', 'within.B'))
        else:
            g.wire(('lastchange.ReturnValue', 'startindex.Cursor'))
        g.chain('guard', 'has', 'cache', 'startindex', 'loop', 'append', 'advance', 'loop')
        g.chain('has.else', 'result')
        g.chain('loop.else', 'apply', 'accepted', 'pop', 'push', 'version', 'ok', 'result')
        g.chain('accepted.else', 'result')
        return g.function(name, outputs=[v('Succeeded', 'bool'), v('Step', 'struct:' + step)],
                          locals=[v('CachedStep', 'struct:' + step), v('Cursor', 'int', '0'),
                                  v('Edits', 'struct:' + mutation + '[]'), v('DidSucceed', 'bool', 'false')])

    dirty = Graph()
    dirty.get('version', 'Version')
    dirty.get('saved', 'SavedVersion')
    dirty.call('different', KML + ':NotEqual_IntInt')
    dirty.wire(('version.Version', 'different.A'), ('saved.SavedVersion', 'different.B'), ('different.ReturnValue', 'result.Dirty'))
    dirty.chain('entry', 'result')
    saved = Graph()
    saved.get('version', 'Version')
    saved.set('saved', 'SavedVersion')
    saved.wire(('version.Version', 'saved.SavedVersion'))
    saved.chain('entry', 'saved')
    return dict(kind='blueprint', path=root + 'BP_DenHistory', parent='/Script/CoreUObject.Object',
                variables=[v('Working', 'object:' + layout), v('UndoSteps', 'struct:' + step + '[]'),
                           v('RedoSteps', 'struct:' + step + '[]'), v('Version', 'int', '0'),
                           v('SavedVersion', 'int', '0'), v('NextVersion', 'int', '0')],
                functions=[initialize(), merge_candidate(), commit(), travel(), travel(True),
                           dirty.function('IsDirty', outputs=[v('Dirty', 'bool')]), saved.function('MarkSaved')])
