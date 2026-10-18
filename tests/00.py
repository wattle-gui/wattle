# Test 00 -- the simplest program: one label and one button.
from Runtime import *

count = 0                        # remembers how many taps so far

def button1_click():             # the engine calls this each time button1 is tapped
    global count
    count += 1
    label1.text = "Tapped %d" % count    # changing .text redraws the label at once

run()                            # hand control to the engine (waits for taps)
