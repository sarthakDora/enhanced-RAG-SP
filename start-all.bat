@echo off
echo Enhanced RAG System - Complete Startup
echo ========================================
echo.
echo This script will start all components of the Enhanced RAG system
echo Make sure Docker is running and Ollama is installed
echo.
echo Starting Qdrant vector database...
docker run -d --name enhanced-rag-qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant
if errorlevel 1 (
    echo Failed to start Qdrant. Make sure Docker is running.
    pause
    exit /b 1
)
echo Qdrant started successfully!
echo.
echo Waiting 10 seconds for Qdrant to initialize...
timeout /t 10 /nobreak > nul
echo.
echo Starting backend server...
if exist "backend\dist\enhanced-rag-backend\enhanced-rag-backend.exe" (
    start "Enhanced RAG Backend" /D "backend\dist\enhanced-rag-backend" enhanced-rag-backend.exe
) else if exist "backend\main.py" (
    echo Backend executable not found, running from source...
    start "Enhanced RAG Backend" /D "backend" python main.py
) else (
    echo Backend not found! Please build the backend first.
    echo Run: cd backend && python build_exe.py
    pause
    exit /b 1
)
echo Backend starting...
echo.
echo Waiting 15 seconds for backend to initialize...
timeout /t 15 /nobreak > nul
echo.
echo Starting frontend server...
if exist "frontend\deployment\server.py" (
    start "Enhanced RAG Frontend" /D "frontend\deployment" python server.py
) else if exist "frontend\src" (
    echo Frontend deployment not found, running from source...
    start "Enhanced RAG Frontend" /D "frontend" npm start
) else (
    echo Frontend not found! Please build the frontend first.
    echo Run: cd frontend && npm run build:deploy
    pause
    exit /b 1
)
echo Frontend starting...
echo.
echo ========================================
echo All services are starting up!
echo ========================================
echo.
echo Access points:
echo - Frontend UI: http://localhost:4200
echo - Backend API: http://localhost:8000
echo - API Docs: http://localhost:8000/docs
echo - Qdrant Dashboard: http://localhost:6333/dashboard
echo.
echo If any service fails to start:
echo 1. Check that all prerequisites are installed
echo 2. Check the individual service windows for errors
echo 3. Try starting services manually
echo.
echo Press any key to exit...
pause > nul