@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo PASSKHADAM - Standalone Portable Windows Executable Builder
echo =====================================================================
echo.

cd /d "%~dp0frontend"
if not exist "package.json" (
    echo [ERROR] frontend/package.json not found!
    pause
    exit /b 1
)

echo [1/3] Checking Node.js environment...
where node >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js is required to package the desktop application.
    echo Please install Node.js 18+ from https://nodejs.org/
    pause
    exit /b 1
)

echo [2/3] Checking and installing dependencies...
if not exist "node_modules" (
    echo Installing npm dependencies...
    call npm install
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install npm dependencies.
        pause
        exit /b 1
    )
)

echo [3/3] Compiling React bundle and building standalone Windows executable...
call npm run dist:win:portable
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to build portable executable.
    pause
    exit /b 1
)

echo.
echo =====================================================================
echo [SUCCESS] PassKhadam Portable Executable Built Successfully!
echo Artifact Path:
echo %~dp0frontend\dist-electron\PassKhadam-Portable-0.2.0.exe
echo =====================================================================
echo.
pause
