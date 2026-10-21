@echo off
setlocal enabledelayedexpansion
title PASSKHADAM - Environment Setup

echo ========================================================
echo       PASSKHADAM Portable - One-Click Setup
echo ========================================================
echo.

:: 1. Check Python
echo [1/3] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)
python --version

:: 2. Check Node.js
echo.
echo [2/3] Checking Node.js and npm...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH!
    echo Please install Node.js 18+ from https://nodejs.org/
    pause
    exit /b 1
)
node --version
npm --version

:: 3. Install Backend Dependencies
echo.
echo [3/3] Installing Python dependencies (backend)...
cd /d "%~dp0backend"
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [WARNING] Some Python dependencies may have failed to install.
)

:: 4. Install Frontend Dependencies
echo.
echo Installing Node.js dependencies (frontend)...
cd /d "%~dp0frontend"
call npm install
if %errorlevel% neq 0 (
    echo [WARNING] npm install for frontend returned an error.
)

:: 5. Install Contracts Dependencies (optional/optional Hardhat)
echo.
echo Installing Node.js dependencies (contracts)...
cd /d "%~dp0contracts"
call npm install
if %errorlevel% neq 0 (
    echo [WARNING] npm install for contracts returned an error.
)

cd /d "%~dp0"

echo.
echo ========================================================
echo      Setup Complete! You can now run start_dev.bat
echo ========================================================
echo.
pause
