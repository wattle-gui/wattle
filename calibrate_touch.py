# calibrate_touch.py -- runs ON THE BOARD (mpremote run calibrate_touch.py), for a new orientation.
# Shows four crosses in the corners of the screen (portrait 240 x 320 unless you pass the size);
# tap each one in turn (TL, TR, BL, BR). It prints the raw readings; calibrate_fit.py (on the PC)
# turns them into the six numbers for board_cyd.py.
import time
import board_cyd

W, H = 240, 320                      # portrait; use 320, 240 for landscape
d = board_cyd.make_display(W, H)
t = board_cyd.make_touch(W, H)
d.clear(0)

targets = (("TL", 20, 20), ("TR", W - 21, 20), ("BL", 20, H - 21), ("BR", W - 21, H - 21))

def cross(x, y, c):
    d.fill_rectangle(x - 12, y - 1, 25, 3, c)
    d.fill_rectangle(x - 1, y - 12, 3, 25, c)

for name, x, y in targets:
    cross(x, y, 0xFFE0)              # all four, yellow
d.draw_text8x8(W // 2 - 60, H // 2 - 4, "tap the crosses", 0xFFFF, 0)
d.draw_text8x8(W // 2 - 60, H // 2 + 8, "TL, TR, BL, BR", 0xFFFF, 0)

for name, x, y in targets:
    cross(x, y, 0xF800)              # the one to tap now: red
    while t.raw() is None:
        time.sleep_ms(20)
    sx = sy = n = 0
    for _ in range(25):              # average about 25 readings while the finger is down
        r = t.raw()
        if r:
            sx += r[0]; sy += r[1]; n += 1
        time.sleep_ms(10)
    print("RAW", name, x, y, sx // n, sy // n)
    cross(x, y, 0x07E0)              # done: green
    while t.raw() is not None:
        time.sleep_ms(20)
    time.sleep_ms(200)

print("DONE")
