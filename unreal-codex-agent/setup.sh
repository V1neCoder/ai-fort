#!/bin/bash

# UEFN Codex Agent - Complete Setup Script for macOS/Linux

echo "========================================"
echo " UEFN Codex Agent - Full Setup"
echo "========================================"
echo ""

# Check Python
echo "[1/5] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found. Please install Python 3.11+"
    exit 1
fi

# Setup Python Virtual Environment
echo "[2/5] Setting up Python backend..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# Install Python dependencies
echo "[3/5] Installing Python dependencies..."
pip install -r app/backend/requirements.txt

# Check Node.js
echo "[4/5] Checking Node.js installation..."
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js not found. Please install Node.js 20+"
    exit 1
fi

# Setup Node packages
echo "[5/5] Installing Node.js dependencies..."
cd app/electron
npm install
cd ../..

echo ""
echo "========================================"
echo " Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Start the app: npm run dev (in app/electron directory)"
echo "2. Or build: npm run build"
echo ""
echo "To activate Python environment in future: source .venv/bin/activate"
echo ""
