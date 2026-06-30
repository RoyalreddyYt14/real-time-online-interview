@echo off
setlocal enabledelayedexpansion

REM Check if virtual environment exists
if not exist ".venv-1\Scripts\activate.bat" (
    echo.
    echo ERROR: Virtual environment not found at .venv-1
    echo.
    echo Please create a virtual environment first:
    echo   python -m venv .venv-1
    echo.
    echo Then install requirements:
    echo   .venv-1\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
call .venv-1\Scripts\activate.bat

if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Run the application
echo.
echo Starting Real-Time Online Interview Application...
echo.
python app.py

if errorlevel 1 (
    echo.
    echo ERROR: Application failed to start
    echo Check the error messages above
    echo.
    pause
    exit /b 1
)

pause