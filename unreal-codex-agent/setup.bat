@echo off
REM UEFN Codex Agent - Complete Setup Script for Windows

echo ========================================
echo  UEFN Codex Agent - Full Setup
echo ========================================
echo.

REM Check Python
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.11+
    exit /b 1
)

REM Setup Python Virtual Environment
echo [2/5] Setting up Python backend...
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

REM Install Python dependencies
echo [3/5] Installing Python dependencies...
REM Install pydantic-core binary first to avoid Rust compilation
pip install --only-binary :all: pydantic-core==2.14.1 2>nul || pip install pydantic-core==2.14.1
pip install -r app/backend/requirements.txt

REM Check Node.js
echo [4/5] Checking Node.js installation...
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found. Please install Node.js 20+
    exit /b 1
)

REM Setup Node packages
echo [5/5] Installing Node.js dependencies...
cd app\electron
npm install --legacy-peer-deps
cd ..\..

echo.
echo ========================================
echo  Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Start the app: npm run dev (in app/electron directory)
echo 2. Or build: npm run build
echo.
echo To activate Python environment in future: .venv\Scripts\activate.bat
echo.
pause
