# Test 04 -- lines and an image. Lines are only drawn; the image also reacts to a tap,
# because its "events" list in the design contains "click".
# (The picture was converted to image1.raw by make_images.py; run_test.py does that for you.)
from Runtime import *

taps = 0

def image1_click():
    global taps
    taps += 1
    label1.text = "picture tapped %d" % taps

run()
