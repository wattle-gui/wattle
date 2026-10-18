# Test 23 -- an error in your script is shown on the screen (and printed on the serial port).
# Each button below contains a deliberate mistake.
from Runtime import *

def button1_click():
    label1.text = "dividing..."
    x = 1 / 0                        # ZeroDivisionError

def button2_click():
    label1.text = undefined_name     # NameError

def tick():
    raise ValueError("this task fails on purpose")

def button3_click():
    every(2000, tick)                # starts a task that fails 2 seconds later (and is then stopped)

run()
