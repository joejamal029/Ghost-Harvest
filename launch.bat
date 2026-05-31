@echo off
title GhostHarvest v2.1 Launcher
echo ========================================================
echo   GhostHarvest v2.1 Launcher
echo ========================================================
echo.
echo Searching for Python installation...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in your PATH.
    echo Please install Python 3.9+ and ensure "Add to PATH" is checked.
    echo.
    pause
    exit /b 1
)

echo Launching GhostHarvest...
python "%~dp0main.py"
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] GhostHarvest exited with error code %errorlevel%.
    pause
)
