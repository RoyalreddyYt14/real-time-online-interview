@echo off
REM Real-Time Online Interview System - Quick Setup Script (Windows)
REM This script helps set up the development environment quickly

setlocal enabledelayedexpansion

echo 🚀 Setting up Real-Time Online Interview System...
echo.

REM Prefer Python 3.12 for compatibility with OpenCV and NumPy
set PYTHON_EXE=
for /f "delims=" %%i in ('python --version 2^>^&1') do set "PYTHON_VER=%%i"
if defined PYTHON_VER (
    echo %PYTHON_VER% | findstr /r /c:"Python 3\.12" >nul
    if !errorlevel! equ 0 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE (
    for /f "delims=" %%i in ('py -3.12 --version 2^>^&1') do set "PYTHON_VER=%%i"
    if defined PYTHON_VER (
        echo %PYTHON_VER% | findstr /r /c:"Python 3\.12" >nul
        if !errorlevel! equ 0 set "PYTHON_EXE=py -3.12"
    )
)

if not defined PYTHON_EXE (
    echo ❌ Python 3.12 is required. Install Python 3.12 (64-bit) and rerun this script.
    pause
    exit /b 1
)

echo ✅ Using %PYTHON_EXE%

REM Create virtual environment if it doesn't exist
if not exist ".venv-1" (
    echo 📦 Creating virtual environment...
    %PYTHON_EXE% -m venv .venv-1
)

REM Activate virtual environment
echo 🔄 Activating virtual environment...
call .venv-1\Scripts\activate.bat

REM Upgrade pip, setuptools, and wheel
echo ⬆️  Upgrading pip, setuptools, and wheel...
python -m pip install --upgrade pip setuptools wheel

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
echo 1. Activate the virtual environment: .venv-1\Scripts\activate
echo 2. Start the app: python app.py
echo 3. Open your browser: http://localhost:5000
echo.
echo Or simply double-click: run.bat
echo.
echo Admin access: http://localhost:5000/admin
echo Admin credentials: admin@example.com / admin123
echo.
echo Happy interviewing! 🎯
echo.
pause