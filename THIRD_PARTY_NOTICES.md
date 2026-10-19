# Third-party notices

Wattle uses, or was made with, the following. Each keeps its own licence. This list is written in good faith;
if you notice a mistake or a missing credit, please say so and it will be corrected.

## Software that runs with the system (not included in the package)

| Component | Used for | Licence |
|---|---|---|
| [MicroPython](https://micropython.org) (firmware, `mpy-cross`, `mpremote`) | the language on the board; copying files; the precompiled `.mpy` files | MIT |
| [esptool](https://github.com/espressif/esptool) | flashing the firmware | GPL-2.0-or-later |
| [Pillow](https://python-pillow.org) | converting pictures and fonts on the computer | HPND (Pillow licence) |
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | the Wattle Editor and the hardware picker window | GPL-3.0 or a commercial licence |
| [pyserial](https://github.com/pyserial/pyserial) | stopping and restarting the board over its serial port | BSD-3-Clause |

These are installed separately by the installer (`pip install ...`); nothing of them is copied into this package. Wattle itself is MIT-licensed, which is compatible with the GPL; PyQt6 is not part of this package. A possible later change
is the LGPL alternative PySide6 for the Editor.

## Source files in the package that were not written for this project

| File | What is known |
|---|---|
| `ili9341.py` (display driver) | Based on [micropython-ili9341](https://github.com/rdagger/micropython-ili9341) by rdagger, **MIT licence**, "Copyright (c) 2020" (the licence text is reproduced below). Modified for this project: one reusable transfer buffer and larger blocks, so that redrawing does not fragment the board's memory. |
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

## Licence text of micropython-ili9341 (for `ili9341.py`)

```
MIT License

Copyright (c) 2020

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
