@echo off
rem Opens a command window in the Wattle folder where the  wattle  command works.
cd /d "%~dp0"
set "PATH=%~dp0;%PATH%"
set PYTHONUTF8=1
echo.
echo   Wattle command window. Type  wattle help  to see what you can do.
echo.
cmd /k
