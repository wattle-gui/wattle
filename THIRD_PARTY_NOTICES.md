# Third-party notices

Wattle uses, or was made with, the following. Each keeps its own licence. This list is written in good faith;
if you notice a mistake or a missing credit, please say so and it will be corrected.

## Software that runs with the system (not included in the package)

| Component | Used for | Licence |
|---|---|---|
| [MicroPython](https://micropython.org) (firmware, `mpy-cross`, `mpremote`) | the language on the board; copying files; the precompiled `.mpy` files | MIT |
| [esptool](https://github.com/espressif/esptool) | flashing the firmware | GPL-2.0-or-later |
| [Pillow](https://python-pillow.org) | converting pictures and fonts on the computer | HPND (Pillow licence) |
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | the hardware picker window (`picker.py`) and the experimental screen viewer (`mirror_viewer.py`) only | GPL-3.0 or a commercial licence |
| [pyserial](https://github.com/pyserial/pyserial) | reading the board's serial port in the experimental screen viewer (`mirror_viewer.py`) only | BSD-3-Clause |

These are installed separately (`pip install ...`); nothing of them is copied into this package. Because PyQt6 is GPL, `picker.py` and `mirror_viewer.py`
are only conveniences: the system works without it (the hardware block of a design can be written by hand). A possible later change
is the LGPL alternative PySide6.

## Source files in the package that were not written for this project

| File | What is known |
|---|---|
| `ili9341.py` (display driver) | **Author and licence not recorded.** It closely resembles the open-source *micropython-ili9341* driver (MIT licence) but this has not been verified. It was modified for this project (larger transfer blocks). To be checked before the first release; if it cannot be traced it will be replaced by a driver written for this project. |
| `touch_xpt2046.py` (touch driver) | a short driver (about 50 lines) for the XPT2046 chip, written in the same session as the Runtime; no copied source is known, but this has not been formally verified. |

## Fonts

The `.fnt` files in `fonts/` are bitmap conversions made by `make_fonts.py` from these open fonts. The fonts keep their licences;
the conversions are shipped under the same terms.

| Font | Author | Licence |
|---|---|---|
| DejaVu Sans, Sans Mono, Serif | DejaVu fonts team (based on Bitstream Vera, Copyright Bitstream, Inc.) | Bitstream Vera licence and public domain changes |
| Liberation Sans, Liberation Serif | Red Hat, Inc. (Ascender / Steve Matteson design) | SIL Open Font Licence 1.1 |
| Comic Relief | Jeff Davis | SIL Open Font Licence 1.1 |

In the design files these fonts appear under the names **Arial**, **Times New Roman** and **Comic Sans MS**, because they are
metric-compatible look-alikes. Those names are trademarks of their owners; **no font of those companies is included**.
Renaming the entries (for example to "Liberation Sans") is planned.

## Other

- The 8x8 built-in font comes from the MicroPython `framebuf` module (MIT).
- The sample pictures and designs in `designs/` are test material written for this project.
