# Test 08 -- changing a widget on a screen that is NOT showing.
# The new value is kept, and appears the next time that screen is shown.
# (Copying values between screens is the script's job -- nothing is done automatically.)
from Runtime import *

count = 0

def button1_click():
    global count
    count += 1
    label2.text = "changed %d time(s)" % count    # label2 lives on the "second" screen

def button2_click():
    Screen("second")

def button3_click():
    Screen("first")

run()
