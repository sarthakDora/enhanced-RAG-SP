@echo off
echo Enhanced RAG System - Starting Application...
echo.

REM Start Docker services
echo Starting Qdrant vector database...
docker-compose up -d

REM Wait for services to be ready
echo Waiting for services to initialize...
timeout /t 5 /nobreak >nul

REM Start Backend
echo Starting FastAPI backend on http://localhost:8000...
cd backend
start "Enhanced RAG Backend" cmd /k "../venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"
cd ..

REM Wait for backend to start
echo Waiting for backend to start...
timeout /t 10 /nobreak >nul

REM Start Frontend
echo Starting Angular frontend on http://localhost:4200...
cd frontend
start "Enhanced RAG Frontend" cmd /k "npm start"
cd ..

echo.
echo ===================================
echo Enhanced RAG System is starting!
echo ===================================
echo Backend API: http://localhost:8000
echo Frontend UI: http://localhost:4200
echo Qdrant Dashboard: http://localhost:6333/dashboard
echo.
echo The application will open automatically in a few moments...
echo Press any key to open the application in your browser...
pause

REM Open the application in default browser
start http://localhost:4200

echo.
echo Application is running!
echo - Upload financial documents via the Documents tab
echo - Chat with your documents via the Chat tab
echo - Monitor system health via API endpoints
echo.
echo Press Ctrl+C in the backend/frontend windows to stop the servers.
pause