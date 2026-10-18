# board_template.py -- what a board profile (board_<name>.py) must provide. Copy it, rename it, fill it in.
# Runtime.py picks the profile with "target.board" in the design JSON, else line 2 of design.txt on the board,
# else board_cyd. Example: board_cyd.py (resistive touch, ILI9341).
NAME = "my board (processor + display chip + touch chip)"      # printed at start-up


def make_display(width, height):
    """Create, initialise and return the display. width/height = the size of the design's screens
    (portrait if height > width): choose the rotation from that. The object needs the drawing methods
    Runtime.py uses (ili9341.Display and the st7789 subclass already have them all):
        fill_rectangle(x, y, w, h, colour565)   block(x0, y0, x1, y1, bytes)   clear(colour565)
        draw_line(x1, y1, x2, y2, colour565)    draw_circle / fill_circle      draw_image(path, x, y, w, h)
        draw_text8x8(x, y, text, fg, bg)        (colour565 = 16-bit RGB565)
    Also switch the backlight on here."""
    raise NotImplementedError


def make_touch(width, height):
    """Return the touch object:
        pressed() -> True while the screen is touched (called often: keep it cheap)
        read()    -> (x, y) in SCREEN pixels (already calibrated / flipped for the orientation), or None
    A resistive panel needs a calibration (see calibrate_touch.py); a capacitive one usually only axis flips."""
    raise NotImplementedError
