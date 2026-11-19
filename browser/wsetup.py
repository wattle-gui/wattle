# wsetup.py -- ON THE BOARD: the first-start Wi-Fi setup, done from a phone. It runs when the ESP32 has no Wi-Fi saved, or cannot join the one it has.
# The ESP32 opens a Wi-Fi network of its own, "Wattle-XXXX" (open: it is only up for a few minutes). A phone that joins it is shown a page
# (any address leads to it, so the phone offers "Sign in to network") where you pick your own Wi-Fi and type its password. The name and the password
# are sealed into wifi.dat (see wifi_cipher.py) and the ESP32 restarts and joins your Wi-Fi. If nobody finishes in 10 minutes it restarts and tries the
# normal way again (a router that is still starting up is then found). It waits 10 minutes, and each visit of the page gives it 3 more.
import socket
import time

IP = "192.168.4.1"
MINUTES = 10          # how long the setup waits; every visit of the page adds time (EXTRA)
EXTRA = 3

PAGE = ("<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Wattle setup</title>"
        "<style>body{font-family:sans-serif;max-width:420px;margin:22px auto;padding:0 14px;color:#10222a}h2{color:#0b6f86}"
        "input,button{font-size:18px;width:100%%;box-sizing:border-box;margin:6px 0 14px 0;padding:10px}"
        "button{background:#0ea5c5;color:#000;border:0;border-radius:6px}.note{background:#fff3cd;padding:10px;border-radius:6px}</style></head><body>"
        "<h2>Wattle setup</h2>%s<form method=post action=/save><label>Choose your Wi-Fi from the list</label>"
        "<select onchange=\"document.getElementsByName('ssid')[0].value=this.value\" style='font-size:18px;width:100%%;padding:10px;margin:6px 0 14px 0'><option value=''>(tap here)</option>%s</select>"
        "<label>Its name (you can also type it)</label><input name=ssid autocomplete=off autocapitalize=off value=\"%s\">"
        "<label>Wi-Fi password</label><input name=pw type=password autocomplete=off>"
        "<label style='display:block;margin-bottom:14px'><input type=checkbox style='width:auto;display:inline' onclick=\"document.getElementsByName('pw')[0].type=this.checked?'text':'password'\"> Show the password</label>"
        "<button>Save and join</button></form>"
        "<p>The ESP32 keeps the password sealed: it works only on this ESP32.</p></body></html>")
DONE = ("<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Wattle setup</title>"
        "<style>body{font-family:sans-serif;max-width:420px;margin:22px auto;padding:0 14px}h2{color:#0b6f86}</style></head><body>"
        "<h2>Saved</h2><p>The ESP32 now restarts and joins <b>%s</b>. This takes about 15 seconds.</p>"
        "<p>Then join your normal Wi-Fi again with this phone and open <b>http://%s.local/</b></p>"
        "<p>If it cannot join, it opens this setup again.</p></body></html>")


def _esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def unquote(s):
    """The text of a web form field: + is a space, %XX is a byte (UTF-8)."""
    s = s.replace("+", " ")
    out = bytearray()
    i = 0
    while i < len(s):
        if s[i] == "%" and i + 2 < len(s) + 0 and i + 3 <= len(s):
            try:
                out.append(int(s[i + 1:i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        out.extend(s[i].encode())
        i += 1
    return out.decode()


def form(body):
    """'ssid=My+Wifi&pw=abc%21' -> {'ssid': 'My Wifi', 'pw': 'abc!'}"""
    d = {}
    for part in body.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            d[unquote(k)] = unquote(v)
    return d


def dns_answer(data):
    """The reply of a tiny DNS server that sends every name to this ESP32: this is what makes a phone offer 'Sign in to network'."""
    if len(data) < 17:
        return None
    i = 12
    while i < len(data) and data[i] != 0:
        i += data[i] + 1
    question = data[12:i + 5]
    return (data[:2] + b"\x81\x80" + data[4:6] + data[4:6] + b"\x00\x00\x00\x00" + question
            + b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04" + bytes((192, 168, 4, 1)))


def save(ssid, password):
    import wifi_cipher
    text = ssid + "\n" + password + "\n"
    f = open("wifi.dat", "w")
    f.write(wifi_cipher.seal(text) + "\n")
    f.close()


def run(reason=""):
    import machine
    import network
    import wnet
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    try:
        sta.disconnect()                 # after a failed join the radio is still searching for that Wi-Fi, and that makes our own network flicker
    except Exception:
        pass
    try:
        nets = sorted({(n[0].decode(), n[3]) for n in sta.scan() if n[0]}, key=lambda t: -t[1])
    except Exception:
        nets = []
    names = []
    for n, _ in nets:
        if n not in names:
            names.append(n)
    options = "".join("<option value=\"%s\">%s</option>" % (_esc(n), _esc(n)) for n in names[:20])
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    mac = ap.config("mac")
    ssid = "Wattle-%02X%02X" % (mac[4], mac[5])
    try:
        ap.config(ssid=ssid, security=0)
    except Exception:
        ap.config(essid=ssid, authmode=0)
    ap.ifconfig((IP, "255.255.255.0", IP, IP))
    wnet.log("Wi-Fi setup open as %s (%s)" % (ssid, reason))
    print("Wi-Fi setup: join the network", ssid, "with a phone")
    web = socket.socket()
    web.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    web.bind(("0.0.0.0", 80))
    web.listen(2)
    web.settimeout(0.1)
    dns = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dns.bind(("0.0.0.0", 53))
    dns.settimeout(0.01)
    try:
        wdt = machine.WDT(timeout=30000)
    except Exception:
        wdt = None
    note = "<p class=note>%s</p>" % _esc(reason) if reason else "<p>Choose your Wi-Fi, type its password, and tap <b>Save and join</b>.</p>"
    last = wnet.SSID if hasattr(wnet, "SSID") else ""
    deadline = time.ticks_add(time.ticks_ms(), MINUTES * 60000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if wdt:
            wdt.feed()
        try:
            data, addr = dns.recvfrom(300)
            answer = dns_answer(data)
            if answer:
                dns.sendto(answer, addr)
        except OSError:
            pass
        try:
            c, _ = web.accept()
        except OSError:
            continue
        try:
            more_time = time.ticks_add(time.ticks_ms(), EXTRA * 60000)           # somebody is there: wait for him
            if time.ticks_diff(more_time, deadline) > 0:
                deadline = more_time
            c.settimeout(2)
            req = c.recv(1500)
            head, _, body = req.partition(b"\r\n\r\n")
            line = head.split(b"\r\n")[0].decode()
            method, path = line.split(" ")[0], line.split(" ")[1]
            length = 0
            for h in head.split(b"\r\n")[1:]:
                if h.lower().startswith(b"content-length:"):
                    length = int(h.split(b":")[1])
            while len(body) < length:
                more = c.recv(400)
                if not more:
                    break
                body += more
            if method == "POST" and path == "/save":
                f = form(body.decode())
                if f.get("ssid"):
                    save(f["ssid"], f.get("pw", ""))
                    c.send(b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n" + (DONE % (_esc(f["ssid"]), wnet.NAME)).encode())
                    c.close()
                    wnet.log("Wi-Fi setup: saved the Wi-Fi %s" % f["ssid"])
                    time.sleep(2)
                    machine.reset()
                page = PAGE % ("<p class=note>Please choose or type the name of your Wi-Fi.</p>", options, "")
            elif path == "/" or path.startswith("/?"):
                page = PAGE % (note, options, _esc(last))
            else:                                           # any other address (the phone's check for a "sign in" page): lead to the form
                c.send(b"HTTP/1.0 302 Found\r\nLocation: http://" + IP.encode() + b"/\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                c.close()
                continue
            c.send(b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n" + page.encode())
        except OSError:
            pass
        finally:
            try:
                c.close()
            except OSError:
                pass
    wnet.log("Wi-Fi setup: nobody finished, restarting")
    machine.reset()
