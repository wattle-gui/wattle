# Test 11 -- "secret": the keyboard shows * instead of what is typed (a PIN or password).
# No target is set, so the digits never appear on the main screen; show() RETURNS the text
# (or None if the user pressed Esc) and the script decides what to do with it.
from Runtime import *

def button1_click():
    pin = keyboard1.show()
    if pin is None:
        label1.text = "cancelled"
    elif pin == "1234":
        label1.text = "PIN correct"
    else:
        label1.text = "wrong PIN (%d digits)" % len(pin)

run()
