#!/usr/bin/env python3
# wattle.py -- the Wattle command for Windows (Linux has the shell script `wattle`, which does the same).
# Type  wattle help  in the "Wattle Command Prompt" to see what it can do.
import glob
import os
import re
import shutil
import subprocess
import time
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
  install --browser [--name NAME] [--yes]   the browser version: a phone, tablet or PC is the screen (the ESP32 needs MicroPython)
  setup [--yes]      set up a NEW plain ESP32 in one go (it writes a ready-made image; this ERASES the ESP32); the Wi-Fi is typed on your phone
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

Examples:   wattle install     wattle new myapp     wattle deploy myapp
"""


def say(text):
    print("\n" + text)


def fail(text):
    print("  STOP: " + text)
    sys.exit(1)


def drain():
    """Throw away keys pressed earlier (Windows): a left-over Enter must not answer the next question."""
    try:
        import ctypes
        h = ctypes.windll.kernel32.GetStdHandle(-10)             # standard input
        ctypes.windll.kernel32.FlushConsoleInputBuffer(h)
    except Exception:
        pass


def ask(question, default="y"):
    if YES:
        return default == "y"
    drain()
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
            for base in (CALLER, os.path.join(HERE, "projects")):      # the folder you typed the command in, then your projects folder
                hit = [c for c in (f, f + ".json") if os.path.exists(os.path.join(base, c))]
                if hit:
                    f = os.path.join(base, f)
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
            proj = os.path.join(HERE, "projects")
            extra = ""
            for d in (proj, CALLER):
                if os.path.isfile(os.path.join(d, one + ".py")):
                    extra = ("\n  I did find a script called %s.py in %s, but there is no design with the same name next to it."
                             "\n  Save your design in the Editor under the same name (File, Save As...), in that folder." % (one, d))
                    break
            fail("I cannot find the design '%s.json' in this folder or in your projects folder (%s).%s\n  Or give the full path of your design, for example:  "
                 "wattle deploy %s" % (one, proj, extra, os.path.join(proj, one)))
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
    """A new app folder with a ready-to-run starter (a label and a button that counts taps), for the screen you choose."""
    if not args or args[0].startswith("--"):
        fail("Give the app a name:  wattle new myapp")
    name = args[0]
    kind = "browser" if "--browser" in args else ("cyd" if "--cyd" in args else "")
    if os.path.exists(name):
        fail("'%s' already exists; choose another name." % name)
    if not kind:
        say("Which screen is this app for?")
        print("  1   a phone, tablet or computer (any ESP32 with Wi-Fi)")
        print("  2   the CYD board: its screen is on the board")
        while kind not in ("1", "2"):
            drain()
            kind = input("  Type 1 or 2 and press Enter: ").strip()
        kind = "browser" if kind == "1" else "cyd"
    if kind == "browser":
        src = os.path.join("browser", "examples", "hello", "hello")
    else:
        src = os.path.join("tests", "00")
    os.mkdir(name)
    shutil.copy(src + ".json", os.path.join(name, name + ".json"))
    shutil.copy(src + ".py", os.path.join(name, name + ".py"))
    print("Created %s%s with %s.json (the design) and %s.py (the script), for %s." % (name, os.sep, name, name, "a phone, tablet or computer" if kind == "browser" else "the CYD"))
    print("Put it on the ESP32:   " + ("wattle" if (os.name == "nt" or shutil.which("wattle")) else "./wattle") + " deploy " + name)
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


def flush_input():
    """Throws away anything typed while the installer was busy, so that it cannot end up in an answer."""
    try:
        if os.name == "nt":
            import msvcrt
            while msvcrt.kbhit():
                msvcrt.getwch()
        else:
            import termios
            termios.tcflush(0, termios.TCIFLUSH)
    except Exception:
        pass


def find_port():
    env = os.environ.get("ESP_PORT")
    if env:
        print("  (using ESP_PORT=%s)" % env)
        return env
    ports = wattle_port.candidates()
    while len(ports) != 1:               # exactly ONE board must be connected: wait until that is so
        if not ports:
            print("\n  No ESP32 board is connected! Please plug in the board you want to set up.")
            print("  (Many USB cables only charge: if nothing is found, try another cable. Windows should show the board as a COM port "
                  "in Device Manager, Ports. If it does not, the board's USB driver is missing: see the manual, chapter Just in Case.)")
        else:
            print("\n  You have more than one ESP32 board connected! Please remove ALL the other boards before you are able to continue!")
        if YES:
            fail("%s; with --yes I will not guess. Set ESP_PORT=COM5 (use the right port) and run again." %
                 ("no board is connected" if not ports else "more than one board is connected"))
        input("  Press Enter when exactly one board is connected (Ctrl+C to give up) ")
        time.sleep(2)
        ports = wattle_port.candidates()
    print("  OK  found " + ports[0])
    return ports[0]


def micropython_version():
    try:
        r = mp("exec", "import sys; print(sys.version)", timeout=30)
        if r.returncode == 0 and "MicroPython" in r.stdout:
            return r.stdout.strip()
    except subprocess.TimeoutExpired:
        pass
    return ""


class _Tee:
    def __init__(self, a, b):
        self.a, self.b = a, b

    def write(self, text):
        for f in (self.a, self.b):
            try:
                f.write(text)
                f.flush()
            except Exception:
                pass
        return len(text)

    def flush(self):
        pass


def no_quick_edit():
    """Windows: a click inside the console window starts 'Select' mode, which freezes the program. Switch that mode off."""
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-10)                       # standard input
        mode = ctypes.c_uint32()
        if k.GetConsoleMode(h, ctypes.byref(mode)):
            k.SetConsoleMode(h, (mode.value & ~0x0040) | 0x0080)       # no ENABLE_QUICK_EDIT_MODE, with ENABLE_EXTENDED_FLAGS
    except Exception:
        pass


def _logged(fn, args):
    """Everything the window shows is also written to setup_log.txt (a window that closes cannot be asked afterwards); a crash is written too."""
    import traceback
    import time as _t
    no_quick_edit()
    log = open(os.path.join(HERE, "setup_log.txt"), "a", encoding="utf-8")
    log.write("\n==== %s ====\n" % _t.strftime("%Y-%m-%d %H:%M:%S"))
    real = sys.stdout
    sys.stdout = _Tee(real, log)
    try:
        return fn(args)
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc(file=sys.stdout)
        raise
    finally:
        sys.stdout = real
        log.close()


def detect_ssid():
    """The name of the Wi-Fi this computer is using now (empty when it uses a cable or the system cannot tell)."""
    try:
        if os.name == "nt":
            out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=10).stdout
            m = re.search(r"^\s*SSID\s*:\s*(.+?)\s*$", out, re.M)
            return m.group(1) if m else ""
        out = subprocess.run(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"], capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            if line.startswith("yes:"):
                return line[4:]
    except Exception:
        pass
    return ""


def ask_wifi(args):
    """The Wi-Fi name and password, typed on this computer (empty name: the phone sets it up later). Returns (name, password) or (None, None)."""
    if "--ssid" in args:
        return args[args.index("--ssid") + 1], (args[args.index("--password") + 1] if "--password" in args else "")
    say("2. Your Wi-Fi: the ESP32 will join it (a Wi-Fi with 2.4 GHz)")
    guess = detect_ssid()
    while True:
        drain()
        name = input("  Wi-Fi name%s: " % (" (press Enter for %s)" % guess if guess else "")).strip() or guess
        if not name:
            return None, None
        drain()
        pw = input("  Its password (you see it as you type: check it): ")
        # The window's text is also saved in setup_log.txt, so the password is NEVER printed again: only how long it is.
        print("  You typed:  Wi-Fi name: " + name + "    password: " + "*" * len(pw) + "  (%d characters)" % len(pw))
        if ask("Is that right?"):
            return name, pw
        print("  Then type them again.")


def hard_reset():
    """Press the ESP32's reset button over the cable (a restart from inside the ESP32 does not bring its Wi-Fi back)."""
    import time
    import serial
    s = serial.Serial()
    s.port = PORT
    s.dtr = False
    s.rts = True
    s.open()
    time.sleep(0.2)
    s.rts = False
    time.sleep(0.1)
    s.close()


def dots(seconds, text=""):
    """Wait, and show a dot every second, so that nobody thinks the window has stopped."""
    import time
    if text:
        print("  " + text, end="", flush=True)
    for _ in range(int(seconds)):
        time.sleep(1)
        print(".", end="", flush=True)
    print()


REASON = ""          # why put_wifi_on_esp32 failed: "silent" (the ESP32 did not answer) or "join" (it answered, but could not join the Wi-Fi)


def ask_name(args):
    """The ESP32's own name: http://<name>.local/ . Each ESP32 on one Wi-Fi needs a different one. Enter alone gives 'wattle'."""
    if "--name" in args:
        return args[args.index("--name") + 1]
    print("  Give this ESP32 a name of its own. The name is also its address on your Wi-Fi: http://<name>.local/")
    print("  Rules for the name: letters and digits, with - or _ between them. No spaces. At most 24 characters.")
    print("  Examples:  Phone_1    Kitchen-tablet")
    while True:
        drain()
        n = input("  A name for this ESP32: ").strip().lower().replace("_", "-")
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,23}", n):         # the name becomes the address (http://<name>.local/): letters, digits and hyphens only
            print("  You typed the name: " + n + "   (its address will be http://" + n + ".local/)")
            if ask("Is that right?"):
                return n
            print("  Then type the name again.")
            continue
        print("  That name does not follow the rules (letters, digits, - and _ only, no spaces, at most 24 characters). Please try again.")


def put_wifi_on_esp32(ssid, pw, need_boot=False, name="wattle"):
    """The new ESP32 has started on the ready-made image. Let it try the Wi-Fi: only a Wi-Fi that works is saved (sealed, as wattle wifi does). Returns the address or None."""
    import time
    global REASON
    REASON = "silent"
    if need_boot:                                    # the BOOT button is still down: the ESP32 waits for a new image instead of starting
        print()
        print("  >>> LET GO OF THE BOOT BUTTON NOW. <<<")
        drain()
        input("  Then press Enter here: ")
    hard_reset()                                     # esptool's own restart can leave the chip waiting for a new image: press reset, cleanly (DTR released)
    dots(10, "Waiting for the ESP32 to start ")     # a new ESP32 needs a few quiet seconds to start; every try to talk to it may restart it
    ok = False
    print("  Asking the ESP32 to answer ", end="", flush=True)
    for _ in range(20):
        r = mp("exec", "print('up')", timeout=20)
        if "up" in r.stdout:
            ok = True
            break
        print(".", end="", flush=True)
        time.sleep(3)
    print()
    if not ok:
        return None
    code = ("import machine, network, time, wifi_cipher\n"
            "S = %r\nP = %r\nN = %r\n"
            "try:\n    w = machine.WDT(timeout=120000)\nexcept Exception:\n    w = None\n"
            "sta = network.WLAN(network.STA_IF)\nsta.active(True)\nsta.disconnect()\nsta.connect(S, P)\n"
            "t = time.ticks_ms()\n"
            "while not sta.isconnected() and time.ticks_diff(time.ticks_ms(), t) < 20000:\n    if w:\n        w.feed()\n    time.sleep_ms(300)\n"
            "if sta.isconnected():\n    f = open('wifi.dat', 'w')\n    f.write(wifi_cipher.seal(S + chr(10) + P + chr(10)) + chr(10))\n    f.close()\n    if N != 'wattle':\n        f = open('name.dat', 'w')\n        f.write(N)\n        f.close()\n    print('JOINED', sta.ifconfig()[0])\n"
            "else:\n    print('FAILED', sta.status())\n") % (ssid, pw, name)
    print("  The ESP32 is joining your Wi-Fi (this can take up to 20 seconds) ...", flush=True)
    r = mp("exec", code, timeout=60)
    m = re.search(r"JOINED (\S+)", r.stdout)
    if not m:
        REASON = "join" if "FAILED" in r.stdout else "silent"
        return None
    hard_reset()                                     # it starts again and joins the Wi-Fi by itself
    return m.group(1)


def ping_wattle(ip):
    import time
    import urllib.request
    print("  Checking that it answers ", end="", flush=True)
    for _ in range(14):
        try:
            if b'"wattle"' in urllib.request.urlopen("http://%s/info" % ip, timeout=3).read():
                print()
                return True
        except Exception:
            print(".", end="", flush=True)
            time.sleep(2)
    print()
    return False


def cmd_setup(args):
    """The ready-made installation: one image (MicroPython and all the Wattle files) is written to a plain ESP32. The Wi-Fi is set up from a phone
    at the first start (browser/wsetup.py on the ESP32)."""
    global YES, PORT
    YES = "--yes" in args
    say("Set up a new ESP32 for Wattle: a phone, tablet or computer will be its screen")
    img = os.path.join(HERE, "images", "wattle_esp32_4MB.bin")
    if not os.path.exists(img):
        fail("the ready-made image is missing (%s). Developers: python3 tools/make_image.py --firmware ESP32_GENERIC-....bin --out images/wattle_esp32_4MB.bin" % img)
    say("1. The ESP32's USB port")
    PORT = find_port()
    ssid, pw = ask_wifi(args)
    board_name = ask_name(args) if ssid else "wattle"
    say("3. Looking at the ESP32")
    print("  (This can take up to a minute.)", flush=True)
    r = subprocess.run([PY, "-m", "esptool", "--connect-attempts", "30", "--after", "no-reset", "--port", PORT, "flash_id"], capture_output=True, text=True, timeout=180)
    out = r.stdout + r.stderr
    chip = re.search(r"Chip (?:type:\s+|is )(ESP32[^\s(,]*)", out)
    size = re.search(r"Detected flash size:\s+(\d+)\s*MB", out)
    mac = re.search(r"MAC:\s+([0-9a-fA-F:]{17})", out)
    need_boot = False
    if (r.returncode or not chip) and "boot mode" in out.lower():          # some ESP32s do not switch to their writing mode by themselves
        print("  The ESP32 did not switch to its writing mode by itself. This happens with some ESP32s: you can help it by hand.")
        print("  Find the small button marked BOOT on the ESP32 (not the one marked EN or RST) and HOLD it down.")
        drain()
        input("  Keep holding it, and press Enter here: ")
        need_boot = True
        r = subprocess.run([PY, "-m", "esptool", "--connect-attempts", "30", "--after", "no-reset", "--port", PORT, "flash_id"], capture_output=True, text=True, timeout=180)
        out = r.stdout + r.stderr
        chip = re.search(r"Chip (?:type:\s+|is )(ESP32[^\s(,]*)", out)
        size = re.search(r"Detected flash size:\s+(\d+)\s*MB", out)
        mac = re.search(r"MAC:\s+([0-9a-fA-F:]{17})", out)
    if r.returncode or not chip:
        tail = [l for l in out.replace("\r", "").split("\n") if l.strip()][-6:]       # what esptool itself said: the real reason
        print("  esptool said:")
        for l in tail:
            print("    " + l[:150])
        fail("the ESP32 does not answer. Close any program that uses it (Thonny), try another USB cable, or hold its BOOT button while you start this again.")
    print("  OK  %s, %s MB of flash" % (chip.group(1), size.group(1) if size else "?"))
    if not re.match(r"ESP32(-D0|-PICO)", chip.group(1)):
        fail("this ready-made image is for a plain ESP32 (like ESP32-D0WD), not for %s." % chip.group(1))
    if size and int(size.group(1)) < 4:
        fail("the ESP32 has only %s MB of flash; the image needs 4 MB." % size.group(1))
    say("4. Writing the image")
    print("  This ERASES everything on the ESP32 (MicroPython and Wattle are written fresh).")
    if not ask("Erase the ESP32 and write Wattle to it?", "n"):
        fail("cancelled; nothing was changed.")
    if need_boot:
        print("  Keep holding the BOOT button until the window says Writing at ...")
    ok = False
    for before, tries in (("no-reset", "5"), ("default-reset", "30")):      # the look above left the chip in writing mode: no second lucky reset is needed
        cmd = [PY, "-m", "esptool", "--connect-attempts", tries, "--before", before, "--chip", "esp32", "--port", PORT, "--baud", "460800", "write_flash", "-z", "0x0", img]
        if subprocess.call(cmd) == 0:
            ok = True
            break
    if not ok:
        fail("writing failed. Try another USB cable, or hold the ESP32's BOOT button while it starts, then run  wattle setup  again.")
    name = "Wattle-"
    if mac:
        b = bytes(int(x, 16) for x in mac.group(1).split(":"))
        name = "Wattle-%02X%02X" % (b[4], (b[5] + 1) & 0xFF)
    addr = None
    while ssid:
        say("5. Giving the ESP32 your Wi-Fi")
        addr = put_wifi_on_esp32(ssid, pw, need_boot, board_name)
        if not addr and REASON == "silent":
            print("  The ESP32 has not answered yet. Trying once more ...")
            addr = put_wifi_on_esp32(ssid, pw, False, board_name)
        if addr:
            break
        if REASON == "silent":
            fail("the ESP32 does not answer over the cable. Unplug it, plug it in again, and run this again.")
        print("  The ESP32 could not join the Wi-Fi %s. Check the name and the password (it must be a 2.4 GHz Wi-Fi)." % ssid)
        if "--ssid" in args:
            break
        drain()
        again = input("  Type the Wi-Fi name again (or press Enter to set it up from your phone instead): ").strip()
        if not again:
            ssid = None
            break
        ssid = again
        drain()
        pw = input("  Its password: ")
    if addr:
        up = ping_wattle(addr)
        try:
            import myboards
            myboards.add(board_name, "board_browser", addr)     # "My boards": the Editor lists it in File > New Design
        except Exception:
            pass
        say("Done. The ESP32 is on your Wi-Fi.")
        print("  On your phone (joined to the same Wi-Fi), open   http://%s.local/" % board_name)
        print("  You should see  Wattle is running!   (If the name does not open, type  http://%s/ )" % addr)
        if not up:
            print("  (This computer could not see the ESP32 just now. That is fine if the phone can.)")
        return 0
    say("5. The ESP32 needs your Wi-Fi: do this on your PHONE (about a minute)")
    print("  a) Open the Wi-Fi settings of the phone and join the network  %s  (it has no password)." % name)
    print("  b) A page opens by itself. If it does not, open Chrome and type  http://192.168.4.1/")
    print("  c) Choose your Wi-Fi, type its password and tap  Save and join.")
    print("  d) Join your normal Wi-Fi again, then open  http://wattle.local/  on the phone. You should see \"Wattle is running!\".")
    print("  The setup stays open for 10 minutes. If you miss it, unplug the ESP32 and plug it in again.")
    return 0


def cmd_install(args):
    global YES, PORT
    if "--browser" in args:                      # the browser version: any ESP32 with Wi-Fi
        return run_tool("install_wattle.py", *args)
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
        es = [PY, "-m", "esptool", "--connect-attempts", "30", "--chip", "esp32", "--port", PORT]
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

    name = ""
    if not YES:
        say("A name for this board")
        print("  Give each CYD board a name of its own, so that you can tell your boards apart.")
        print("  Rules for the name: letters, digits, - and _ . No spaces. At most 24 characters.")
        print("  Examples:  CYD_51    Workshop")
        while True:
            name = ""
            while not re.fullmatch(r"[A-Za-z0-9_-]{1,24}", name):
                flush_input()
                name = input("  Name: ").strip()
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,24}", name):
                    print("  That name does not follow the rules. Please try again.")
            print("  You typed the name: " + name)
            if ask("Is that right?"):
                break
            print("  Then type the name again.")
    if name:
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(name + "\n")
        r = mp("fs", "cp", f.name, ":board_name.txt")
        os.remove(f.name)
        print("  OK  this board is called: " + name if r.returncode == 0 else "  !!  could not write the name to the board")
    else:
        mp("fs", "rm", ":board_name.txt")
    try:
        import myboards
        myboards.add(name or "CYD", "board_cyd")                # "My boards": the Editor lists it in File > New Design
    except Exception:
        pass

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
              "pick": ("tools", "picker.py"), "test": ("tests", "run_test.py"), "wifi": ("wifi_setup.py",), "pin": ("pin_setup.py",),
              "remove": ("tools", "remove_wattle.py")}
    if cmd == "install":
        return cmd_install(rest)
    if cmd == "setup":
        return _logged(cmd_setup, rest)
    if cmd == "new":
        return cmd_new(rest)
    if cmd == "deploy":
        return cmd_deploy(rest)
    if cmd == "editor":
        return cmd_editor(rest)
    if cmd == "reset":
        return cmd_reset(rest)
    if cmd == "uninstall":
        return run_tool(os.path.join("tools", "remove_wattle.py"), "--uninstall")
    if cmd in simple:
        return run_tool(os.path.join(*simple[cmd]), *rest)
    print("Unknown command '%s'. Type  wattle help" % cmd)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(1)
