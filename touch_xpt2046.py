# touch_xpt2046.py -- resistive touch driver (XPT2046 / ADS7843 family).
# Touch driver interface used by Runtime.py:
#   pressed()  -> True while the screen is touched
#   read()     -> (x, y) in screen pixels, or None if not touched

from machine import Pin, SPI


class XPT2046:

    def __init__(self, sck, mosi, miso, cs, irq, cal, width, height):

        self.spi = SPI(2, baudrate=1000000, polarity=0, phase=0,
                       sck=Pin(sck), mosi=Pin(mosi), miso=Pin(miso))
        self.cs = Pin(cs, Pin.OUT, value=1)
        self.irq_pin = Pin(irq, Pin.IN)
        self.cal = cal
        self.width = width
        self.height = height

    def pressed(self):
        return self.irq_pin.value() == 0

    def _command(self, c):

        tx = bytearray([c, 0, 0])
        rx = bytearray(3)

        self.cs.value(0)
        self.spi.write_readinto(tx, rx)
        self.cs.value(1)

        return (rx[1] << 4) | (rx[2] >> 4)

    def raw(self):
        """Raw (x, y) readings of the panel, or None if not touched. Used for calibration."""
        if self.irq_pin.value() != 0:
            return None
        return (self._command(0xD0), self._command(0x90))

    def read(self):

        r = self.raw()
        if r is None:
            return None
        rx, ry = r

        a, b, c, d, e, f = self.cal

        x = int(a * rx + b * ry + c)
        y = int(d * rx + e * ry + f)

        return (max(0, min(self.width - 1, x)),
                max(0, min(self.height - 1, y)))
