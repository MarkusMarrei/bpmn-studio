@echo off
cd /d "%~dp0"
title BPMN Studio - AI BPMN Generator

echo =====================================================================
echo   BPMN Studio - Local AI BPMN Generator
echo   Author: Markus Marrei (Apache 2.0 License)
echo =====================================================================
echo.

where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=py"
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set "PY_CMD=python"
    ) else (
        echo [ERROR] Python was not found in your system PATH!
        echo Please install Python 3.10+ from https://www.python.org/
        echo Make sure to check the box "Add python.exe to PATH" during installation.
        pause
        exit /b 1
    )
)

echo [1/2] Checking Python packages...
%PY_CMD% -c "import fastapi, uvicorn" >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Installing required dependencies from requirements.txt...
    %PY_CMD% -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install requirements. Please run: %PY_CMD% -m pip install -r requirements.txt
        pause
        exit /b 1
    )
)

echo [2/2] Starting server at http://127.0.0.1:8000 ...
echo Browser should open automatically. Keep this window open while using the app.
echo Press Ctrl+C in this window to stop the server.
echo.
%PY_CMD% app.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Server terminated with error code %errorlevel%.
)
pause
