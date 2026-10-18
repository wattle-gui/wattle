# Test 18 -- LOW_POWER: between touch checks the processor sleeps (lightsleep) instead of waiting.
# Everything else works as before; taps are noticed within about 0.15 second.
# (A board in this mode ignores the computer's stop request -- reset it with reset.sh.)
import Runtime
Runtime.LOW_POWER = True          # set BEFORE the loop starts

from Runtime import *

PERIOD = 1500                     # milliseconds between ticks -- change it and reload

ticks = 0
taps = 0

def tick():
    global ticks
    ticks += 1
    label1.text = "ticks: %d" % ticks
    progressbar1.value = (ticks * 10) % 110

def button1_click():
    global taps
    taps += 1
    button1.text = "Taps: %d" % taps

every(PERIOD, tick)
run()
