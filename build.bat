@echo off
title Build MC Controller EXE
echo ========================================
echo   Building MC Server Controller EXE
echo ========================================
echo.

where python >nul 2>&1 || (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

echo [1/3] Installing PyInstaller...
pip install pyinstaller -q

echo [2/3] Building EXE...
pyinstaller --onefile --name mc_controller --windowed --distpath build --workpath build\temp --clean mc_controller.py

echo [3/3] Done!
echo.
if exist "build\mc_controller.exe" (
    echo EXE created: build\mc_controller.exe
) else (
    echo Build failed. Check output above.
)
echo.
pause
