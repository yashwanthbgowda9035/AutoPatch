@echo off
setlocal EnableExtensions
cd /d "%~dp0"
where docker >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Docker Desktop is required. Install/start it first.
  exit /b 1
)
echo [AutoPatch] Safe container preview: http://127.0.0.1:8016
echo [INFO] This preview disables Docker code execution, GitHub publishing and external AI calls.
docker compose up --build
exit /b %ERRORLEVEL%
