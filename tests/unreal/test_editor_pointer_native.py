"""Entry cursor state and its one-frame retry; headless tests do not assert OS cursor rendering."""


def run(unreal, host, controller, bus, get, set_, check):
    set_(host,'InputBus',bus)
    set_(host,'EditorController',controller)
    set_(host,'UIOpen',True)
    set_(controller,'bShowMouseCursor',False)
    host.call_method('FinishEditorEntry')
    scheduled=get(host,'PointerRestoreFrame')
    check(get(controller,'bShowMouseCursor') and scheduled>unreal.SystemLibrary.get_frame_count(),
          'finishing editor entry restores the cursor after the HUD change and schedules a later-frame retry')

    # Mount and host tick can both occur during one engine frame. Do not consume the retry that early.
    set_(controller,'bShowMouseCursor',False)
    host.call_method('PollEditorPointer')
    check(not get(controller,'bShowMouseCursor') and get(host,'PointerRestoreFrame')==scheduled,
          'same-frame tick preserves the pending cursor restore')
    set_(host,'PointerRestoreFrame',0)
    host.call_method('PollEditorPointer')
    check(get(controller,'bShowMouseCursor') and get(host,'PointerRestoreFrame')==-1,
          'later-frame cursor restore needs no click and consumes its request')
    set_(controller,'bShowMouseCursor',False)
    host.call_method('PollEditorPointer')
    check(not get(controller,'bShowMouseCursor'), 'completed entry repair does not keep overriding cursor state')

    set_(host,'Looking',True);set_(host,'PointerRestoreFrame',0)
    host.call_method('PollEditorPointer')
    check(not get(controller,'bShowMouseCursor') and get(host,'Looking') and get(host,'PointerRestoreFrame')==-1,
          'entry retry respects held camera-look and does not reopen the pointer')
    set_(host,'Looking',False)
    set_(host,'UIOpen',False);set_(host,'PointerRestoreFrame',0)
    host.call_method('PollEditorPointer')
    check(not get(controller,'bShowMouseCursor') and get(host,'PointerRestoreFrame')==-1,
          'closing before the retry cancels it without changing the game cursor')

    set_(host,'UIOpen',True);set_(host,'InputBus',None)
    host.call_method('RestoreEditorPointer')
    check(not get(controller,'bShowMouseCursor'),'cursor repair safely skips an unavailable input bus')
    set_(host,'InputBus',bus);set_(host,'EditorController',None);set_(host,'PointerRestoreFrame',0)
    host.call_method('PollEditorPointer')
    check(get(host,'PointerRestoreFrame')==-1,'missing controller safely consumes the one-shot cursor repair')

    set_(host,'EditorController',controller);set_(host,'PointerRestoreFrame',0)
    host.call_method('DetachEditor',(False,))
    check(not get(host,'UIOpen') and get(host,'PointerRestoreFrame')==-1,
          'editor teardown clears its deferred cursor request')
