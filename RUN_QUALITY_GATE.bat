@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title AutoPatch 5.6 - Quality Gate
color 0B
echo.
echo  ==================================================
echo      AUTOPATCH 5.6 - PRE-PUSH QUALITY GATE
 echo  ==================================================
echo.
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
  set "PYTHON_ARGS="
) else (
  where py >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
  ) else (
    where python >nul 2>&1
    if errorlevel 1 goto no_python
    set "PYTHON_EXE=python"
    set "PYTHON_ARGS="
  )
)
echo [1/3] Installing test dependencies...
"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install --disable-pip-version-check -r backend\requirements-dev.txt
if errorlevel 1 goto failed
echo [2/3] Running Python regression tests...
"%PYTHON_EXE%" %PYTHON_ARGS% -m pytest backend\tests -q
set "TEST_RESULT=%ERRORLEVEL%"
if not "%TEST_RESULT%"=="0" goto failed
echo [3/3] Checking frontend JavaScript syntax...
where node >nul 2>&1
if errorlevel 1 (
  echo [INFO] Node.js not installed. JS syntax check skipped locally.
  echo [INFO] GitHub Actions runs this check automatically after upload.
) else (
  for %%F in (frontend\assets\*.js) do (
    node --check "%%F"
    if errorlevel 1 goto failed
  )
)
echo.
echo [PASS] Local quality gate completed.
exit /b 0
:no_python
echo [ERROR] Python 3 not found. Install Python from https://python.org
exit /b 1
:failed
echo.
echo [FAIL] Quality gate failed. Fix errors before uploading.
exit /b 1
