# Test 14 -- buttons in the four corners: can the touch panel reach the very edges?
from Runtime import *

def tl_click(): label1.text = "top-left"
def tr_click(): label1.text = "top-right"
def bl_click(): label1.text = "bottom-left"
def br_click(): label1.text = "bottom-right"

run()
