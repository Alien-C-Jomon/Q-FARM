
@echo off
title Q-FARM Launcher
color 0A

echo ========================================
echo        Q-FARM ONE-CLICK LAUNCHER
echo ========================================
echo.

set "PROJECT_DIR=C:\Users\Alien C Jomon\Documents\Q-FARM"

if not exist "%PROJECT_DIR%\.venv\Scripts\activate.bat" (
    echo ERROR: Python virtual environment not found.
    echo Check your Q-FARM installation.
    pause
    exit /b 1
)

echo [1/3] Starting Q-FARM backend...

start "Q-FARM Backend" cmd /k "cd /d ""%PROJECT_DIR%"" && call .venv\Scripts\activate.bat && python -m backend.app"

echo.
echo [2/3] Waiting for the website to start...
timeout /t 5 /nobreak >nul

echo.
echo [3/3] Opening Q-FARM website...
start "" "http://127.0.0.1:5000/"

echo.
echo Q-FARM launcher finished!
echo Keep the backend CMD window open while using the website.
echo.
pause