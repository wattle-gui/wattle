# Test 37 -- STRESS TEST. Three screens full of widgets; timers move gauges, charts and bars about 10 times a second and the
# program changes screen every 15 seconds, for hours. It writes stress_log.txt on the board:
#   BOOT line at every start (why the board restarted: power-on, watchdog, crash ...), then once a minute a line with
#   uptime, free memory, allocated memory, the largest free block, timer runs, screen changes, errors, and how long ago each
#   timer last ran (a timer that stopped shows up as a growing age), and ERROR lines with a full traceback, the memory state
#   at that moment and which screen was showing.
# A watchdog (machine.WDT, 120 s) restarts the board if the program freezes; the next BOOT line then says "WDT reset", so a
# freeze is recorded instead of leaving a dead board and a log that just stops.
# Free memory that keeps falling means a leak; "largest block" falling while free memory stays flat means fragmentation;
# "timer runs" that stop growing means a timer died.
# DO NOT use mpremote while this runs: it interrupts the program (the watchdog then restarts the test and the log says so).
import gc, math, time, random, sys
import machine
from Runtime import *

CAUSES = {machine.PWRON_RESET: "power-on", machine.HARD_RESET: "hard reset", machine.WDT_RESET: "WDT reset (freeze!)",
          machine.DEEPSLEEP_RESET: "deep sleep", machine.SOFT_RESET: "soft reset"}
MAX_ERROR_LINES = 400          # the log must not fill the flash if something goes badly wrong

t0 = time.ticks_ms()
runs = 0
changes = 0
errors = 0
error_lines = 0
phase = 0.0
names = ["a", "b", "c"]
current = 0
last_fast = last_slow = t0


def largest_block():
    # The biggest bytearray that can still be allocated (probes 32 KB down to 1 KB): falls when memory is fragmented.
    for k in (32768, 24576, 16384, 12288, 8192, 6144, 4096, 3072, 2048, 1024):
        try:
            b = bytearray(k)
            del b
            return k
        except MemoryError:
            pass
    return 0


def say(text):
    global error_lines
    with open("stress_log.txt", "a") as f:
        f.write(text)


def state():
    gc.collect()
    return "free %d alloc %d block %d" % (gc.mem_free(), gc.mem_alloc(), largest_block())


def safe(fn):                                  # a failure is written to the log (and counted) instead of stopping the test
    def run_it():
        global errors, error_lines
        try:
            fn()
        except Exception as e:
            errors += 1
            if error_lines >= MAX_ERROR_LINES:
                return
            with open("stress_log.txt", "a") as f:
                f.write("ERROR #%d in %s at %d s, screen %s: %s: %s | %s\n" % (
                    errors, fn.__name__, (time.ticks_ms() - t0) // 1000, names[current], type(e).__name__, e, state()))
                sys.print_exception(e, f)
                error_lines += 8
    return run_it


def fast():                                    # about 10 times a second
    global runs, phase, last_fast
    last_fast = time.ticks_ms()
    runs += 1
    phase += 0.15
    s = math.sin(phase)
    gauge1.value = 50 + 45 * s
    gauge2.value = 50 + 45 * math.cos(phase * 0.7)
    gauge3.value = 50 + 45 * math.sin(phase * 0.4)
    waveform1.add(50 + 40 * s)
    waveform2.add(50 + 40 * math.cos(phase * 1.3))
    waveform3.add(50 + 40 * math.sin(phase * 0.5) + random.randint(-5, 5))
    progressbar1.value = int(50 + 45 * s)
    barchart1.set(runs % 8, random.randint(0, 100))
    barchart2.set(runs % 10, random.randint(0, 100))


def slow():                                    # once a second
    global last_slow
    last_slow = time.ticks_ms()
    wdt.feed()
    s = (time.ticks_ms() - t0) // 1000
    label1.text = "%02d:%02d:%02d" % (s // 3600, s // 60 % 60, s % 60)
    label2.text = "screen b  %d" % s
    memo1.text = "up %d s\nruns %d" % (s, runs)


def log():                                     # once a minute
    s = (time.ticks_ms() - t0) // 1000
    now = time.ticks_ms()
    say("%d s  %s  runs %d  screens %d  errors %d  fast-age %d ms  slow-age %d ms\n" % (
        s, state(), runs, changes, errors, time.ticks_diff(now, last_fast), time.ticks_diff(now, last_slow)))


def change_screen():                           # every 15 seconds
    global current, changes
    current = (current + 1) % 3
    changes += 1
    Screen(names[current])


def stepper1_changed(value):
    gauge1.value = value


say("BOOT %s | MicroPython %s | %s\n" % (CAUSES.get(machine.reset_cause(), "reset cause %s" % machine.reset_cause()),
                                          ".".join(str(n) for n in sys.implementation.version[:3]), state()))
wdt = machine.WDT(timeout=120000)

every(100, safe(fast))
every(1000, safe(slow))
every(60000, safe(log))
every(15000, safe(change_screen))
run()
