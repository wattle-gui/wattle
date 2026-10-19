#!/usr/bin/env python3
# wattle.py -- the Wattle command for Windows (Linux has the shell script `wattle`, which does the same).
# Type  wattle help  in the "Wattle Command Prompt" to see what it can do.
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CALLER = os.getcwd()                     # the folder you typed the command in: your own files are looked for there first
os.chdir(HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))

import wattle_port                       # noqa: E402

PY = sys.executable
FIRMWARE = "ESP32_GENERIC-20241025-v1.24.0.bin"

HELP = """Wattle -- usage:  wattle <command>

  install [--yes]    guided installation: find the board, put Wattle and the demo on it
  new NAME           make a starter app in the folder NAME (a label and a button)
  deploy NAME        copy the app NAME (a folder, or a design NAME.json with its script NAME.py) to the board, check it, and start it
  deploy DESIGN.json SCRIPT.py     the same for two files with any names
  check              check the design and script that are on the board; explains mistakes
  test N             load test number N (a ready-made example) onto the board
  reset              restart the board
  editor             start the Wattle Editor
  wifi               put your Wi-Fi name and password on the board (file wifi.dat; nothing is kept on the computer)
  fonts / images / pick    the font converter, picture converter and hardware picker
  remove             start again: empty the board (asks first)

Examples:   wattle install     wattle new hello     wattle deploy hello
"""


def say(text):
    print("\n" + text)


def fail(text):
    print("  STOP: " + text)
    sys.exit(1)


def ask(question, default="y"):
    if YES:
        return default == "y"
    a = input("  %s [%s] " % (question, "Y/n" if default == "y" else "y/N")).strip().lower()
    return default == "y" if not a else a.startswith("y")


def run_tool(script, *args, env=None):
    e = dict(os.environ, **(env or {}))
    e.setdefault("PYTHONUTF8", "1")
    return subprocess.call([PY, os.path.join(HERE, script), *args], env=e)


def mp(*args, timeout=40):
    return subprocess.run(wattle_port.MPREMOTE + ["connect", PORT, *args], capture_output=True, text=True, timeout=timeout)


# ---------------------------------------------------------------- deploy: which two files do you mean?

def resolve_deploy(args):
    """Names that exist in the folder you typed the command in mean those files."""
    out = []
    for f in args:
        if not f.startswith("--") and not os.path.isabs(f):
            for c in (f, f + ".json"):
                if os.path.exists(os.path.join(CALLER, c)):
                    f = os.path.join(CALLER, f)
                    break
        out.append(f)
    return out


def pick_files(names):
    """One name (a folder, or a design with or without .json) -> (design, script). Two names -> as given."""
    if len(names) == 2:
        return names
    if len(names) != 1:
        fail("usage:  wattle deploy NAME     or     wattle deploy DESIGN.json SCRIPT.py")
    one = names[0]
    if os.path.isdir(one):
        designs = sorted(glob.glob(os.path.join(one, "*.json")))
        if not designs:
            fail("The folder %s holds no design (.json file)." % one)
        if len(designs) > 1:
            fail("The folder %s holds %d designs. Name the one you want, for example:  wattle deploy %s  "
                 "(NAME is the design's name without .json)." % (one, len(designs), os.path.join(one, "NAME")))
        design = designs[0]
    else:
        design = one if os.path.isfile(one) else one + ".json"
        if not os.path.isfile(design):
            fail("I cannot find '%s' (a design, or a folder that holds one).\n  Give the full path, for example:  "
                 "wattle deploy C:\\Users\\you\\Documents\\dad" % one)
    base = design[:-5] if design.lower().endswith(".json") else design
    folder = os.path.dirname(design) or "."
    if os.path.isfile(base + ".py"):
        return design, base + ".py"
    if os.path.isfile(os.path.join(folder, "Project_1.py")):
        return design, os.path.join(folder, "Project_1.py")
    scripts = sorted(glob.glob(os.path.join(folder, "*.py")))
    if len(scripts) == 1:
        return design, scripts[0]
    name = os.path.basename(base)
    if not scripts:
        fail("There is no script next to %s. Save your script (a .py file) in the same folder." % os.path.basename(design))
    fail("There are %d scripts next to %s, and none is named %s.py. Give the one you want the design's name, or name "
         "both files:  wattle deploy %s C:\\path\\to\\script.py" % (len(scripts), os.path.basename(design), name, design))


def cmd_deploy(args):
    options = [a for a in args if a.startswith("--")]
    names = [a for a in resolve_deploy(args) if not a.startswith("--")]
    design, script = pick_files(names)
    return run_tool(os.path.join("tools", "deploy.py"), design, script, *options)


def cmd_new(args):
    if not args:
        fail("Give the app a name:  wattle new myapp")
    name = args[0]
    if os.path.exists(name):
        fail("'%s' already exists; choose another name." % name)
    os.mkdir(name)
    shutil.copy(os.path.join("tests", "00.json"), os.path.join(name, name + ".json"))
    shutil.copy(os.path.join("tests", "00.py"), os.path.join(name, name + ".py"))
    print("Created %s\\ with %s.json (the design) and %s.py (the script)." % (name, name, name))
    print("Put it on the board:   wattle deploy " + name)
    return 0


def cmd_editor(args):
    exe = os.path.join(os.path.dirname(PY), "pythonw.exe")
    exe = exe if os.path.exists(exe) else PY
    flags = 0x00000008 | 0x00000200 if sys.platform.startswith("win") else 0      # DETACHED_PROCESS | NEW_PROCESS_GROUP
    subprocess.Popen([exe, os.path.join(HERE, "Editor", "ESP32_Editor.py"), *args], cwd=os.path.join(HERE, "Editor"),
                     creationflags=flags)
    return 0


def cmd_reset(args):
    import boardlink
    boardlink.restart()
    print("The board has been restarted.")
    return 0


# ---------------------------------------------------------------- install: the board part

YES = False
PORT = wattle_port.PORT


def find_port():
    env = os.environ.get("ESP_PORT")
    if env:
        print("  (using ESP_PORT=%s)" % env)
        return env
    ports = wattle_port.candidates()
    if not ports:
        fail("no board found. Plug the board into a USB socket of this computer. Many USB cables only charge: if nothing is "
             "found, try another cable. Windows should show the board as a COM port (Device Manager, Ports). If it does "
             "not, the board's USB driver is missing: see the manual, chapter Just in Case.\n  Then run  wattle install  again.")
    if len(ports) == 1:
        print("  OK  found " + ports[0])
        return ports[0]
    print("  Several boards are connected. Please unplug the ones you do not want to change.")
    for i, p in enumerate(ports, 1):
        print("  %d   %s" % (i, p))
    if YES:
        fail("several boards are connected; with --yes I will not guess. Set ESP_PORT=COM5 (use the right port) and run again.")
    while True:                          # no default: a wrong board must never be chosen by pressing Enter
        k = input("  Which one is the board? Type its number (1 to %d) and press Enter: " % len(ports)).strip()
        if k.isdigit() and 1 <= int(k) <= len(ports):
            return ports[int(k) - 1]
        print("  Please type a number from the list.")


def micropython_version():
    try:
        r = mp("exec", "import sys; print(sys.version)", timeout=30)
        if r.returncode == 0 and "MicroPython" in r.stdout:
            return r.stdout.strip()
    except subprocess.TimeoutExpired:
        pass
    return ""


def cmd_install(args):
    global YES, PORT
    YES = "--yes" in args
    check = "--check" in args
    demo = "--no-demo" not in args
    say("1. The board's USB port")
    PORT = find_port()
    if wattle_port.in_use(PORT):
        fail("another program is using %s (Thonny? a serial monitor?). Close it, then run  wattle install  again." % PORT)
    if not check:
        with open(os.path.join(HERE, "wattle.port"), "w") as f:
            f.write(PORT + "\n")
    os.environ["ESP_PORT"] = PORT

    say("2. MicroPython on the board")
    ver = micropython_version()
    if not ver:
        import boardlink
        boardlink.PORT = PORT
        try:
            boardlink.halt()             # a running program may block mpremote: stop it and try once more
        except Exception:
            pass
        ver = micropython_version()
    if ver:
        print("  OK  " + " ".join(ver.split())[:70])
        if "v1.24" not in ver:
            print("  !!  Wattle was built and tested with MicroPython 1.24; this is a different version (it may still work).")
    else:
        print("  !!  MicroPython does not answer: the board is blank, or has something else on it.")
        if check:
            return 0
        print("  MicroPython can be installed now. This ERASES everything on the board.")
        if not ask("Install MicroPython 1.24.0 on the board?", "n"):
            fail("Wattle needs MicroPython on the board.")
        fw = os.path.join(HERE, FIRMWARE)
        if not os.path.exists(fw):
            if not ask("Download %s (about 1.6 MB) from micropython.org?" % FIRMWARE, "y"):
                fail("download it yourself from micropython.org/download (ESP32_GENERIC) and put it in %s, then run again." % HERE)
            import urllib.request
            try:
                urllib.request.urlretrieve("https://micropython.org/resources/firmware/" + FIRMWARE, fw)
            except Exception as e:
                fail("the download failed (%s)" % e)
        if not ask("Last chance: erase the board and write %s?" % FIRMWARE, "n"):
            fail("cancelled; nothing was changed.")
        es = [PY, "-m", "esptool", "--chip", "esp32", "--port", PORT]
        if subprocess.call(es + ["erase_flash"]) or subprocess.call(es + ["--baud", "460800", "write_flash", "-z", "0x1000", fw]):
            fail("writing the firmware failed. Press the board's BOOT button while it starts, or try another cable, then run again.")
        print("  OK  MicroPython written.\n  Waiting for the board to restart ...")
        import time
        for _ in range(8):
            time.sleep(3)
            ver = micropython_version()
            if ver:
                break
        if not ver:
            fail("the board does not answer yet. Unplug it, plug it in again, wait 5 seconds and run this again.")
        print("  OK  MicroPython is running on the board.")
    if check:
        say("Check finished: nothing was changed.")
        return 0

    say("3. Copying the Wattle files to the board")
    if run_tool(os.path.join("tools", "install_board.py"), env={"WATTLE_FROM_INSTALLER": "1"}):
        fail("copying failed. Read the message above, then run  wattle install  again.")

    demo_ok = True
    if demo:
        say("4. The demo")
        print("  Loading the demo onto the board: please wait ...")
        demo_ok = run_tool(os.path.join("tools", "deploy.py"), os.path.join("hello_demo", "hello.json"),
                           os.path.join("hello_demo", "demo.py"), "--as", "demo") == 0
        print("  OK  The demo is on the board." if demo_ok else "  !!  the demo could not be loaded (the files are on the board).")

    say("ALL DONE")
    if demo_ok:
        print("  Wattle is installed and the demo is running on the board's screen.")
    else:
        print("  Wattle is installed, but the demo could not be loaded (see the message above).")
    return 0


# ---------------------------------------------------------------- the rest

def main(argv):
    if not argv or argv[0] in ("help", "-h", "--help"):
        print(HELP)
        return 0
    cmd, rest = argv[0], argv[1:]
    simple = {"check": ("tools", "check_script.py"), "fonts": ("tools", "make_fonts.py"), "images": ("tools", "make_images.py"),
              "pick": ("tools", "picker.py"), "test": ("tests", "run_test.py"), "wifi": ("wifi_setup.py",),
              "remove": ("tools", "remove_wattle.py")}
    if cmd == "install":
        return cmd_install(rest)
    if cmd == "new":
        return cmd_new(rest)
    if cmd == "deploy":
        return cmd_deploy(rest)
    if cmd == "editor":
        return cmd_editor(rest)
    if cmd == "reset":
        return cmd_reset(rest)
    if cmd in simple:
        return run_tool(os.path.join(*simple[cmd]), *rest)
    print("Unknown command '%s'. Type  wattle help" % cmd)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(1)
