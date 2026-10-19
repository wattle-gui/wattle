@echo off
rem wattle.cmd -- the Wattle command for Windows. It runs wattle.py with the Python that came with Wattle.
set PYTHONUTF8=1
"%~dp0python\python.exe" "%~dp0wattle.py" %*
