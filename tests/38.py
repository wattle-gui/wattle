# Test 38 -- STRESS TEST 2: what test 37 leaves out. Three screens: four large pictures (redrawn at every visit), big fonts in four
# typefaces plus a gauge and a waveform, and a typing screen. The program changes screen every 15 seconds, and every 50 seconds a
# scripted "finger" (a stand-in for the touch panel) answers a pop-up message(...) and types ABC + Enter on the keyboard; the test
# checks the answers. So the things that need one BIG block of memory (pictures, fonts, the pop-up box, the keyboard) are exercised
# for hours. Logging as in test 37: a BOOT line (why the board started), a line a minute (free / allocated / largest block, counts,
# timer ages), ERROR lines with a full traceback and the memory state, and a 120 s watchdog that records a freeze as "WDT reset".
# DO NOT use mpremote while this runs (it interrupts the program). A passive look at the serial port is fine.
import gc, math, time, random, sys
import machine
import Runtime
from Runtime import *

CAUSES = {machine.PWRON_RESET: "power-on", machine.HARD_RESET: "hard reset", machine.WDT_RESET: "WDT reset (freeze!)",
          machine.DEEPSLEEP_RESET: "deep sleep", machine.SOFT_RESET: "soft reset"}
MAX_ERROR_LINES = 400

t0 = time.ticks_ms()
runs = 0
changes = 0
errors = 0
error_lines = 0
msg_ok = msg_bad = kb_ok = kb_bad = 0
phase = 0.0
names = ["pics", "fonts", "typing"]
current = 0
last_fast = last_slow = t0


class ScriptedTouch:
    """Wraps the real touch panel. tap(x, y, after_ms) schedules a 'finger' that stays down for 220 ms, so message() and the
    keyboard can be operated without a person. Real touches still work."""

    def __init__(self, real):
        self.real = real
        self.taps = []

    def tap(self, x, y, after_ms):
        self.taps.append((time.ticks_add(time.ticks_ms(), after_ms), x, y))

    def clear(self):
        self.taps = []

    def _now(self):
        now = time.ticks_ms()
        for t, x, y in self.taps:
            d = time.ticks_diff(now, t)
            if 0 <= d < 220:
                return (x, y)
        return None

    def pressed(self):
        return self._now() is not None or self.real.pressed()

    def read(self):
        p = self._now()
        return p if p is not None else self.real.read()

    def raw(self):
        return self.real.raw()


fake = ScriptedTouch(Runtime.touch)
Runtime.touch = fake                            # the Runtime looks this name up every time it reads the screen


def largest_block():
    for k in (32768, 24576, 16384, 12288, 8192, 6144, 4096, 3072, 2048, 1024):
        try:
            b = bytearray(k)
            del b
            return k
        except MemoryError:
            pass
    return 0


def say(text):
    with open("stress_log.txt", "a") as f:
        f.write(text)


def state():
    gc.collect()
    return "free %d alloc %d block %d" % (gc.mem_free(), gc.mem_alloc(), largest_block())


def safe(fn):
    def run_it():
        global errors, error_lines
        try:
            fn()
        except Exception as e:
            errors += 1
            fake.clear()
            print("ERROR in %s: %s: %s" % (fn.__name__, type(e).__name__, e))
            sys.print_exception(e)
            if error_lines >= MAX_ERROR_LINES:
                return
            with open("stress_log.txt", "a") as f:
                f.write("ERROR #%d in %s at %d s, screen %s: %s: %s | %s\n" % (
                    errors, fn.__name__, (time.ticks_ms() - t0) // 1000, names[current], type(e).__name__, e, state()))
                sys.print_exception(e, f)
                error_lines += 8
    return run_it


def msg_rects(text, buttons):
    # The same arithmetic as Runtime.message(), to know where its buttons are.
    box_w = Runtime.WIDTH - 40
    sc = 2
    lines = Runtime._wrap(text, (box_w - 16) // (8 * sc))
    if len(lines) > 4:
        sc = 1
        lines = Runtime._wrap(text, (box_w - 16) // 8)
    lh = 8 * sc + 4
    btn_h = 40
    box_h = 12 + len(lines) * lh + 14 + btn_h + 12
    bx = 20
    by = max(0, (Runtime.HEIGHT - box_h) // 2)
    n = len(buttons)
    gap = 8
    each = (box_w - 16 - gap * (n - 1)) // n
    btn_y = by + box_h - 12 - btn_h
    return [(bx + 8 + i * (each + gap), btn_y, each, btn_h) for i in range(n)]


def centre(r):
    return (r[0] + r[2] // 2, r[1] + r[3] // 2)


def fast():                                    # about 10 times a second
    global runs, phase, last_fast
    last_fast = time.ticks_ms()
    runs += 1
    phase += 0.15
    s = math.sin(phase)
    g1.value = 50 + 45 * s
    w1.add(50 + 40 * math.cos(phase * 1.3) + random.randint(-5, 5))


def slow():                                    # once a second
    global last_slow
    last_slow = time.ticks_ms()
    wdt.feed()
    t3.text = "checks: msg %d/%d kb %d/%d" % (msg_ok, msg_ok + msg_bad, kb_ok, kb_ok + kb_bad)


def exercise():                                # every 50 seconds: pop-up message, then the keyboard
    global msg_ok, msg_bad, kb_ok, kb_bad
    text = "Reset the counter?"
    buttons = ("Yes", "No")
    x, y = centre(msg_rects(text, buttons)[0])
    fake.tap(x, y, 700)                         # the finger presses "Yes"
    answer = message(text, *buttons)
    fake.clear()
    if answer == "Yes":
        msg_ok += 1
    else:
        msg_bad += 1
        say("CHECK FAILED message: got %r, wanted 'Yes' at %d s\n" % (answer, (time.ticks_ms() - t0) // 1000))
    t2.text = "message: " + str(answer)

    keys = Runtime._kb_keys(Runtime._kb_geom(), False)
    pos = {}
    for k in keys:
        pos[k[0]] = (k[1] + k[3] // 2, k[2] + k[4] // 2)
    delay = 2200                                # drawing the keyboard takes about a second; an earlier tap is taken for the opening tap
    for label in ("A", "B", "C", "Enter"):
        fake.tap(pos[label][0], pos[label][1], delay)
        delay += 600
    typed = keyboard1.show()
    fake.clear()
    if typed == "ABC":
        kb_ok += 1
    else:
        kb_bad += 1
        say("CHECK FAILED keyboard: got %r, wanted 'ABC' at %d s\n" % (typed, (time.ticks_ms() - t0) // 1000))
    t1.text = "typed: " + str(typed)
    print("exercise at %d s: message=%r keyboard=%r" % ((time.ticks_ms() - t0) // 1000, answer, typed))


def log():                                     # once a minute
    s = (time.ticks_ms() - t0) // 1000
    now = time.ticks_ms()
    say("%d s  %s  runs %d  screens %d  msg %d/%d  kb %d/%d  errors %d  fast-age %d ms  slow-age %d ms\n" % (
        s, state(), runs, changes, msg_ok, msg_ok + msg_bad, kb_ok, kb_ok + kb_bad, errors,
        time.ticks_diff(now, last_fast), time.ticks_diff(now, last_slow)))


def change_screen():                           # every 15 seconds
    global current, changes
    current = (current + 1) % 3
    changes += 1
    Screen(names[current])


say("BOOT %s | MicroPython %s | %s\n" % (CAUSES.get(machine.reset_cause(), "reset cause %s" % machine.reset_cause()),
                                          ".".join(str(n) for n in sys.implementation.version[:3]), state()))
wdt = machine.WDT(timeout=120000)

every(100, safe(fast))
every(1000, safe(slow))
every(60000, safe(log))
every(15000, safe(change_screen))
every(50000, safe(exercise))
print("test 38 running")
run()
