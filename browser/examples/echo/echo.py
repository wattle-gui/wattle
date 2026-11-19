# echo.py -- made with the Editor for the browser: type in the memo and the label counts what you typed.
from Runtime import *


def memo1_changed(text):
    label1.text = "%d characters" % len(text)


def button1_click():
    memo1.text = ""
    label1.text = "Cleared"


run()
