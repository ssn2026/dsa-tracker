@echo off
rem Starts the DSA Tracker, setting everything up on first run.
cd /d "%~dp0"

set "PY=venv\Scripts\python.exe"

if exist "%PY%" goto run

echo Setting up for first use. This takes a minute, only happens once.
echo.

set "BOOTSTRAP="
where py >nul 2>&1
if not errorlevel 1 set "BOOTSTRAP=py -3"
if defined BOOTSTRAP goto makevenv
where python >nul 2>&1
if not errorlevel 1 set "BOOTSTRAP=python"
if defined BOOTSTRAP goto makevenv

echo Python was not found on this machine.
echo Install Python 3.12 or newer from https://www.python.org/downloads/
echo and be sure to tick "Add Python to PATH" in the installer.
echo.
pause
exit /b 1

:makevenv
%BOOTSTRAP% -m venv venv
if not exist "%PY%" goto venvfailed

"%PY%" -m pip install --upgrade pip --quiet
"%PY%" -m pip install -r requirements.txt --quiet
if errorlevel 1 goto installfailed

echo Setup complete.
echo.
goto run

:venvfailed
echo.
echo Could not create the virtual environment. See the message above.
pause
exit /b 1

:installfailed
echo.
echo Installing the dependencies failed. Check your internet connection
echo and run this file again.
pause
exit /b 1

:run
echo Starting DSA Tracker at http://localhost:8000
echo Close this window, or press Ctrl+C, to stop it.
echo.
"%PY%" app.py
pause
