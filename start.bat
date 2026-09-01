@echo off
title MC Server Controller
echo ========================================
echo   Minecraft Server Controller
echo ========================================
echo.

where python >nul 2>&1 || (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

echo Installing dependencies...
pip install -r "%~dp0requirements.txt" -q 2>nul
echo.

echo Starting controller on http://127.0.0.1:8765
echo Press Ctrl+C to stop
echo.
python "%~dp0mc_controller.py" %*
pause
