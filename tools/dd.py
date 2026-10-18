#!/usr/bin/env python3
"""Den Designer dev driver: run the main game install for in-game tests without anyone at the keyboard.

    tools/dd.py status                 is the game up; the sandbox session line
    tools/dd.py kill                   force-close the game (waits until it's gone)
    tools/dd.py launch                 start it through Lutris (game id 2, the main install)
    tools/dd.py den [--save newest]    wait for the main menu, load the sandbox campaign's Den, wait until settled
    tools/dd.py restart                kill + launch + den
    tools/dd.py send "<sandbox command>"   one ZC Sandbox command (cmd.txt / reply.txt)
    tools/dd.py lua "<code>" | -f file     Lua in the game (PlagueNightConsole, through ZComPlagueNight/tools/pn.py)
    tools/dd.py con "<console line>"       an Unreal console command, e.g. "zcomden open"
    tools/dd.py shot [out.jpg]             the game's monitor (right half of the desktop), 1280 px wide
    tools/dd.py log [n]                    the last n lines of Den Designer's log

The sandbox campaign is the throwaway one (BA3302BC...); ZC Sandbox refuses changes anywhere else.
"""
import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODS = REPO.parent
GAME = Path("/run/media/chats/e0057d4a-fe46-43eb-a837-db51979c500f/Games/STAR WARS Zero Company (2026)")
UE4SS = GAME / "Star Wars Zero Company/SWZeroCompany/Binaries/Win64/ue4ss"
SANDBOX = UE4SS / "Mods/ZCSandbox"
LOG = REPO / "src/ZComDen/zcom_den.log"
PN = MODS / "ZComPlagueNight/tools/pn.py"
LUTRIS_ID = 2


def game_pids():
    out = subprocess.run(["pgrep", "-af", "SWZeroCompany.exe"], capture_output=True, text=True).stdout
    return [int(l.split()[0]) for l in out.splitlines()
            if "Win64\\SWZeroCompany.exe" in l and "pgrep" not in l and "bash" not in l]


def hello():
    try:
        first = (SANDBOX / "reply.txt").read_text(errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return ""
    return first if first.startswith("hello") else ""


def send(line, timeout=60):
    """Appends one sandbox command with a fresh id and waits for its answer line."""
    ident = "dd%d" % int(time.time() * 1000)
    reply = SANDBOX / "reply.txt"
    # One command per write, replacing the file: under Proton the sandbox sees every write as a replaced file
    # and reads it from the top, so anything left in it would run again (a stale `campaign load` reloaded the
    # Den mid-load and crashed the game, 2026-10-18).
    with open(SANDBOX / "cmd.txt", "w") as f:
        f.write("#%s %s\n" % (ident, line))
    end = time.time() + timeout
    while time.time() < end:
        try:
            for l in reply.read_text(errors="replace").splitlines():
                if l.startswith(ident + " "):
                    return l
        except OSError:
            pass
        time.sleep(0.5)
    return None


def kill():
    pids = game_pids()
    for pid in pids:
        subprocess.run(["kill", str(pid)])
    end = time.time() + 30
    while game_pids() and time.time() < end:
        time.sleep(1)
    for pid in game_pids():
        subprocess.run(["kill", "-9", str(pid)])
    time.sleep(3)
    print("killed" if pids else "not running")


def launch():
    if game_pids():
        print("already running")
        return
    # The new session writes a fresh reply.txt; an old one would look like a session that's already up.
    try:
        (SANDBOX / "reply.txt").unlink()
    except OSError:
        pass
    subprocess.Popen(["lutris", "lutris:rungameid/%d" % LUTRIS_ID], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    print("launching")


def den(save="newest", timeout=400):
    """Waits for a fresh sandbox session at the main menu, then loads the sandbox Den."""
    started = time.time()
    while time.time() - started < timeout:
        if game_pids() and hello():
            break
        time.sleep(2)
    else:
        sys.exit("no sandbox session after %d s" % timeout)
    print(hello()[:120])
    time.sleep(5)  # let the title screen settle
    print(send("campaign load %s" % save, timeout=300))
    print(send("wait phase=hub settled=1 timeout=240000", timeout=260))


def shot(out):
    full = REPO / "dist/shot-full.png"
    subprocess.run(["spectacle", "-b", "-n", "-f", "-o", str(full)], check=True)
    from PIL import Image
    im = Image.open(full).convert("RGB")
    w, h = im.size
    if w >= 2 * h:  # two monitors side by side: the game is on the right one
        im = im.crop((w // 2, 0, w, h))
    im.thumbnail((1280, 1280))
    im.save(out, quality=85)
    full.unlink()
    print(out)


def lua(code=None, file=None):
    args = [sys.executable, str(PN), "--instance", "1", "--timeout", "60"]
    args += ["-f", file] if file else [code]
    r = subprocess.run(args, capture_output=True, text=True)
    sys.stdout.write(r.stdout + r.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd")
    ap.add_argument("rest", nargs="*")
    ap.add_argument("-f", "--file")
    ap.add_argument("--save", default="newest")
    a = ap.parse_args()
    if a.cmd == "status":
        print("running pids:", game_pids() or "none")
        print(hello() or "no sandbox session line")
    elif a.cmd == "kill":
        kill()
    elif a.cmd == "launch":
        launch()
    elif a.cmd == "den":
        den(a.save)
    elif a.cmd == "restart":
        kill()
        launch()
        den(a.save)
    elif a.cmd == "send":
        print(send(" ".join(a.rest)))
    elif a.cmd == "lua":
        lua(" ".join(a.rest), a.file)
    elif a.cmd == "con":
        line = " ".join(a.rest).replace("\\", "\\\\").replace("'", "\\'")
        lua("print(S and S.g and S.g.console(S.g.any_context(), '%s') or "
            "StaticFindObject('/Script/Engine.Default__KismetSystemLibrary'):ExecuteConsoleCommand("
            "FindFirstOf('BrunoGameInstance'), '%s', nil))" % (line, line))
    elif a.cmd == "shot":
        shot(a.rest[0] if a.rest else str(REPO / "dist/screen.jpg"))
    elif a.cmd == "log":
        n = int(a.rest[0]) if a.rest else 20
        print("\n".join(LOG.read_text(errors="replace").splitlines()[-n:]))
    else:
        sys.exit("unknown command " + a.cmd)


if __name__ == "__main__":
    main()
