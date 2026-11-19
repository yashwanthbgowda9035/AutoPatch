@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo.
echo [AutoPatch] Setting up VS Code Python environment...
where py >nul 2>&1
if not errorlevel 1 (
  set "PY=py -3"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Python 3.10+ not found. Install Python and reopen VS Code.
    exit /b 1
  )
  set "PY=python"
)
if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r backend\requirements-dev.txt
if errorlevel 1 exit /b 1
echo.
echo [PASS] VS Code environment is ready.
echo Select .venv\Scripts\python.exe in VS Code if prompted.
echo Press F5 to debug or run RUN_VSCODE.bat in the terminal.
exit /b 0
