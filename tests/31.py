# Test 31 -- gauge, stepper, chart. The stepper (- / +) sets a value; the big gauge shows it, and every second the
# chart adds the stepper value. "Add noise" adds a random wobble to the chart. gauge2 is a half-circle gauge (sweep=180).
import random
from Runtime import *

def stepper1_changed(value):
    gauge1.value = value
    gauge2.value = value / 10

def tick():
    waveform1.add(stepper1.value)

def button1_click():
    waveform1.clear()

def button2_click():
    waveform1.add(max(0, min(100, stepper1.value + random.randint(-30, 30))))

every(200, tick)        # five points a second: try 100 or less
run()
