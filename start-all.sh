#!/bin/bash
echo "Enhanced RAG System - Complete Startup"
echo "========================================"
echo ""
echo "This script will start all components of the Enhanced RAG system"
echo "Make sure Docker is running and Ollama is installed"
echo ""
echo "Starting Qdrant vector database..."
docker run -d --name enhanced-rag-qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant
if [ $? -ne 0 ]; then
    echo "Failed to start Qdrant. Make sure Docker is running."
    exit 1
fi
echo "Qdrant started successfully!"
echo ""
echo "Waiting 10 seconds for Qdrant to initialize..."
sleep 10
echo ""
echo "Starting backend server..."
if [ -f "backend/dist/enhanced-rag-backend/enhanced-rag-backend" ]; then
    echo "Starting backend executable..."
    cd backend/dist/enhanced-rag-backend && ./enhanced-rag-backend &
    BACKEND_PID=$!
    echo "Backend PID: $BACKEND_PID"
    cd - > /dev/null
elif [ -f "backend/main.py" ]; then
    echo "Backend executable not found, running from source..."
    cd backend && python3 main.py &
    BACKEND_PID=$!
    echo "Backend PID: $BACKEND_PID"
    cd - > /dev/null
else
    echo "Backend not found! Please build the backend first."
    echo "Run: cd backend && python build_exe.py"
    exit 1
fi
echo ""
echo "Waiting 15 seconds for backend to initialize..."
sleep 15
echo ""
echo "Starting frontend server..."
if [ -f "frontend/deployment/server.py" ]; then
    echo "Starting frontend deployment server..."
    cd frontend/deployment && python3 server.py &
    FRONTEND_PID=$!
    echo "Frontend PID: $FRONTEND_PID"
    cd - > /dev/null
elif [ -f "frontend/package.json" ]; then
    echo "Frontend deployment not found, running from source..."
    cd frontend && npm start &
    FRONTEND_PID=$!
    echo "Frontend PID: $FRONTEND_PID"
    cd - > /dev/null
else
    echo "Frontend not found! Please build the frontend first."
    echo "Run: cd frontend && npm run build:deploy"
    exit 1
fi
echo ""
echo "========================================"
echo "All services are starting up!"
echo "========================================"
echo ""
echo "Access points:"
echo "- Frontend UI: http://localhost:4200"
echo "- Backend API: http://localhost:8000"
echo "- API Docs: http://localhost:8000/docs"
echo "- Qdrant Dashboard: http://localhost:6333/dashboard"
echo ""
echo "Process IDs (for stopping later):"
echo "- Backend PID: $BACKEND_PID"
echo "- Frontend PID: $FRONTEND_PID"
echo ""
echo "To stop services:"
echo "- Stop Qdrant: docker stop enhanced-rag-qdrant"
echo "- Stop Backend: kill $BACKEND_PID"
echo "- Stop Frontend: kill $FRONTEND_PID"
echo ""
echo "Services are running in the background."
echo "Press Ctrl+C to return to terminal."
echo ""

# Wait for user interrupt
trap 'echo ""; echo "Use the kill commands above to stop services."; exit 0' INT
while true; do
    sleep 1
done