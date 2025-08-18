@echo off
echo Enhanced RAG System - Stop All Services
echo =======================================
echo.
echo Stopping all Enhanced RAG services...
echo.

echo Stopping Qdrant container...
docker stop enhanced-rag-qdrant 2>nul
docker rm enhanced-rag-qdrant 2>nul
echo Qdrant stopped.
echo.

echo Stopping backend and frontend processes...
echo Looking for Enhanced RAG processes...
echo.

REM Kill processes by window title (if started with start command)
taskkill /FI "WindowTitle eq Enhanced RAG Backend*" /T /F 2>nul
taskkill /FI "WindowTitle eq Enhanced RAG Frontend*" /T /F 2>nul

REM Kill processes by executable name
taskkill /IM "enhanced-rag-backend.exe" /T /F 2>nul
taskkill /IM "python.exe" /FI "CommandLine eq *main.py*" /T /F 2>nul
taskkill /IM "python.exe" /FI "CommandLine eq *server.py*" /T /F 2>nul
taskkill /IM "node.exe" /FI "CommandLine eq *ng serve*" /T /F 2>nul

echo.
echo =======================================
echo All Enhanced RAG services stopped!
echo =======================================
echo.
echo Services that were stopped:
echo - Qdrant vector database
echo - Backend API server
echo - Frontend web server
echo.
pause