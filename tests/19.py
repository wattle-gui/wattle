# Test 19 -- how slow can the touch interval be? The interval changes by itself every 5 seconds;
# tap as fast as you can and compare the number of hits that are recognised.
# run(poll_ms=N) / set_poll_ms(N) = how often the screen is checked for a touch.
import Runtime
Runtime.LOW_POWER = True          # sleep between checks (this is where a long interval saves power)

from Runtime import *

delays = (50, 100, 150, 250, 400, 600, 1000, 1500)
step = 0
hits = 0
results = ""

def button1_click():
    global hits
    hits += 1
    label2.text = "hits: %d" % hits

def next_delay():                 # called every 5 seconds
    global step, hits, results
    results += "%d ms: %d hits\n" % (delays[step], hits)
    memo1.text = "results (hits per 5 s):\n" + results
    step = (step + 1) % len(delays)
    set_poll_ms(delays[step])
    hits = 0
    label1.text = "delay: %d ms" % delays[step]
    label2.text = "hits: 0"

every(5000, next_delay)
run(poll_ms=delays[0])
