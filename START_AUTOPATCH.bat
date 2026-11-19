@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title AutoPatch Velocity - Setup
color 07
echo.
echo  ====================================================
echo    AUTOPATCH VELOCITY - KINETIC CODE + CAREER
 echo  ====================================================
echo.
echo [1/4] Checking Python 3...
where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_COMMAND=py -3"
) else (
    where python >nul 2>&1
    if errorlevel 1 goto no_python
    set "PYTHON_COMMAND=python"
)
%PYTHON_COMMAND% --version
if errorlevel 1 goto no_python

echo.
echo [2/4] Creating virtual environment if required...
if not exist ".venv\Scripts\python.exe" (
    %PYTHON_COMMAND% -m venv ".venv"
    if errorlevel 1 goto setup_failed
)

echo.
echo [3/4] Installing backend dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "backend\requirements.txt"
if errorlevel 1 goto setup_failed

echo.
echo [4/4] Checking local port 8015...
".venv\Scripts\python.exe" -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(1 if s.connect_ex(('127.0.0.1',8015)) == 0 else 0)"
if errorlevel 1 goto port_busy
echo Launching server and dashboard...
start "AutoPatch Velocity Backend" "%~dp0RUN_SERVER.bat"
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8015"
echo.
echo  Dashboard: http://127.0.0.1:8015
echo  API docs:  http://127.0.0.1:8015/docs
echo  Keep the AutoPatch Backend window open while you use the dashboard.
echo.
pause
exit /b 0

:port_busy
echo.
echo [ERROR] Port 8015 is already occupied by another application.
echo Stop the previous AutoPatch backend terminal with Ctrl+C, then rerun this launcher.
echo To locate it: netstat -ano ^| findstr :8015
pause
exit /b 1

:no_python
echo.
echo [ERROR] Python 3 was not found. Install Python 3.10+ from python.org.
echo During setup choose "Add Python to PATH", then rerun this launcher.
pause
exit /b 1

:setup_failed
echo.
echo [ERROR] Setup failed. Check your network and Python version.
echo Manual instructions are in README.md.
pause
exit /b 1
