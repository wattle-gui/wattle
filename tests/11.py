# Test 11 -- "secret": the keyboard shows * instead of what is typed (a password, for example).
# No target is set, so the digits never appear on the main screen; show() RETURNS the text
# (or None if the user pressed Esc) and the script decides what to do with it.
from Runtime import *

def button1_click():
    password = keyboard1.show()
    if password is None:
        label1.text = "cancelled"
    elif password == "1234":
        label1.text = "password correct"
    else:
        label1.text = "wrong password (%d digits)" % len(password)

run()
