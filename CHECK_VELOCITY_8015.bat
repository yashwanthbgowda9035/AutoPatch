@echo off
curl.exe --silent --max-time 8 http://127.0.0.1:8015/ | findstr /C:"AutoPatch // VELOCITY" >nul
if errorlevel 1 ( echo [NOT READY] Velocity 5.6 is not running on port 8015. & exit /b 1 )
echo [OK] AutoPatch Velocity 5.6 is running at http://127.0.0.1:8015/
