#!/usr/bin/env python3
# run_test.py N -- load test N onto the board and show what to look for.
#   python3 tests/run_test.py 0        (Windows: set ESP_PORT=COM5 first)
# Steps: clean the board (keeps the runtime + boot files) -> upload NN.json, NN.py as Project_1.py,
# design.txt, the fonts and images the design uses -> reset the board.
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import wattle_port
PORT = wattle_port.PORT
KEEP = ("boot.py", "main.py", "Runtime.mpy", "Runtime.py", "ili9341.mpy", "ili9341.py",
        "board_cyd.py", "touch_xpt2046.py", "ID.dat", "wifi.dat")

CLEAN = """
import os
keep = %r
def rmtree(p):
    for n in os.listdir(p):
        q = p + '/' + n
        if os.stat(q)[0] & 0x4000: rmtree(q)
        else: os.remove(q)
    os.rmdir(p)
for n in os.listdir():
    if n in keep: continue
    if os.stat(n)[0] & 0x4000: rmtree(n)
    else: os.remove(n)
""" % (KEEP,)


def mp(*args, check=True):
    return subprocess.run(["mpremote", "connect", PORT] + list(args), check=check)


def main():
    name = "%02d" % int(sys.argv[1]) if sys.argv[1].isdigit() else sys.argv[1]   # 20 or E20
    design_path = os.path.join(HERE, name + ".json")
    design = json.load(open(design_path))

    # Stop whatever the board is running: reset it, then send Ctrl-C again and again while it boots,
    # so it halts at the prompt BEFORE the project (maybe a sleeping LOW_POWER one) starts.
    import serial, time
    ser = serial.Serial(PORT, 115200, timeout=0.05)
    ser.dtr = False
    ser.rts = True              # EN low = reset
    time.sleep(0.1)
    ser.rts = False
    t0 = time.time()
    while time.time() - t0 < 3.0:
        ser.write(b"\x03")
        ser.read(200)
        time.sleep(0.03)
    ser.close()
    mp("exec", CLEAN)
    mp("fs", "cp", design_path, ":" + name + ".json")
    mp("fs", "cp", os.path.join(HERE, name + ".py"), ":Project_1.py")
    open(os.path.join(HERE, "design.txt"), "w").write(name + ".json\nboard_cyd\n")
    mp("fs", "cp", os.path.join(HERE, "design.txt"), ":design.txt")

    errfont = os.path.join(ROOT, "fonts", "dejavusansmono_12.fnt")      # used by the on-screen error messages
    if os.path.exists(errfont):
        mp("fs", "mkdir", ":fonts", check=False)
        mp("fs", "cp", errfont, ":fonts/dejavusansmono_12.fnt")

    kinds = {w["widget"] for s in design["screens"] for w in s["widgets"]}
    fonts = {w.get("font_type", "default") for s in design["screens"] for w in s["widgets"]}
    if fonts - {"default", ""}:
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_fonts.py"), "--upload", design_path],
                       check=True, env=dict(os.environ, ESP_PORT=PORT))
    if "image" in kinds:
        build = os.path.join(HERE, "_build")
        os.makedirs(build, exist_ok=True)
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_images.py"), design_path, "upload"],
                       check=True, cwd=build, env=dict(os.environ, ESP_PORT=PORT))

    subprocess.run(["esptool", "--port", PORT, "--after", "hard_reset", "chip_id"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    txt = os.path.join(HERE, name + ".txt")
    print("\n=== test %s loaded -- board restarted ===" % name)
    if os.path.exists(txt):
        print(open(txt).read())


main()
