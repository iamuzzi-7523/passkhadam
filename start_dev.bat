@echo off
setlocal
title PASSKHADAM Platform Launcher

echo ========================================================
echo        Starting PASSKHADAM Platform (Dev Mode)
echo ========================================================
echo.

:: Check if frontend node_modules exists
if not exist "%~dp0frontend\node_modules\" (
    echo [NOTICE] frontend\node_modules not found.
    echo Running one-time setup...
    call "%~dp0setup.bat"
)

echo [1/2] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "PassKhadam Backend (FastAPI)" cmd /k "cd /d "%~dp0backend" && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 /nobreak > nul

echo [2/2] Starting Vite Frontend on http://127.0.0.1:5173 ...
start "PassKhadam Frontend (Vite/React)" cmd /k "cd /d "%~dp0frontend" && npm run dev"

timeout /t 2 /nobreak > nul

echo.
echo ========================================================
echo PASSKHADAM is running!
echo - Web App:      http://127.0.0.1:5173
echo - API Docs:     http://127.0.0.1:8000/docs
echo.
echo Pre-seeded Demo Accounts (Password: passkhadam123):
echo - Worker:       worker@passkhadam.org
echo - Employer:     employer@apexinfra.com
echo - Government:   gov@maharashtra.gov.in
echo - Admin:        admin@passkhadam.org
echo - Aadhaar:      authority@uidai.gov.in
echo ========================================================
echo.

start http://127.0.0.1:5173
