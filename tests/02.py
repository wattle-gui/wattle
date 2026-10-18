# Test 02 -- switch and checkbox. Both send a "changed" event with their new value.
from Runtime import *

def switch1_changed(value):                # value is True (on) or False (off)
    label1.text = "Switch: " + ("ON" if value else "OFF")

def checkbox1_changed(value):
    label2.text = "Check: " + ("yes" if value else "no")

run()
