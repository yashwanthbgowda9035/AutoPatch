@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run START_AUTOPATCH.bat first to create .venv.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r "backend\requirements-dev.txt"
if errorlevel 1 (
  echo Unable to install development test dependencies.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pytest backend\tests -v
pause
