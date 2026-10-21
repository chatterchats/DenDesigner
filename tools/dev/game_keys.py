#!/usr/bin/env python3
"""Development-only X11 input, guarded by the running game window's focus.

This exercises Wine/Slate/player input, unlike invoking Blueprint event handlers.
It is never included in the pak. No desktop pixels or unrelated windows are read.
Use --click X Y for a left click in game-client coordinates.
Use --drag X1 Y1 X2 Y2 for a continuous drag; --button 3 tests RMB look.
"""
import argparse
import ctypes as C
import ctypes.util
import subprocess
import time
import dd


def send(keys,hold=.12,click=None,drag=None,button=1,settle=2):
    if not 0<hold<=2:raise ValueError('hold must be between 0 and 2 seconds')
    if not 0<=settle<=5:raise ValueError('settle must be between 0 and 5 seconds')
    if button not in (1,3):raise ValueError('Only left/right buttons are supported')
    if click is not None and drag is not None:raise ValueError('Choose click or drag')
    if drag is not None:click=drag[:2]
    window=dd.game_window();target=int(window,16)
    x=C.CDLL(ctypes.util.find_library('X11'));xt=C.CDLL(ctypes.util.find_library('Xtst'))
    dpy=C.c_void_p;ulong=C.c_ulong
    x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=dpy
    x.XCloseDisplay.argtypes=[dpy]
    x.XGetInputFocus.argtypes=[dpy,C.POINTER(ulong),C.POINTER(C.c_int)]
    x.XQueryTree.argtypes=[dpy,ulong,C.POINTER(ulong),C.POINTER(ulong),C.POINTER(C.POINTER(ulong)),C.POINTER(C.c_uint)]
    x.XFree.argtypes=[C.c_void_p]
    x.XStringToKeysym.argtypes=[C.c_char_p];x.XStringToKeysym.restype=ulong
    x.XKeysymToKeycode.argtypes=[dpy,ulong];x.XKeysymToKeycode.restype=C.c_ubyte
    x.XFlush.argtypes=[dpy]
    x.XDefaultRootWindow.argtypes=[dpy];x.XDefaultRootWindow.restype=ulong
    x.XGetGeometry.argtypes=[dpy,ulong,C.POINTER(ulong),C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(C.c_uint),C.POINTER(C.c_uint),C.POINTER(C.c_uint),C.POINTER(C.c_uint)]
    x.XTranslateCoordinates.argtypes=[dpy,ulong,ulong,C.c_int,C.c_int,C.POINTER(C.c_int),C.POINTER(C.c_int),C.POINTER(ulong)]
    xt.XTestFakeKeyEvent.argtypes=[dpy,C.c_uint,C.c_int,ulong];xt.XTestFakeKeyEvent.restype=C.c_int
    xt.XTestFakeMotionEvent.argtypes=[dpy,C.c_int,C.c_int,C.c_int,ulong];xt.XTestFakeMotionEvent.restype=C.c_int
    xt.XTestFakeRelativeMotionEvent.argtypes=[dpy,C.c_int,C.c_int,ulong];xt.XTestFakeRelativeMotionEvent.restype=C.c_int
    xt.XTestFakeButtonEvent.argtypes=[dpy,C.c_uint,C.c_int,ulong];xt.XTestFakeButtonEvent.restype=C.c_int
    display=x.XOpenDisplay(None)
    if not display:raise RuntimeError('No X11 display')
    pressed=[];button_down=False
    try:
        codes=[]
        for key in keys:
            symbol=x.XStringToKeysym(key.encode('ascii'));code=x.XKeysymToKeycode(display,symbol)
            if not symbol or not code:raise ValueError('Unsupported key: '+key)
            codes.append(code)
        # X11 focus can arrive before Wine/the game resumes input processing.
        # Allow the game to settle after activation before a short key pulse.
        subprocess.run(['wmctrl','-ia',window],check=True);time.sleep(settle)
        # Revalidate the PID/title and focus after activation. Never send a key
        # to an arbitrary active app if the game closed or failed to activate.
        if dd.game_window()!=window:raise RuntimeError('Game window changed')
        def check_focus():
            focused=ulong();revert=C.c_int();x.XGetInputFocus(display,C.byref(focused),C.byref(revert))
            current=focused.value
            for _ in range(20):
                if current==target:return
                root,parent=ulong(),ulong();children=C.POINTER(ulong)();count=C.c_uint()
                if current<=1 or not x.XQueryTree(display,current,C.byref(root),C.byref(parent),C.byref(children),C.byref(count)):break
                if children:x.XFree(children)
                if parent.value==current:break
                current=parent.value
            raise RuntimeError('Game does not own keyboard focus; no further input sent')
        check_focus()
        if click is not None:
            root=ulong();gx,gy=C.c_int(),C.c_int();width,height,border,depth=[C.c_uint() for _ in range(4)]
            if not x.XGetGeometry(display,target,C.byref(root),C.byref(gx),C.byref(gy),C.byref(width),C.byref(height),C.byref(border),C.byref(depth)):
                raise RuntimeError('Cannot inspect game window geometry')
            px,py=click
            if not (0<=px<width.value and 0<=py<height.value):raise ValueError('Click is outside the game window')
            if drag is not None and not (0<=drag[2]<width.value and 0<=drag[3]<height.value):
                raise ValueError('Drag endpoint is outside the game window')
            sx,sy=C.c_int(),C.c_int();child=ulong()
            if not x.XTranslateCoordinates(display,target,x.XDefaultRootWindow(display),px,py,C.byref(sx),C.byref(sy),C.byref(child)):
                raise RuntimeError('Cannot translate game coordinates')
            if not xt.XTestFakeMotionEvent(display,-1,sx.value,sy.value,0):raise RuntimeError('Mouse move failed')
            x.XFlush(display);time.sleep(.3)
            check_focus()
        for code in codes:
            if not xt.XTestFakeKeyEvent(display,code,1,0):raise RuntimeError('Key down failed')
            pressed.append(code);x.XFlush(display);time.sleep(.04)
        if click is not None:
            if not xt.XTestFakeButtonEvent(display,button,1,0):raise RuntimeError('Mouse down failed')
            button_down=True;x.XFlush(display)
        if drag is None:
            deadline=time.monotonic()+hold
            while time.monotonic()<deadline:
                time.sleep(min(.04,max(0,deadline-time.monotonic())))
                check_focus()
        else:
            steps=max(2,round(hold*60))
            prior_dx=prior_dy=0
            for step in range(1,steps+1):
                time.sleep(hold/steps);check_focus()
                dx=round((drag[2]-px)*step/steps)
                dy=round((drag[3]-py)*step/steps)
                # RMB look captures/recentres the cursor. Absolute destinations
                # would fight that warp instead of supplying mouse deltas.
                if button==3:
                    moved=xt.XTestFakeRelativeMotionEvent(display,dx-prior_dx,dy-prior_dy,0)
                else:
                    moved=xt.XTestFakeMotionEvent(display,-1,sx.value+dx,sy.value+dy,0)
                if not moved:raise RuntimeError('Drag move failed')
                prior_dx,prior_dy=dx,dy
                x.XFlush(display)
    finally:
        if button_down:xt.XTestFakeButtonEvent(display,button,0,0)
        for code in reversed(pressed):xt.XTestFakeKeyEvent(display,code,0,0)
        x.XFlush(display);x.XCloseDisplay(display)
    print('Sent game-window input:', '+'.join(keys), 'drag '+str(drag) if drag is not None else 'click '+str(click) if click is not None else '')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('keys',nargs='*');p.add_argument('--hold',type=float,default=.12)
    mouse=p.add_mutually_exclusive_group()
    mouse.add_argument('--click',nargs=2,type=int,metavar=('X','Y'))
    mouse.add_argument('--drag',nargs=4,type=int,metavar=('X1','Y1','X2','Y2'))
    p.add_argument('--button',type=int,choices=(1,3),default=1)
    p.add_argument('--settle',type=float,default=2,help='Seconds to let game input resume after activation (default: 2)')
    a=p.parse_args()
    if not a.keys and a.click is None and a.drag is None:p.error('Supply keys, --click or --drag')
    send(a.keys,a.hold,a.click,a.drag,a.button,a.settle)
