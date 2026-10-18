# Test 15 -- "enabled" and "visible". A disabled widget ignores taps; a hidden one is
# neither drawn nor tappable. The script can change both at any time.
from Runtime import *

def btn_dis_click():   status.text = "disabled button worked"
def btn_hid_click():   status.text = "hidden button worked"

def btn_show_click():
    status.text = "show tapped"
    btn_hid.visible = True        # appears on top of "behind"

def btn_hide_click():
    status.text = "hide tapped"   # (shows the tap arrived)
    btn_hid.visible = False       # disappears; "behind" shows again

def btn_enable_click():
    status.text = "enable tapped"
    btn_dis.enabled = True        # now it answers taps

run()
