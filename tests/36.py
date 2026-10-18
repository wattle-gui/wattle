# Test 36 -- the design saved by the Editor (MASTER_cursor.json), showing its "master_displays" screen.
# The widgets are only connected by the script: the stepper sets the gauge and the waveform.
from Runtime import *

def stepper1_changed(value):
    gauge1.value = value
    waveform1.add(value)

Screen("master_displays")
run()
