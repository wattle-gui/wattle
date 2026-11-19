# phone_test.py -- tries the phone commands: phone.vibrate(), phone.beep(), phone.speak(), phone.stay_awake(), and the phone's size.
import time
from Runtime import *

awake = False
alarm_at = 0


def show_size():
    label1.text = "Size: %d x %d\nlandscape: %s\npixel ratio: %.2f" % (phone.width, phone.height, phone.landscape, phone.dpr)


def phone_resized():                    # called by the Runtime when the phone reports a new size (rotation, browser resize)
    show_size()


def button1_click():
    phone.vibrate(300)


def button2_click():
    phone.beep(880, 300)


def button3_click():
    phone.speak("The core temperature is too high")


def button4_click():
    global awake
    awake = not awake
    phone.stay_awake(awake)
    button4.text = "Stay awake: " + ("ON" if awake else "off")


def button5_click():
    global alarm_at
    alarm_at = time.ticks_add(time.ticks_ms(), 10000)
    label2.text = "Alarm set. Do not touch."


full = False


def button6_click():
    global full
    full = not full
    phone.fullscreen(full)              # on: the page goes full screen on the next tap; off: leaves full screen at once
    label2.text = "Tap anywhere to go full screen" if full else "Full screen off"


def check():
    global alarm_at
    if alarm_at and time.ticks_diff(time.ticks_ms(), alarm_at) >= 0:
        alarm_at = 0
        label2.text = "ALARM!"
        phone.vibrate(500)
        phone.beep(1000, 500)
        phone.speak("Alarm. The core temperature is too high")


every(500, check)
run()
