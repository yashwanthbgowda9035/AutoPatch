@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Run SETUP_VSCODE.bat first.
  exit /b 1
)
set "AUTOPATCH_PUBLIC_DEMO=0"
set "AUTOPATCH_ALLOWED_HOSTS=localhost,127.0.0.1,testserver"
echo.
echo [AutoPatch] Local development server: http://127.0.0.1:8015
echo Press Ctrl+C to stop. Start Docker Desktop for isolated execution.
".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8015 --reload
exit /b %ERRORLEVEL%
