@echo off
echo.
echo =========================================
echo  Lead Automation System - Windows
echo =========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Run the Python startup script
python start.py %*

pause