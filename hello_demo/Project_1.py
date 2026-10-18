# The demo shown after installation.
# Screen "main": a title, a caption, a tap counter and a button. The third tap switches to screen "done": a live gauge and a moving
# chart, to show what Wattle looks like, and a long button. The button switches to screen "yours" (a short note); 10 seconds later the
# screen goes blank and the demo ends, which frees the board.
import math
from Runtime import *

count = 0                        # remembers how many taps so far
live = False                     # True while screen "done" is showing (only then the gauge and chart are moved)
phase = 0.0

def button1_click():             # the Runtime calls this each time button1 is tapped
    global count, live
    count += 1
    label1.text = "Taps: %d" % count     # changing .text redraws the label at once
    if count == 3:                       # the third tap: show the live screen
        live = True
        Screen("done")

leaving = 0                      # counts the ticks since Exit was tapped (0 = not tapped yet)

def button2_click():             # "Exit - and design your own"
    global live, leaving
    live = False
    leaving = 1
    Screen("yours")

def tick():                      # about 10 times a second
    global phase
    global leaving
    phase += 0.12
    if leaving:                          # 100 ticks = 10 seconds after Exit: blank the screen and end the demo,
        leaving += 1                     # so the board is free (Thonny or mpremote can connect)
        if leaving > 100:
            backlight(0)
            raise SystemExit
    if live:
        gauge1.value = 50 + 40 * math.sin(phase)
        waveform1.add(50 + 35 * math.sin(phase * 1.7) + 10 * math.sin(phase * 0.5))

every(100, tick)
run()                            # hand control to the Runtime (waits for taps)
