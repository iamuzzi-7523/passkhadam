#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

echo "========================================================"
echo "       Starting PASSKHADAM Platform (Dev Mode)"
echo "========================================================"
echo ""

if [ ! -d "$DIR/frontend/node_modules" ]; then
    echo "[NOTICE] frontend/node_modules not found. Running setup..."
    bash "$DIR/setup.sh"
fi

# 1. Start FastAPI Backend in background
echo "[1/2] Starting FastAPI Backend on http://127.0.0.1:8000..."
cd "$DIR/backend"
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

sleep 3

# 2. Start Vite Frontend in background
echo "[2/2] Starting Vite Frontend on http://127.0.0.1:5173..."
cd "$DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================================"
echo "PASSKHADAM is live!"
echo "- Web App:  http://127.0.0.1:5173"
echo "- API Docs: http://127.0.0.1:8000/docs"
echo ""
echo "Pre-seeded Demo Accounts (Password: passkhadam123):"
echo "  * Worker:       worker@passkhadam.org"
echo "  * Employer:     employer@apexinfra.com"
echo "  * Government:   gov@maharashtra.gov.in"
echo "  * Admin:        admin@passkhadam.org"
echo "  * Aadhaar:      authority@uidai.gov.in"
echo "========================================================"
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT TERM
wait
