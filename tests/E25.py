# MultiScreen: two screens, each with one button. Tapping a button shows the other screen.
# screen1 and screen2 may have different orientations (landscape and portrait): the display turns to the shape of the screen it shows.
from Runtime import *

def button1_click():             # the button on screen1
    Screen("screen2")

def button2_click():             # the button on screen2
    Screen("screen1")

run()
