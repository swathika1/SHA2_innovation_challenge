@echo off
REM SHA2 Rehab Coach - Mobile App Quick Setup for Windows
REM This script automates Capacitor setup

setlocal enabledelayedexpansion

echo.
echo  =========================================
echo  SHA2 Rehab Coach - Mobile App Setup
echo  =========================================
echo.

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found. Please install from https://nodejs.org/
    pause
    exit /b 1
)

echo [✓] Node.js found: 
for /f "tokens=*" %%i in ('node --version') do echo    %%i

REM Check npm
npm --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: npm not found.
    pause
    exit /b 1
)

echo [✓] npm found:
for /f "tokens=*" %%i in ('npm --version') do echo    %%i

echo.
echo [1] Installing npm dependencies...
call npm install
if errorlevel 1 (
    echo ERROR: npm install failed
    pause
    exit /b 1
)

echo [✓] Dependencies installed

echo.
echo [2] Checking Capacitor...
call npx cap --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Capacitor not accessible
    pause
    exit /b 1
)

echo [✓] Capacitor available

echo.
echo [3] Syncing files to Android...
call npx cap sync
if errorlevel 1 (
    echo WARNING: Capacitor sync had issues, but continuing...
)

echo.
echo =========================================
echo Setup Complete! ✓
echo =========================================
echo.
echo Next steps:
echo  1. Open in Android Studio:
echo     npm run open:android
echo.
echo  2. Or start emulator and run:
echo     npx cap run android
echo.
echo For more details, see MOBILE_APP_SETUP.md
echo.

pause
