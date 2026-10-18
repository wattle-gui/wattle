# Test 35 -- one big gauge with + and - buttons (to study the drawing). The scale has 10 intervals, the first mark is 0.
from Runtime import *

def change(d):
    gauge1.value = max(0, min(100, gauge1.value + d))

def button1_click():
    change(5)

def button2_click():
    change(-5)

run()
