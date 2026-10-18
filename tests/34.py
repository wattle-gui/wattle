# Test 34 -- a miniature "scope" with no hardware: the script makes a sine wave (plus a little noise) and the waveform
# draws it. The slider sets the frequency. With a real input, replace the maths by  waveform1.add(adc.read()).
import math, random
from Runtime import *

phase = 0.0
freq = 3                                 # waves per 100 values

def slider1_changed(value):
    global freq
    freq = value

def sample():
    global phase
    phase += freq * 0.0628               # 2 * pi / 100
    waveform1.add(50 + 40 * math.sin(phase) + random.randint(-3, 3))

def button1_click():
    waveform1.clear()

every(20, sample)
run()
