# Test 30 -- Wi-Fi and the real time. wifi() reads the network name and password from wifi.dat on the board
# (line 1 = name, line 2 = password; they are never shown; wifi_setup.py puts the file there). ntp() sets the clock from the internet.
# timezone(h) tells now() your hours from UTC: change the 10 below to your own.
from Runtime import *

timezone(10)

def tick():                                  # twice a second is plenty for a clock
    t = now()
    label1.text = "%02d:%02d:%02d" % (t[3], t[4], t[5])
    label2.text = "%04d-%02d-%02d" % (t[0], t[1], t[2])

def button1_click():
    label3.text = "connecting ..."
    if not wifi():
        label3.text = "no Wi-Fi (see wifi.dat)"
    elif ntp():
        label3.text = "time set; " + wifi_ip()
    else:
        label3.text = "connected, no time"

def button2_click():
    wifi_off()
    label3.text = "Wi-Fi off"

every(500, tick)
run()
