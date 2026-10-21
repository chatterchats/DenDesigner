#!/usr/bin/env python3
"""Den Designer dev driver: run the main game install for in-game tests without anyone at the keyboard.

    tools/dev/dd.py status                 is the game up; the sandbox session line
    tools/dev/dd.py kill                   force-close the game (waits until it's gone)
    tools/dev/dd.py launch                 start it through Lutris (game id 2, the main install)
    tools/dev/dd.py den [--save newest]    wait for the main menu, load the sandbox campaign's Den, wait until settled
    tools/dev/dd.py restart                kill + launch + den
    tools/dev/dd.py send "<sandbox command>"   one ZC Sandbox command (cmd.txt / reply.txt)
    tools/dev/dd.py lua "<code>" | -f file     Lua in the game (PlagueNightConsole, through ZComPlagueNight/tools/pn.py)
    tools/dev/dd.py con "<console line>"       an Unreal console command, requires the optional development console
    tools/dev/dd.py shot [out.jpg]             capture only the game window
    tools/dev/dd.py log [n]                    the last n lines of the game log

The sandbox campaign is the throwaway one (BA3302BC...); ZC Sandbox refuses changes anywhere else.
"""
import argparse
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODS = REPO.parent
GAME = Path("/run/media/chats/e0057d4a-fe46-43eb-a837-db51979c500f/Games/STAR WARS Zero Company (2026)")
UE4SS = GAME / "Star Wars Zero Company/SWZeroCompany/Binaries/Win64/ue4ss"
SANDBOX = UE4SS / "Mods/ZCSandbox"
LOG = GAME / "prefix/drive_c/users/steamuser/AppData/Local/SWZeroCompany/Saved/Logs/SWZeroCompany.log"
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
    if save not in ("newest", "baseline"):
        sys.exit("sandbox campaign load accepts only newest or baseline")
    started = time.time()
    while time.time() - started < timeout:
        if game_pids() and hello():
            break
        time.sleep(2)
    else:
        sys.exit("no sandbox session after %d s" % timeout)
    print(hello()[:120])
    time.sleep(5)  # let the title screen settle
    reply = send("campaign load %s" % save, timeout=300)
    print(reply)
    if not reply or " err " in reply:
        sys.exit("sandbox campaign load failed")
    print(send("wait phase=hub settled=1 timeout=240000", timeout=260))


def game_window():
    """Match both the running game process and its exact main-window title."""
    pids = set(game_pids())
    windows = subprocess.check_output(["wmctrl", "-lp"], text=True)
    matches = []
    for line in windows.splitlines():
        parts = line.split(None, 4)
        if len(parts) == 5 and int(parts[2]) in pids and parts[4].strip() in (
                "STAR WARS Zero Company™", "STAR WARS Zero Company"):
            matches.append(parts[0])
    if len(matches) != 1:
        raise RuntimeError("Could not uniquely identify the game window; no desktop action taken")
    return matches[0]


def shot(out):
    # XGetImage/ImageMagick can return an old Vulkan window pixmap indefinitely.
    # Ask the compositor for the active window, with focus guards and a unique
    # output file: Spectacle may return before its asynchronous export completes.
    window = game_window()
    output = Path(out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.stem}.{uuid.uuid4().hex}{output.suffix or '.png'}")
    subprocess.run(["wmctrl", "-ia", window], check=True)
    time.sleep(1)

    def require_focus():
        active = subprocess.check_output(["xprop", "-root", "_NET_ACTIVE_WINDOW"], text=True)
        if game_window() != window or int(active.split()[-1], 16) != int(window, 16):
            raise RuntimeError("Game lost active-window focus; capture discarded")

    process = None
    try:
        require_focus()
        process = subprocess.Popen(["spectacle", "-a", "-b", "-n", "-e", "-S", "-o", str(temporary)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 15
        prior_size = None
        while time.monotonic() < deadline:
            require_focus()
            code = process.poll()
            if code not in (None, 0):
                raise RuntimeError(f"Game window capture failed ({code})")
            size = temporary.stat().st_size if temporary.exists() else 0
            if code == 0 and size > 0 and size == prior_size:
                require_focus()
                temporary.replace(output)
                break
            prior_size = size
            time.sleep(.2)
        else:
            raise RuntimeError("Game window capture did not finish exporting")
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        temporary.unlink(missing_ok=True)
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
