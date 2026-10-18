# Test 03 -- sliders (horizontal and vertical) driving progress bars.
from Runtime import *

def slider1_changing(value):         # called on every step WHILE the finger moves
    label1.text = "H: %d" % value

def slider1_changed(value):          # called once, when the finger is lifted
    progressbar1.value = value       # a progress bar just shows .value (0..max)

def slider2_changing(value):
    label2.text = "V: %d" % value

def slider2_changed(value):
    progressbar2.value = value

def button1_click():                 # setting .value from the script moves the slider too
    for w in (slider1, progressbar1, slider2, progressbar2):
        w.value = 0
    label1.text = "H: 0"
    label2.text = "V: 0"

def button2_click():
    for w in (slider1, progressbar1, slider2, progressbar2):
        w.value = 100
    label1.text = "H: 100"
    label2.text = "V: 100"

run()
