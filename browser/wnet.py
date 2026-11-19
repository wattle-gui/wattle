# wnet.py -- the network side of Wattle in the browser (runs ON the board): joins Wi-Fi, keeps the log file, and says who the board is.
# The password comes from wifi.dat, put there by  wattle wifi  (sealed with the chip's own key, see wifi_cipher.py).
import network
import os
import time



def _name():
    """The board's network name: http://<name>.local. name.dat (one line) gives it another name when two boards share a network."""
    try:
        n = open("name.dat").read().strip()
    except OSError:
        n = ""
    return n or "wattle"


NAME = _name()
sta = network.WLAN(network.STA_IF)


def log(text):
    try:
        if os.stat("wattle_log.txt")[6] > 12000:             # a board that wakes every minute would fill the flash: keep the last two logs only
            try:
                os.remove("wattle_log.old")
            except OSError:
                pass
            os.rename("wattle_log.txt", "wattle_log.old")
    except OSError:
        pass
    try:
        f = open("wattle_log.txt", "a")
        f.write("%d s: %s\n" % (time.ticks_ms() // 1000, text))
        f.close()
    except OSError:
        pass


def read_credentials():
    try:
        text = open("wifi.dat").read().strip()
    except OSError:
        return None
    if text.startswith("wattle1:"):
        import wifi_cipher
        text = wifi_cipher.unseal(text.split("\n")[0])
        if not text:
            return None
    lines = text.split("\n")
    return (lines[0], lines[1]) if len(lines) > 1 else None


SSID = ""


def _cached(ssid):
    """After a deep sleep of up to an hour the board may reuse the address it had (it skips the DHCP wait). The address and the
    sleep time were kept in the chip's RTC memory by deepsleep(); a longer sleep, a power-off or another network: not used."""
    try:
        import json
        import machine
        d = json.loads(machine.RTC().memory())
        if d.get("s") == ssid and 0 < d.get("t", 0) <= 3600:
            return tuple(d["n"])
    except Exception:
        pass
    return None


def _join(cred, address):
    sta.active(True)
    try:
        sta.config(pm=sta.PM_NONE)           # no Wi-Fi power saving: a napping board misses the multicast name lookups (wattle.local) and answers slowly
    except Exception:
        pass
    try:
        network.hostname(NAME)               # MicroPython 1.23 and later
    except (AttributeError, ValueError):
        try:
            sta.config(dhcp_hostname=NAME)   # 1.22
        except Exception:
            pass
    if address:
        sta.ifconfig(address)
    sta.connect(cred[0], cred[1])


def _portal(reason):
    """No Wi-Fi saved, or it cannot be joined: the ESP32 opens a network of its own and a phone sets the Wi-Fi up (see wsetup.py). Never returns."""
    log("Wi-Fi setup starts: " + (reason or "no Wi-Fi saved yet"))
    import wsetup
    wsetup.run(reason)


def connect():
    global SSID
    cred = read_credentials()
    if not cred:
        _portal("")
    SSID = cred[0]
    address = _cached(SSID)
    if sta.active():                         # a restart that left the radio on: start clean
        sta.active(False)
        time.sleep(0.5)
    t0 = time.ticks_ms()
    _join(cred, address)
    limit = 5000 if address else 30000
    while not sta.isconnected():
        if time.ticks_diff(time.ticks_ms(), t0) > limit:
            if not address:
                _portal("The ESP32 could not join the Wi-Fi %s. Check its name and password (or wait until your router is on) and try again." % SSID)
            log("Wi-Fi: the old address did not work, joining the normal way")
            sta.active(False)
            time.sleep(0.5)
            address = None
            t0 = time.ticks_ms()
            _join(cred, None)
            limit = 30000
        time.sleep_ms(20)
    log("Wi-Fi joined in %d ms%s" % (time.ticks_diff(time.ticks_ms(), t0), " with the address from before" if address else ""))
    return sta.ifconfig()[0]
