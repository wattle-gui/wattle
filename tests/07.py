# Test 07 -- two screens. Screen("<id>") shows another screen of the same design.
# The design lists both screens; the first one in the list is shown at start-up.
from Runtime import *

def button1_click():
    Screen("second")

def button2_click():
    Screen("first")

run()
