# E26 -- a design made in the Editor with the four new widgets. The script connects them:
# the stepper sets the gauge and adds a value to the waveform.
from Runtime import *

def stepper1_changed(value):
    gauge1.value = value
    waveform1.add(value)

run()
