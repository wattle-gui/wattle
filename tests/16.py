# Test 16 -- periodic tasks. every(ms, function) calls function every ms milliseconds
# without any touch; stop(function) cancels it. Touch handlers keep working meanwhile.
from Runtime import *

seconds = 0
taps = 0

def tick():                        # once a second
    global seconds
    seconds += 1
    label1.text = "seconds: %d" % seconds

def sweep():                       # five times a second: bar runs 0..100 and starts over
    progressbar1.value = (progressbar1.value + 5) % 105

def button1_click():               # stop / restart the clock
    if button1.text == "Stop clock":
        stop(tick)
        button1.text = "Start clock"
    else:
        every(1000, tick)
        button1.text = "Stop clock"

def button2_click():               # proves taps still work while tasks run
    global taps
    taps += 1
    button2.text = "Taps: %d" % taps

every(1000, tick)
every(200, sweep)
run()
