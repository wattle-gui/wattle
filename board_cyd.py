# board_cyd.py -- board profile: "CYD" 2.8" (ESP32 + ILI9341 + XPT2046).
# Everything that is specific to this hardware lives here (pins, buses,
# rotation, calibration, which drivers). Runtime.py only calls
# make_display() / make_touch(). To support another board, copy this file.

from machine import Pin, SPI, PWM

NAME = "CYD 2.8 (ESP32 + ILI9341 + XPT2046)"

# Touch calibration for the resistive panel: screen x/y from raw readings,
#   x = a*rx + b*ry + c      y = d*rx + e*ry + f
TOUCH_CAL = (0, -0.191388, 335.215332, -0.129870, 0, 248.181824)           # landscape 320 x 240
TOUCH_CAL_PORTRAIT = (-0.13279, -0.000844, 251.9116, -0.002118, 0.186733, -11.6882)  # portrait 240 x 320: run calibrate_touch.py

PORTRAIT_ROTATION = 180       # 0 or 180: which way up the picture is when the design is portrait


BUTTON_PIN = 0              # the BOOT button on the back (pressed = 0); RESET cannot be used by software

_backlight = None


def set_backlight(percent):
    """Brightness of the display backlight, 0 (off) to 100 (full)."""
    if _backlight is not None:
        _backlight.duty_u16(65535 * max(0, min(100, int(percent))) // 100)


def make_display(width, height):
    """Returns a display object with fill_rectangle(), block(), clear(),
    draw_line(), draw_image() (the ili9341.Display interface)."""

    import ili9341

    spi = SPI(1, baudrate=40000000, polarity=0, phase=0,
              sck=Pin(14), mosi=Pin(13), miso=Pin(12))

    display = ili9341.Display(spi, cs=Pin(15), dc=Pin(2), rst=Pin(4),
                              width=width, height=height,
                              rotation=PORTRAIT_ROTATION if height > width else 90)

    global _backlight
    _backlight = PWM(Pin(21), freq=1000, duty_u16=65535)       # backlight, full brightness

    return display


def make_touch(width, height):
    """Returns a touch object with pressed() and read() -> (x, y) | None."""

    import touch_xpt2046

    return touch_xpt2046.XPT2046(sck=25, mosi=32, miso=39, cs=33, irq=36,
                                 cal=TOUCH_CAL_PORTRAIT if height > width else TOUCH_CAL,
                                 width=width, height=height)
