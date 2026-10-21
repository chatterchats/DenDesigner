"""Exercise native drag transactions in the Blueprint VM, without pointer mocks."""
def run(unreal, host, actor, facts, get, field, check, settle, command):
    from runtime_pick import FACT
    from runtime_transform import ENTRY_FIELDS
    comp=actor.get_component_by_class(unreal.StaticMeshComponent)
    host.call_method('AcceptSelection',(facts,))
    history=get(host,'History');doc=get(host,'WorkingDocument')
    baseline=actor.get_actor_transform()
    mobility=comp.get_editor_property('mobility')
    version=get(history,'Version');count=len(get(history,'UndoSteps'))
    def snapshot():
        result=[]
        for row in get(doc,'Entries'):
            values=[]
            for name in ENTRY_FIELDS:
                value=field(row,name)
                if name in ['Position','Scale','FingerprintPosition']:value=(value.x,value.y,value.z)
                elif name=='Rotation':value=(value.pitch,value.yaw,value.roll)
                elif name=='Materials':value=tuple(value)
                values.append(value)
            result.append(tuple(values))
        return result
    entries=snapshot()
    draft_pending=get(host,'DraftPending')
    start=comp.get_world_location();rot=comp.get_world_rotation();scale=comp.get_world_scale()
    def preview(position=start,rotation=rot,size=scale):
        return host.call_method('PreviewSelectionDrag',(position,rotation,size))
    def begin(mode):return host.call_method('BeginSelectionDrag',(mode,))
    def finish(commit):return host.call_method('EndSelectionDrag',(commit,))
    def check_baseline(label):
        check(actor.get_actor_transform()==baseline and comp.get_editor_property('mobility')==mobility,label)
    def undo():
        command('undo');settle()
    moved=unreal.Vector(start.x+17.25,start.y-3.5,start.z+9.75)

    check(not begin(0) and not begin(4),'drag rejects unsupported modes')
    check(begin(1) and not begin(2),'a drag captures one selection and cannot nest')
    check(not finish(True) and get(history,'Version')==version,'click without a drag makes no history')
    check_baseline('unchanged release preserves exact pose and mobility')
    check(begin(1) and preview(moved),'native move preview updates live geometry')
    check(comp.get_world_location()==moved and not get(host,'Busy') and get(history,'Version')==version
          and snapshot()==entries and get(host,'DraftPending')==draft_pending,
          'preview changes neither document, history, draft schedule nor world queue')
    host.call_method('SetSelectionField',('X',str(start.x+200)))
    check(comp.get_world_location()==moved and get(history,'Version')==version,
          'numeric edits cannot use an uncommitted preview as their baseline')
    check(not preview(unreal.Vector(float('nan'),0,0)) and comp.get_world_location()==moved,
          'invalid preview leaves the last valid pose intact')
    command('back')
    check(not get(host,'DragActive') and get(host,'HasSelection') and get(host,'Editing'),
          'Escape cancels drag while retaining selection and editor')
    check_baseline('Escape restores exact original pose and mobility')
    check(get(history,'Version')==version and snapshot()==entries,
          'cancel leaves layout and undo history untouched')

    check(begin(1) and preview(moved) and preview(start),'drag can return to its exact starting pose')
    check(not finish(True) and len(get(history,'UndoSteps'))==count,'returning to start creates no undo step')
    check_baseline('returning to start also restores original mobility')

    check(begin(1),'begin move transaction')
    accepted=[preview(unreal.Vector(start.x+step,start.y,start.z)) for step in range(1,21)]
    check(all(accepted),'all intermediate move previews are accepted')
    check(finish(True) and not get(host,'DragActive'),'release commits native move transaction')
    if field(facts,'Kind',FACT)==2:
        host.call_method('CancelWork')
        host.call_method('Clear')
        check_baseline('teardown before the first queued frame restores the released preview')
        host.call_method('BeginLayout',(doc,))
    settle()
    check(len(get(history,'UndoSteps'))==count+1 and abs(comp.get_world_location().x-start.x-20)<1e-6,
          'twenty preview updates become exactly one committed undo step')
    entry=next(row for row in get(doc,'Entries') if field(row,'Key')==field(facts,'Key',FACT))
    if field(facts,'Kind',FACT)==2:
        check(field(entry,'HasPosition') and not field(entry,'HasRotation') and not field(entry,'HasScale'),
              'moving untouched vanilla adds only a position override')
    undo();check_baseline('one Undo restores the complete pre-drag state')
    command('redo');settle()
    check(abs(comp.get_world_location().x-start.x-20)<1e-6,'Redo restores the committed drag pose')
    undo()

    check(begin(2) and preview(rotation=unreal.Rotator(pitch=rot.pitch,yaw=rot.yaw+15,roll=rot.roll)),
          'rotation preview uses the same transaction')
    check(finish(True),'rotation release commits');settle()
    check(comp.get_world_location()==start and comp.get_world_scale()==scale,'rotation preserves position and nonuniform scale')
    undo();check_baseline('rotation Undo restores exact pose')
    check(begin(3) and preview(size=unreal.Vector(scale.x*1.2,scale.y*1.2,scale.z)),
          'scale preview supports a two-axis change')
    check(finish(True),'scale release commits');settle()
    check(abs(comp.get_world_scale().x-scale.x*1.2)<1e-6 and comp.get_world_scale().z==scale.z,
          'scale transaction preserves the excluded axis')
    undo();check_baseline('scale Undo restores exact pose')

    check(begin(1) and preview(moved),'begin preview before selection replacement')
    host.call_method('AcceptSelection',(facts,))
    check(not get(host,'DragActive'),'selection replacement cancels the old transaction')
    check_baseline('selection replacement restores captured geometry')

    check(begin(1) and preview(moved),'begin preview before queued command')
    command('rotate',1)
    host.call_method('PumpEditorMutations')
    check(len(get(host,'EditEvents'))==1 and get(host,'DragActive') and get(history,'Version')==version,
          'queued edits wait for drag completion')
    finish(False);settle()
    check(len(get(host,'EditEvents'))==0 and len(get(history,'UndoSteps'))==count+1,
          'queued edit runs after drag cancellation')
    undo();check_baseline('queued edit Undo returns to the pre-drag state')

    # A direct external history operation invalidates the captured generation.
    # The transaction must not restore stale geometry over the newly applied edit.
    check(begin(1) and preview(moved),'begin preview before external history change')
    host.call_method('RedoEdit');settle()
    authoritative=actor.get_actor_transform()
    host.call_method('PollSelectionDrag')
    check(not get(host,'DragActive') and actor.get_actor_transform()==authoritative,
          'stale drag cancellation does not overwrite a newer history operation')
    undo();check_baseline('external edit can still undo to original pose')
    check(snapshot()==entries,'all drag tests leave original layout entries intact')
