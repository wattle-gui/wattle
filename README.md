# Wattle

**Version 0.10**

**Touch-screen apps for the ESP32: you draw them, you do not program them.**

## START HERE: read the manual

**Download the manual for your computer, and follow it from the first page.** It takes you from the download to your first app, one step at a time.

- **[Manual for Windows](https://github.com/wattle-gui/wattle/releases/latest/download/Wattle_manual_windows_0.10.zip)** (unpack it, then open `getting_started.html`)
- **[Manual for Linux](https://github.com/wattle-gui/wattle/releases/latest/download/Wattle_manual_linux_0.10.zip)** (unpack it, then open `getting_started.html`)

The manual's first chapter explains what Wattle is, and chapter 2 installs it. You do not need anything else from this page.

> **What Wattle supports today:** the **CYD** (*Cheap Yellow Display*: an ESP32 with its own 2.8-inch touch screen) and the **browser version** (any ESP32 with Wi-Fi, with a phone, tablet or computer as its screen).
> **Planned, with no date yet:** two ESP32-S3 touch-screen boards: a 2.8-inch ESP32-S3 display with capacitive touch, and the Waveshare ESP32-S3-Touch-LCD-2.8.

## What it is

You draw your screens in the **Wattle Editor**, write a short MicroPython script that says what your app *does*, and put both on the ESP32. Wattle draws the screens, watches the touches and calls your functions. You write no drawing code and no touch code.

## Free to use

Wattle is free, under the **MIT licence**: you may use it, study it, change it, share it and even sell it, for any purpose. The one
condition is that the copyright notice stays with it (that is how everyone who contributed is acknowledged). The full text is in
[LICENSE](LICENSE). Parts made by others keep their own licences: see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## What is where

- `Runtime.py` (and `Runtime.mpy`, the precompiled copy): the program that runs on the board. The other board files next to it are the display and touch drivers, `board_cyd.py`, `main.py` and `wifi_cipher.py`.
- `Editor/`: the Editor, where you draw your designs.
- `tools/`: the helper scripts that run on your computer (`./wattle` starts them for you).
- `fonts/`, `hardware/`, `hello_demo/`: the typefaces, the list of supported hardware, and the demo that is put on the board.
- `tests/`: numbered example apps, which are also the manual's working examples.

## What you get

- 16 widgets: label, button, memo, switch, checkbox, slider, progressbar, image, line, keyboard, choice, tree,
  gauge, stepper, waveform (a moving trace, like a slow oscilloscope) and barchart
- several screens, timers, pop-up messages, saved settings, landscape and portrait
- six typefaces (Arial, Times New Roman, Comic Sans MS and three DejaVu fonts, in free look-alike versions), pictures
- screen brightness, screen saver, the BOOT button as a power button
- Wi-Fi and the real time from the internet (NTP)
- error messages on the display, and a checker that explains syntax errors and misspelt names
- a low-power mode for battery use
- numbered tests (`tests/`) that double as the manual's working examples, and a record of the results (`tests/RESULTS.md`)

## The manuals

Each manual download holds three manuals, as web pages with pictures:

- **Getting Started**: everything needed to install Wattle, design your screens in the Editor and write your script.
- **Reference Manual**: every property of every widget, the design file in full, the tools, the hardware, and the test results.
- **Just in Case**: the installation details and extra help.

The technical reference for the internals is `SYSTEM_README.md`.

## What comes next

Version 0.10 works with the CYD and with the browser version, on **Linux** (a package, `wattle_0.10_all.deb`) and **Windows 10** (a Setup program, `Wattle-Setup-0.10.exe`). The two ESP32-S3 touch-screen boards above are planned. The manual tells you everything about installing.

## Credits

Created by **Bob Stanton** together with **Claude** (Claude Code, by Anthropic).
Thanks to the authors of MicroPython, mpremote, esptool, Pillow, PyQt6 and the font projects listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and to everybody who shares software freely.

## No warranty

The software is provided as it is, without any warranty (see the licence). Use it at your own risk.
