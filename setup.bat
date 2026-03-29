@echo off
REM Real-Time Online Interview System - Quick Setup Script (Windows)
REM This script helps set up the development environment quickly

echo 🚀 Setting up Real-Time Online Interview System...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✅ Python detected: %PYTHON_VERSION%

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔄 Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo ⬆️  Upgrading pip...
pip install --upgrade pip

REM Install dependencies
echo 📚 Installing dependencies...
pip install -r requirements.txt

REM Check if YOLO model exists
if not exist "yolov8n.pt" (
    echo 🤖 Downloading YOLO model...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt' -OutFile 'yolov8n.pt'"
)

REM Create necessary directories
echo 📁 Creating directories...
if not exist "instance" mkdir instance
if not exist "static\resumes" mkdir static\resumes
if not exist "static\faces" mkdir static\faces

echo.
echo 🎉 Setup complete!
echo.
echo To run the application:
echo 1. Activate the virtual environment: venv\Scripts\activate
echo 2. Start the app: python app.py
echo 3. Open your browser: http://localhost:5000
echo.
echo Admin access: http://localhost:5000/admin
echo Admin credentials: admin@example.com / admin123
echo.
echo Happy interviewing! 🎯
echo.
pause