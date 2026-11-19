# Test E24 -- TWO screens, TWO orientations: screen1 is landscape (320 x 240), screen2 is portrait (240 x 320).
# Screen() turns the display and the touch to the shape of the screen it shows.
from Runtime import *

def button2_click(): label1.text = "landscape: top-left"
def button3_click(): label1.text = "landscape: top-right"
def button4_click(): label1.text = "landscape: bottom-left"
def button5_click(): label1.text = "landscape: bottom-right"
def button6_click(): Screen("screen2")

def button8_click(): label7.text = "portrait: top-left"
def button9_click(): label7.text = "portrait: top-right"
def button10_click(): label7.text = "portrait: bottom-left"
def button11_click(): label7.text = "portrait: bottom-right"
def button12_click(): Screen("screen1")

run()
