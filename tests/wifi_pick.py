# Pick WiFi -- a working network chooser. Scan lists the networks in the dropdown, Connect asks
# for the password on the keyboard (shown as *) and joins. The password is never shown. When the
# connection works, the name and password are saved SEALED in wifi.dat (readable only on this board),
# which is the file Runtime's wifi() reads, so the board joins by itself from then on.
import network, time
from Runtime import *

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
names = []

def button1_click():                       # Scan
    global names
    label2.text = "Scanning..."
    found = {}
    for n in wlan.scan():                  # (ssid, bssid, channel, rssi, security, hidden)
        name = n[0].decode()
        if name and (name not in found or n[3] > found[name]):
            found[name] = n[3]
    names = sorted(found, key=lambda k: -found[k])[:8]      # strongest first
    choice1.items = names or ["(none found)"]
    choice1.selected = 0
    label2.text = "%d networks found. Pick one." % len(names)

def button2_click():                       # Connect
    if not names:
        label2.text = "Scan first."
        return
    name = names[choice1.selected]
    pw = keyboard1.show()                  # None = Esc
    if pw is None:
        label2.text = "Cancelled."
        return
    label2.text = "Connecting to " + name + "..."
    wlan.disconnect()
    wlan.connect(name, pw)
    for _ in range(40):
        if wlan.isconnected():
            label2.text = "Connected! IP " + wlan.ifconfig()[0]
            try:
                import wifi_cipher
                with open("wifi.dat", "w") as f:
                    f.write(wifi_cipher.seal(name + "\n" + pw) + "\n")
                label2.text = "Connected and saved! IP " + wlan.ifconfig()[0]
            except Exception:
                pass                       # no wifi_cipher on the board: connected, but not saved
            return
        time.sleep_ms(250)
    label2.text = "Could not connect. Wrong password?"

run()
