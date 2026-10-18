# Test 28 -- backlight(percent), screensaver(seconds, dim) and the BOOT button.
#   backlight(20)        dim to 20 %          backlight(0)   blank the screen: a touch (or BOOT) brings it back
#   screensaver(5, 10)   after 5 s idle dim to 10 %; the next touch only wakes the screen (it is not a click)
#   screensaver(5)       after 5 s idle blank the screen completely
#   power_button(True)   the BOOT button on the back blanks the screen / wakes it again
from Runtime import *

taps = 0

def count():
    global taps
    taps += 1
    label2.text = "taps: %d" % taps

def button1_click():
    backlight(20)
    count()

def button2_click():
    backlight(100)
    count()

def button3_click():
    count()
    backlight(0)                     # blank; touch the screen (or press BOOT) to bring it back

def button4_click():
    screensaver(5, 10)
    label1.text = "saver: 5 s, dim 10%"
    count()

def button5_click():
    screensaver(5)                   # dim defaults to 0 = blank
    label1.text = "saver: 5 s, blank"
    count()

def button6_click():
    screensaver(0)
    label1.text = "saver off"
    count()

def button7_click():
    power_button(True)               # BOOT now blanks / wakes the screen
    label1.text = "BOOT = power button"
    count()

run()
