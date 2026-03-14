@echo off
REM Docker build and deployment script for Windows PowerShell
REM Run this script from Windows PowerShell in the project directory
REM This will execute the build inside WSL

setlocal enabledelayedexpansion

set "PROJECT_DIR=\\wsl.localhost\Ubuntu\home\swathika\IC26\SHA2_innovation_challenge"
set "IMAGE_NAME=rehab-coach"
set "IMAGE_TAG=latest"
set "FULL_IMAGE=%IMAGE_NAME%:%IMAGE_TAG%"

echo.
echo ==========================================
echo SHA2 Innovation Challenge - Docker Build
echo ==========================================
echo.

echo Checking Docker installation...
wsl -d Ubuntu bash -c "docker --version" >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not installed in WSL
    echo Please install Docker Desktop with WSL 2 backend
    pause
    exit /b 1
)

echo Checking Docker daemon...
wsl -d Ubuntu bash -c "docker ps -q" >nul 2>&1
if errorlevel 1 (
    echo Warning: Docker daemon may not be running
    echo Please ensure Docker Desktop is running
    pause
)

echo.
echo Building Docker image: %FULL_IMAGE%
echo ==========================================
echo.

wsl -d Ubuntu bash -c "cd /home/swathika/IC26/SHA2_innovation_challenge && sudo docker build -t %FULL_IMAGE% ."

if errorlevel 1 (
    echo.
    echo Error: Build failed!
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Build successful!
echo ==========================================
echo.

echo Verifying image...
wsl -d Ubuntu bash -c "sudo docker images | grep %IMAGE_NAME%"

echo.
echo Next steps:
echo 1. Edit .env with your API keys
echo 2. Run with docker-compose:
echo    wsl -d Ubuntu docker-compose up -d
echo.
echo 3. Or run directly:
echo    wsl -d Ubuntu docker run -p 8000:8000 --env-file .env %FULL_IMAGE%
echo.
echo Access the app at: http://localhost:8000
echo.
pause
