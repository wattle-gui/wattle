# Test results

One row per test per board. Result: PASS / FAIL (+ what was seen).
Re-run the whole list when you port to another board (`python3 tests/run_test.py N`).

| Test | What | CYD 2.8 (ESP32, ILI9341, XPT2046) |
|---|---|---|
| 00 | label + button, tap counter | PASS (2026-10-04) |
| 01 | change colour/text from the script | PASS (2026-10-04). Colour check of greys: neutral, no correction needed |
| 02 | switch + checkbox (X marks, values) | PASS (2026-10-04) |
| 03 | sliders H+V, progress bars, live _changing callback, set .value from script | PASS (2026-10-04) — label must be wide enough for the number (H:/V: used) |
| 04 | lines (h/v/diagonal, thickness, colours) + image + tap on image (click event) | PASS (2026-10-04) |
| 05 | built-in font: sizes 8/16/24, bold, italic, alignment, clipping inside border | PASS (2026-10-04) |
| 06 | typefaces: Arial 32, Times italic, Comic bold, DejaVu x3, missing font falls back | PASS (2026-10-04) |
| 07 | two screens, Screen('id') switching, backgrounds, no leftovers | PASS (2026-10-04) |
| 08 | change a widget on a hidden screen; kept and shown later | PASS (2026-10-04) |
| 09 | full keyboard: keys, Space, Bksp, LF, scrollbar, Enter->target, Esc. (Found+fixed: memo text now starts at the top) | PASS (2026-10-04) |
| 10 | numeric keyboard: layout, one '.', '-' first only, max_length, lone '-' ignored, starts empty (found+fixed: keyboard memo cleared each time) | PASS (2026-10-04) |
| 11 | keyboard secret (*), max_length, show() return value, Esc -> None | PASS (2026-10-04) |
| 12 | keyboard events: input_event per key, enter event. (Found+fixed: a keyboard widget with events covering a button blocked its taps) | PASS (2026-10-04) |
| 13 | keyboard stays open (hide_on_enter false): Enter sends+clears, Esc returns last text | PASS (2026-10-04) |
| 14 | touch reaches all four screen corners | PASS (2026-10-04) |
| 15 | enabled=false and visible=false ignore taps; script can show/hide/enable; hide erases and redraws what was behind. (Found+fixed: hiding used to leave the widget on screen) | PASS (2026-10-04) |
| 16 | periodic tasks: every(ms, fn) / stop(fn); taps still respond | PASS (2026-10-04) |
| overnight | board left running test 16 for ~18 hours: no freeze, no crash, taps still answered (label showed only 3 of 5 digits - too narrow) | PASS (2026-10-05) |
| 17 | image scaling: fit+transparent, fit, fill, stretch; screen-colour padding | PASS (2026-10-05) |
| 18 | LOW_POWER (lightsleep) with tasks and taps, 1000 ms clock | PASS (2026-10-05) |
| 18 | LOW_POWER with tasks and taps; every(500) fine | PASS (2026-10-05) |
| 18b | every(1500) also fine | PASS (2026-10-05) |
| 19 | touch interval: run(poll_ms) / set_poll_ms(); sweep while tapping fast (subjective). Hits per 5 s: 50ms=5, 100=7, 150=3, 250=4, 400=2, 600=3, 1000=1 | PASS (2026-10-05) — default 150 ms is a good middle |
| 20 | radio groups, vertical + horizontal, changed event with item number, only 2 items redrawn per tap, set .selected from script | PASS (2026-10-05) |
| 21 | dropdown: field+arrow, list opens below/above, inverted current, scroll, outside tap cancels, widgets underneath restored, list starts at first item. Designer idea: '*' marks the default item in the item editor | PASS (2026-10-05) |
| 22 | tree menu: 3 levels, + / - parents, 3-char indent, inverted selection, text-path event, scroll bar, partial redraws | PASS (2026-10-05) |
| E20 | radio groups built in the Editor (TEST_20.json): all 5 widgets same properties as mine; horizontal group has no event -> moves its dot but sends nothing. Found+fixed: interactive widgets now react to touch even with an empty events list | PASS (2026-10-06) |
| E21 | dropdowns built in the Editor (TEST_21.json): same properties as mine (texts differ only by typos); list opens below/above, pick, cancel, scroll, button under the list restored | PASS (2026-10-06) |
| E22 | tree built in the Editor (TEST_22.json, 304x224, font 16): opens/closes/selects, 3-char indent, scroll bar. Found+fixed: closing a branch while scrolled did not redraw fully | PASS (2026-10-06) |
| 02 (regression) | switch + checkbox after the events/touch rule change | PASS (2026-10-06) |
| 03 (regression) | sliders + progress bars + live _changing after the touch rule change | PASS (2026-10-06) |
| 20 (regression) | radio groups with events after the touch rule change | PASS (2026-10-06) |
| 21 (regression) | dropdowns after the touch rule change | PASS (2026-10-06) |
| 22 (regression) | tree menu after the touch rule change and the scroll fix; Pick WiFi opens the branch | PASS (2026-10-06) |
| power-up | board started from a power bank/charger with no computer: project runs by itself | PASS (2026-10-06) |
| E23 | PORTRAIT screen 240x320 built in the Editor (PORT1.json): picture upright with USB at the bottom (PORTRAIT_ROTATION=180), four corner buttons + slider hit correctly after calibrate_touch.py | PASS (2026-10-06) |
| 23 | errors shown on the screen: handler, periodic task; title centred, 12 px mono text, breaks at spaces only, all white | PASS (2026-10-07) |
| 24 | message(): one, two and three buttons, long wrapped text, box removed and screen restored | PASS (2026-10-07) |
| 23 | (final wording) error screen: place of the error in words, line number at the end of a syntax error message, hint to run check_script.py | PASS (2026-10-07) |
| 25 | save() / load(): the count survives a restart; Clear resets it | PASS (2026-10-07) |
| 00 (regression) | label + button after the error-handling changes | PASS (2026-10-07) |
| 03 (regression) | sliders + bars + live callback after the error-handling changes | PASS (2026-10-07) |
| 16 (regression) | periodic tasks, stop/start, taps while running, after the error-handling changes | PASS (2026-10-07) |
| 21 (regression) | dropdowns after the error-handling changes | PASS (2026-10-07) |
| 22 (regression) | tree menu after the error-handling changes. Note: with many rows open, rows outside the view need the scroll bar (one row per tap) | PASS (2026-10-07) |
| 22 (scroll bar) | tree scroll bar: ends = one row, middle = jump to that place | PASS (2026-10-07) |
| 21 (scroll bar) | drop-down scroll bar (bottom list, 7 items): ends = one row, middle = jump | PASS (2026-10-07) |
| 09 (scroll bar) | keyboard memo scroll bar: ends = one line, middle = jump | PASS (2026-10-07) |
| 26 | error while the script starts (NameError): centred title, name only, place in words, capital hint, blank line below | PASS (2026-10-07) |
| 27 | syntax error at start-up: red screen with (line 6); check_script.py names the cause (expected ':') | PASS (2026-10-07) |
| 28 | backlight(percent), blank with 0, screensaver(seconds, dim), a waking touch is not a click, BOOT button wakes / blanks (power_button) | PASS (2026-10-07) |
| 29 | long press (an experiment): widgets listing longpress get <id>_longpress() after a ~0.7 s hold; a tap still clicks | PASS WITH CAUTION (2026-10-07): works, but not as reliable as a tap on the resistive panel; for convenience actions only |
| 30 | Wi-Fi and real time: wifi() reads name/password from ID.dat lines 5-6 (never shown), ntp() sets the clock, timezone(h) + now() give local time, wifi_off(); set_longpress_ms(ms) added | PASS (2026-10-07) |
| 32 | waveform (style bars, update_ms) and stationary barchart (set / clear); only the plot area is redrawn; chart drawing in framebuffer bands (~45 ms); colour names orange, purple, pink, brown, grey added | PASS (2026-10-07) |
| 33 | stationary barchart filled from the design (values, labels, show_values): rainfall 2021-2025; text size follows font_size | PASS (2026-10-07) |
| 34 | miniature scope: waveform fed by a script-made sine wave, frequency slider, Clear; stays smooth while the slider is used | PASS (2026-10-07) |
| 35 | big gauge with + / -: needle-only update, circle and tick marks stay closed; ticks default 10, scale 0 at the lower left | PASS (2026-10-07) |
| 31 | gauge (270 deg dial, needle-only update), stepper (- / +, limits, changed event), waveform (line, Clear / Add noise), half-circle gauge | PASS (2026-10-07) |
| 36 | the Editor-saved MASTER_cursor.json (byte-identical to MASTER.json): master_displays screen; stepper drives gauge and waveform from the script | PASS (2026-10-07) |
| 37 | STRESS TEST: 3 screens full of widgets (gauges, waveforms, bar charts, progress bars, stepper, clock), timers about 10 times a second, a screen change every 15 s | PASS (2026-10-14), with a caution. Ran 12 h 28 min unattended on one board (log: tests/37_overnight_2026-10-13_log.txt): 0 errors, 0 MemoryErrors, 1 start only (no watchdog reset), 250,740 timer runs, 2,979 screen changes, no timer ever stalled (longest gap 1 s); free memory flat at about 69 KB, allocated memory flat. HISTORY: the first overnight runs FAILED and found two real faults that were fixed before release: (1) gauge and chart drawing allocated a new buffer on every update (MemoryError after hours); (2) display.clear() allocated a 5120-byte line on every screen change (MemoryError on about 9 of 10 screen changes after 2 minutes). UNSOLVED POSSIBILITY: the largest free block (probed once a minute) fell from about 12 KB at start to 2-4 KB within the first hours and then stayed there (no further fall in the remaining 8 hours). So memory is fragmented but stable. A single allocation larger than a few KB (a big picture, a big font loaded for the first time, a long message box) could in principle still fail with a MemoryError after a long run. Test 37 does not use pictures, the keyboard, pop-up messages or large fonts, and it was run on one board only; a longer run (days) and a run that includes those features have NOT been done. |
| 38 | STRESS TEST 2: four large pictures redrawn at every screen change, big fonts in four typefaces, a gauge and a waveform, and every 50 s a pop-up message and the keyboard operated by a scripted 'finger' (answers are checked) | IN PROGRESS (2026-10-14). The first version FAILED within minutes and found a real fault (ili9341.draw_image allocated a new 7.7 KB bytes object per strip -> MemoryError), fixed by reading into the driver's scratch buffer. After the fix: 14:59-16:46, two runs of 1.05 h and 0.67 h (each ended by an interruption, not a fault: the second start line says WDT reset), together 123 pop-ups and 123 typed entries ALL CORRECT, 0 errors, largest free block steady at 8-12 KB (log: tests/38_runs_2026-10-14_log.txt). OVERNIGHT RUN PASSED (2026-10-14 17:29 to 2026-10-15 about 11:40): 65 371 s = 18 h 9 min, ONE start line (power-on), 0 errors, 0 failed checks, 1 307 pop-up answers and 1 307 keyboard entries ALL CORRECT (1 307/1 307 each), 3 922 screen changes, 527 252 timer runs, free memory steady at 62-72 KB, largest free block 12 KB (8 KB at times), never lower (log: tests/38_overnight_2026-10-14_log.txt). Limits: one board, one fixed workload. |
| 39 (re-run of 38) | same stress workload with the shared font buffers; board on the powered USB hub, desktop off | PASS (2026-10-16): 11 h 12 min (40 350 s), one BOOT (power-on), 0 errors, 806/806 pop-ups and keyboard entries correct, free 69-79 KB, largest block 8-12 KB. Log: tests/39_overnight_2026-10-15_log.txt. One board, fixed workload. |
| wifi_pick (extra) | Pick WiFi: scan, dropdown of networks, secret keyboard, connect | PASS (2026-10-16, Bob's own finger on #51): Scan, list, keyboard and the connect step all behaved as described. The password is never shown or stored. |
| 40 (stress test 3) | test 38 plus a slider that moves ten times a second (the new round-knob slider), board on the powered hub | PASS (2026-10-17): 12 h 54 min (46 473 s), one BOOT (power-on), 0 errors, 927/927 pop-ups and keyboard entries correct, free 68-79 KB, largest block 8-12 KB. Log: tests/40_overnight_2026-10-16_log.txt. One board, fixed workload. |
| E25 | design made in the Editor from the E24 recipe (gauge, stepper, waveform, barchart): key order and types as specified; all widgets work on the board. KNOWN EDITOR BUGS (for Cursor): the list fields "Text under the bars" and "Bar heights" took no input (lists added by hand for the test) | PASS WITH EDITOR BUGS (2026-10-08) |
| E26 | the same design made in the Editor after Cursor fixed the two list fields (labels and values typed in the Editor, no hand editing): gauge at 40, barchart with years and numbers, stepper moves the gauge and adds values to the waveform | PASS (2026-10-08) |
