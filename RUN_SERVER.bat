@echo off
cd /d "%~dp0"
title AutoPatch Velocity - Python Backend
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment missing. Run START_AUTOPATCH.bat first.
  pause
  exit /b 1
)
echo.
echo AutoPatch dashboard: http://127.0.0.1:8015
echo FastAPI docs:        http://127.0.0.1:8015/docs
echo Press Ctrl+C in this window to stop the backend.
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8015
if errorlevel 1 (
  echo.
  echo The backend stopped with an error. See messages above.
  pause
)
