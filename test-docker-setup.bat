@echo off
setlocal enabledelayedexpansion

echo 🧪 Testing Docker Setup for Enhanced RAG
echo =========================================

REM Check if Docker is running
docker info >nul 2>&1
if !errorlevel! neq 0 (
    echo ❌ Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

echo ✅ Docker is running

REM Check if docker-compose is available
docker-compose version >nul 2>&1
if !errorlevel! neq 0 (
    echo ❌ docker-compose not found. Please install Docker Compose.
    pause
    exit /b 1
)

echo ✅ Docker Compose is available

REM Stop any existing containers
echo 🛑 Stopping existing containers...
docker-compose down --remove-orphans 2>nul

REM Test backend build only (fastest test)
echo 🔨 Testing backend build (this may take a few minutes)...
docker-compose build backend --no-cache
if !errorlevel! neq 0 (
    echo ❌ Backend build failed. Check the error above.
    pause
    exit /b 1
)

echo ✅ Backend builds successfully

REM Test frontend build
echo 🔨 Testing frontend build...
docker-compose build frontend --no-cache
if !errorlevel! neq 0 (
    echo ❌ Frontend build failed. Check the error above.
    pause
    exit /b 1
)

echo ✅ Frontend builds successfully

REM Quick start test (without waiting for full startup)
echo 🚀 Quick startup test...
docker-compose up -d
if !errorlevel! neq 0 (
    echo ❌ Failed to start containers. Check the error above.
    pause
    exit /b 1
)

echo ✅ Containers started successfully

REM Check container status
echo 📊 Container status:
docker-compose ps

REM Cleanup
echo 🧹 Cleaning up test containers...
docker-compose down 2>nul

echo.
echo 🎉 Docker setup test completed successfully!
echo.
echo 📋 Next steps:
echo    1. Run: docker-start.bat (for full startup with health checks)
echo    2. Or run: docker-compose up --build
echo.
echo 🌐 When running, access:
echo    - Frontend: http://localhost
echo    - Backend API: http://localhost:8000
echo    - Qdrant: http://localhost:6333/dashboard
echo    - Ollama: http://localhost:11434
echo.

pause