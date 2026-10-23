@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo  PASSKHADAM — Automated GitHub Repository Sync
echo =====================================================================
echo.

cd /d "%~dp0"

:: 1. Ensure Git is installed
where git >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Git is not installed or not in PATH!
    pause
    exit /b 1
)

:: 2. Set repository author to pass GitHub privacy constraints
git config user.name "Mohammed Uzair"
git config user.email "iamuzzi-7523@users.noreply.github.com"

:: 3. Custom commit message or default timestamped message
set COMMIT_MSG=%*
if "%COMMIT_MSG%"=="" (
    for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c-%%a-%%b)
    for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a:%%b)
    set COMMIT_MSG=Update PassKhadam system development - !mydate! !mytime!
)

echo [1/4] Checking repository status...
git status --short

echo.
echo [2/4] Staging tracked and untracked development files...
git add -A

echo.
echo [3/4] Committing changes with message: "%COMMIT_MSG%"...
git commit -m "%COMMIT_MSG%"
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] No changes to commit or commit already up to date.
)

echo.
echo [4/4] Pushing changes to GitHub origin main...
git push origin main
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Git push failed. Please check your network connection and git credentials.
    pause
    exit /b 1
)

echo.
echo =====================================================================
echo [SUCCESS] PassKhadam repository successfully synchronized with GitHub!
echo =====================================================================
echo.
