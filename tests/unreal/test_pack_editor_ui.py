"""Maintainer UI check in an isolated graphical editor after test_pack_editor.py.

Runs through Slate ticks and closes automatically; changes form state only, not saved metadata.
"""
import unreal as u
import den_pack_editor
from den_pack_editor import panel as impl
from concurrent.futures import Future
import time,traceback
u.EditorPythonScripting.set_keep_python_script_alive(True)
p=den_pack_editor.open_panel()
p.packs.set_selected_option('DenPythonTest');p.open_pack()
assert p.rows
p.fields['title'].set_text('Python authoring · live panel')
f=Future();p.future=f;p.job={'output':'/tmp'};p.busy(True)
p.tick=u.register_slate_post_tick_callback(p.poll_build)
bp=u.load_asset('/DenPropPackEditor/UI/EUW_PropPacks')
sub=u.get_editor_subsystem(u.EditorUtilitySubsystem)
_,tab=sub.spawn_and_register_tab_and_get_id(bp)
assert sub.close_tab_by_id(tab)
start=time.monotonic();state=0

def tick(delta):
 global state
 try:
  if state==0 and time.monotonic()-start>2:
   q=den_pack_editor.open_panel()
   assert q is not p and q.future is f
   assert q.packs.get_selected_option()=='DenPythonTest'
   assert str(q.fields['title'].get_text())=='Python authoring · live panel'
   f.set_result('/tmp');state=1
  elif state==1 and time.monotonic()-start>4:
   assert impl._current.output=='/tmp'
   assert impl._current.future is None
   impl._current.message('UI verified: tab reopened, edits retained, build completion delivered.')
   u.log('DENPACK_PYTHON_UI ok');state=2
  elif state==2 and time.monotonic()-start>25:
   u.unregister_slate_post_tick_callback(handle)
   u.EditorPythonScripting.set_keep_python_script_alive(False)
 except Exception:
  u.log_error(traceback.format_exc());u.unregister_slate_post_tick_callback(handle)
  u.EditorPythonScripting.set_keep_python_script_alive(False)
handle=u.register_slate_post_tick_callback(tick)
