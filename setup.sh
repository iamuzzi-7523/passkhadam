#!/usr/bin/env bash
set -e

echo "========================================================"
echo "      PASSKHADAM Portable - One-Click Setup"
echo "========================================================"
echo ""

# 1. Check Python
echo "[1/3] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in PATH!"
    echo "Please install Python 3.10+."
    exit 1
fi
python3 --version

# 2. Check Node.js & npm
echo ""
echo "[2/3] Checking Node.js and npm..."
if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js is not installed or not in PATH!"
    echo "Please install Node.js 18+."
    exit 1
fi
node --version
npm --version

# 3. Install Backend Dependencies
echo ""
echo "[3/3] Installing Python dependencies (backend)..."
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR/backend"
python3 -m pip install -r requirements.txt

# 4. Install Frontend Dependencies
echo ""
echo "Installing Node.js dependencies (frontend)..."
cd "$DIR/frontend"
npm install

# 5. Install Contracts Dependencies
echo ""
echo "Installing Node.js dependencies (contracts)..."
cd "$DIR/contracts"
npm install

cd "$DIR"
echo ""
echo "========================================================"
echo "     Setup Complete! Run ./start_dev.sh to launch"
echo "========================================================"
