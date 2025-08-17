@echo off
REM Enhanced RAG Docker Startup Script for Windows
REM This script helps developers start the containerized application easily

setlocal enabledelayedexpansion

echo 🚀 Starting Enhanced RAG Application with Docker
echo ================================================

REM Check if Docker is running
docker info >nul 2>&1
if !errorlevel! neq 0 (
    echo ❌ Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

REM Check if docker-compose is available
docker-compose version >nul 2>&1
if !errorlevel! neq 0 (
    echo ❌ docker-compose not found. Please install Docker Compose.
    pause
    exit /b 1
)

REM Parse command line arguments
set MODE=production
set REBUILD=false
set LOGS=false

:parse_args
if "%1"=="" goto end_parse
if "%1"=="--dev" set MODE=development
if "%1"=="--development" set MODE=development
if "%1"=="--rebuild" set REBUILD=true
if "%1"=="--logs" set LOGS=true
if "%1"=="--help" goto show_help
if "%1"=="-h" goto show_help
shift
goto parse_args

:show_help
echo Usage: %0 [OPTIONS]
echo.
echo Options:
echo   --dev, --development    Start in development mode
echo   --rebuild              Force rebuild of containers
echo   --logs                 Show logs after startup
echo   --help, -h             Show this help message
echo.
echo Examples:
echo   %0                     # Start in production mode
echo   %0 --dev               # Start in development mode
echo   %0 --rebuild --logs    # Rebuild and show logs
pause
exit /b 0

:end_parse

echo 📋 Configuration:
echo    Mode: !MODE!
echo    Rebuild: !REBUILD!
echo    Show logs: !LOGS!
echo.

REM Set compose files based on mode
set COMPOSE_FILES=-f docker-compose.yml
if "!MODE!"=="development" (
    set COMPOSE_FILES=!COMPOSE_FILES! -f docker-compose.override.yml
)

REM Stop existing containers
echo 🛑 Stopping existing containers...
docker-compose !COMPOSE_FILES! down --remove-orphans

REM Build containers if needed
if "!REBUILD!"=="true" (
    echo 🔨 Rebuilding containers...
    docker-compose !COMPOSE_FILES! build --no-cache
) else (
    echo 🔨 Building containers...
    docker-compose !COMPOSE_FILES! build
)

REM Start services
echo 🚀 Starting services...
docker-compose !COMPOSE_FILES! up -d

REM Wait for services to be healthy
echo ⏳ Waiting for services to be ready...
timeout /t 10 /nobreak >nul

echo 🏥 Checking service health...

REM Check backend health using docker-compose exec instead of curl
for /l %%i in (1,1,30) do (
    docker-compose !COMPOSE_FILES! exec -T backend curl -f http://localhost:8000/health >nul 2>&1
    if !errorlevel! equ 0 (
        echo ✅ Backend is healthy
        goto check_frontend
    )
    timeout /t 2 /nobreak >nul
)
echo ❌ Backend health check failed
docker-compose !COMPOSE_FILES! logs backend
pause
exit /b 1

:check_frontend
REM Check frontend using docker-compose exec
for /l %%i in (1,1,30) do (
    docker-compose !COMPOSE_FILES! exec -T frontend wget --no-verbose --tries=1 --spider http://localhost:80/ >nul 2>&1
    if !errorlevel! equ 0 (
        echo ✅ Frontend is healthy
        goto check_qdrant
    )
    timeout /t 2 /nobreak >nul
)
echo ❌ Frontend health check failed
docker-compose !COMPOSE_FILES! logs frontend
pause
exit /b 1

:check_qdrant
REM Check Qdrant using docker-compose exec
for /l %%i in (1,1,30) do (
    docker-compose !COMPOSE_FILES! exec -T qdrant curl -f http://localhost:6333/dashboard >nul 2>&1
    if !errorlevel! equ 0 (
        echo ✅ Qdrant is healthy
        goto check_ollama
    )
    timeout /t 2 /nobreak >nul
)
echo ❌ Qdrant health check failed
docker-compose !COMPOSE_FILES! logs qdrant
pause
exit /b 1

:check_ollama
REM Check Ollama using docker-compose exec
for /l %%i in (1,1,30) do (
    docker-compose !COMPOSE_FILES! exec -T ollama curl -f http://localhost:11434/api/tags >nul 2>&1
    if !errorlevel! equ 0 (
        echo ✅ Ollama is healthy
        goto success
    )
    timeout /t 2 /nobreak >nul
)
echo ❌ Ollama health check failed
docker-compose !COMPOSE_FILES! logs ollama
pause
exit /b 1

:success
echo.
echo 🎉 All services are running successfully!
echo.
echo 📱 Application URLs:
echo    Frontend:         http://localhost
echo    Backend API:      http://localhost:8000
echo    API Docs:         http://localhost:8000/docs
echo    Qdrant Dashboard: http://localhost:6333/dashboard
echo    Ollama API:       http://localhost:11434
echo.
echo 💡 Useful commands:
echo    View logs:        docker-compose !COMPOSE_FILES! logs -f
echo    Stop services:    docker-compose !COMPOSE_FILES! down
echo    Service status:   docker-compose !COMPOSE_FILES! ps
echo.

REM Show logs if requested
if "!LOGS!"=="true" (
    echo 📋 Showing service logs ^(Ctrl+C to exit^):
    docker-compose !COMPOSE_FILES! logs -f
)

echo 🚀 Setup complete! Your Enhanced RAG application is ready to use.
pause