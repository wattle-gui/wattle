# Test 21 -- dropdown ("choice" widget, style "dropdown"). The widget's height is the height of the
# closed field AND of every row in the list. The list opens over the other widgets (below the field,
# or above it when there is no room below); when it closes, what was under it is redrawn.
from Runtime import *

taps = 0

def choice1_changed(index):
    label1.text = choice1.items[index]

def choice2_changed(index):
    label3.text = choice2.items[index]

def button1_click():
    global taps
    taps += 1
    label2.text = "taps: %d" % taps

run()
