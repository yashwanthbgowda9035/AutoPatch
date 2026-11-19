@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title AutoPatch - Publish Complete Project to GitHub
color 0B
echo.
echo  ==========================================================
echo      AUTOPATCH - PUSH THE COMPLETE PROJECT TO GITHUB
echo  ==========================================================
echo.
echo  This includes frontend, backend, tests, examples and docs.
echo  Local .env files, .venv and caches are ignored.
echo.
where git >nul 2>&1
if errorlevel 1 goto missing_git
if not exist ".gitignore" goto missing_ignore
if not exist "backend\app\main.py" goto wrong_folder
if not exist "frontend\index.html" goto wrong_folder

echo.
echo  Running quality checks before uploading source...
call "%~dp0RUN_QUALITY_GATE.bat"
if errorlevel 1 goto failed

echo  STEP 1 - Create an EMPTY GitHub repository named AutoPatch.
echo  Open: https://github.com/new
echo  Do NOT select Add a README, .gitignore or license there.
echo.
set /p "REPO_URL=Paste the new repository HTTPS URL here: "
if not defined REPO_URL goto no_url

echo.
echo  STEP 2 - Preparing the local Git repository...
if not exist ".git" (
    git init -b main
    if errorlevel 1 goto failed
) else (
    echo  Existing .git directory detected. It will be reused.
)

git config user.name >nul 2>&1
if errorlevel 1 goto ask_name
:check_email
git config user.email >nul 2>&1
if errorlevel 1 goto ask_email
goto stage_files
:ask_name
echo.
set /p "AUTHOR_NAME=Your name for Git commits: "
if not defined AUTHOR_NAME goto missing_identity
git config user.name "%AUTHOR_NAME%"
if errorlevel 1 goto failed
goto check_email
:ask_email
echo.
set /p "AUTHOR_EMAIL=Your GitHub email for Git commits: "
if not defined AUTHOR_EMAIL goto missing_identity
git config user.email "%AUTHOR_EMAIL%"
if errorlevel 1 goto failed
:stage_files
echo.
echo  STEP 3 - Review the files that will be uploaded:
git add -A
if errorlevel 1 goto failed
git status --short
echo.
echo  Checking staged diff for whitespace errors...
git diff --cached --check
if errorlevel 1 goto failed
echo.
echo  Check that no secrets or personal data are listed above.
choice /C YN /N /M "Continue and push these files? [Y/N]: "
if errorlevel 2 goto cancelled

git diff --cached --quiet
if errorlevel 1 (
    git commit -m "Initial AutoPatch project release"
    if errorlevel 1 goto failed
) else (
    echo  No new changes to commit.
)

set "CURRENT_REMOTE="
for /f "delims=" %%U in ('git remote get-url origin 2^>nul') do set "CURRENT_REMOTE=%%U"
if defined CURRENT_REMOTE (
    if /I not "%CURRENT_REMOTE%"=="%REPO_URL%" goto remote_conflict
    echo  Existing origin matches the requested repository.
) else (
    git remote add origin "%REPO_URL%"
    if errorlevel 1 goto failed
)

echo.
echo  STEP 4 - Pushing to GitHub...
git push -u origin main
if errorlevel 1 goto push_failed
echo.
echo  SUCCESS! Your complete AutoPatch project is on GitHub.
echo  Repository: %REPO_URL%
echo.
pause
exit /b 0

:remote_conflict
echo [ERROR] An origin remote already exists with a different URL.
git remote get-url origin
echo For safety, no remote was changed. Use Git manually if needed.
goto failed
:missing_git
echo [ERROR] Git is not installed or not on PATH.
echo Install Git for Windows from https://git-scm.com/downloads/win
echo Restart CMD after installation, then rerun this file.
goto failed
:missing_ignore
echo [ERROR] .gitignore missing. Use the complete GitHub-ready project folder.
goto failed
:wrong_folder
echo [ERROR] Project files missing. Run this batch file inside the extracted AutoPatch folder.
goto failed
:no_url
echo [ERROR] No repository URL supplied.
goto failed
:missing_identity
echo [ERROR] Git commit name/email is required.
goto failed
:push_failed
echo.
echo [ERROR] Git push failed. Common causes:
echo - Sign in to GitHub in the browser when Git Credential Manager asks.
echo - Create the repository first, with no README or other files.
echo - Confirm the repository URL and your account permissions.
echo - If you have a preexisting GitHub repo, follow README_GITHUB.md.
goto failed
:cancelled
echo Cancelled. No files were pushed.
pause
exit /b 0
:failed
echo.
pause
exit /b 1
