# PASSKHADAM Local Development Launcher (PowerShell)
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       Starting PASSKHADAM Platform (Dev Mode)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$root = $PSScriptRoot

# Check if dependencies installed
if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "[NOTICE] Frontend dependencies not found. Running setup..." -ForegroundColor Yellow
    & "$root\setup.bat"
}

# 1. Start FastAPI Backend in a new window
Write-Host "`n[1/2] Starting FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

Start-Sleep -Seconds 3

# 2. Start Vite Frontend in a new window
Write-Host "[2/2] Starting Vite Frontend on http://127.0.0.1:5173..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"

Start-Sleep -Seconds 2

Write-Host "`n========================================================" -ForegroundColor Green
Write-Host "PASSKHADAM is live!" -ForegroundColor Green
Write-Host "- Web App:  http://127.0.0.1:5173" -ForegroundColor White
Write-Host "- API Docs: http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Pre-seeded Demo Accounts (Password: passkhadam123):" -ForegroundColor Cyan
Write-Host "  * Worker:       worker@passkhadam.org" -ForegroundColor Gray
Write-Host "  * Employer:     employer@apexinfra.com" -ForegroundColor Gray
Write-Host "  * Government:   gov@maharashtra.gov.in" -ForegroundColor Gray
Write-Host "  * Admin:        admin@passkhadam.org" -ForegroundColor Gray
Write-Host "  * Aadhaar:      authority@uidai.gov.in" -ForegroundColor Gray
Write-Host "========================================================`n" -ForegroundColor Green

Start-Process "http://127.0.0.1:5173"
