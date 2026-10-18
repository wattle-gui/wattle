# Test 22 -- tree (a menu with up to 3 levels). Tapping a parent opens/closes it; tapping an end
# item selects it and sends its text path, e.g. "Display/Theme/Dark".
from Runtime import *

def tree1_selected(path):
    label1.text = path              # a real menu would open a screen here, e.g.  Screen("wifi")

def button1_click():
    tree1.selected = "Network/WiFi"     # a script can choose an item; the branches above it open
    label1.text = "Network/WiFi"

run()
