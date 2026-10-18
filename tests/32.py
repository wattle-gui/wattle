# Test 32 -- waveform (style "bars") and barchart.
# waveform1 MOVES: add(value) puts a new bar on the right and the old ones move left (use it for a voltage, a temperature ...).
# barchart1 is STATIONARY: it has 8 bars and set(number, value) changes one of them (0 = the first).
import random
from Runtime import *

def tick():
    waveform1.add(random.randint(10, 100))

def button1_click():
    barchart1.set(random.randint(0, 7), random.randint(0, 100))

def button2_click():
    waveform1.clear()
    barchart1.clear()

every(30, tick)                    # a new value every 30 ms ...  the waveform shows them at most every update_ms (150) -- see the design
run()
