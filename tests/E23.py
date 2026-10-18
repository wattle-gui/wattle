# Test E23 -- PORTRAIT screen (240 x 320), design built in the Editor.
# The runtime reads "orientation": "portrait" / width 240 / height 320 from the design and
# turns the display; the board file (board_cyd.py) holds the portrait rotation and touch numbers.
from Runtime import *

def button1_click(): label1.text = "top-left"
def button2_click(): label1.text = "top-right"
def button3_click(): label1.text = "bottom-left"
def button4_click(): label1.text = "bottom-right"

def slider1_changing(value):
    label1.text = "slider %d" % value

run()
