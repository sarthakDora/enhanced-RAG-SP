#!/bin/bash
echo "Enhanced RAG System - Complete Build Script"
echo "==========================================="
echo ""

# Check if we're in the correct directory
if [ ! -f "backend/main.py" ] || [ ! -f "frontend/package.json" ]; then
    echo "Error: Please run this script from the project root directory"
    echo "Expected structure: backend/main.py and frontend/package.json"
    exit 1
fi

echo "Starting complete build process..."
echo ""

echo "[1/4] Building Backend Executable..."
echo "===================================="
cd backend

# Check if Python is available
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "Error: Python not found. Please install Python 3.8+"
    exit 1
fi

# Use python3 if available, otherwise python
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

# Install build dependencies
echo "Installing build dependencies..."
$PYTHON_CMD -m pip install -r requirements-exe.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install backend dependencies"
    exit 1
fi

# Build executable
echo "Building executable..."
$PYTHON_CMD build_exe.py
if [ $? -ne 0 ]; then
    echo "Error: Backend build failed"
    exit 1
fi

cd ..

echo ""
echo "[2/4] Building Frontend Package..."
echo "================================="
cd frontend

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    echo "Error: Node.js not found. Please install Node.js 18+"
    exit 1
fi

# Install dependencies
echo "Installing frontend dependencies..."
npm install
if [ $? -ne 0 ]; then
    echo "Error: Failed to install frontend dependencies"
    exit 1
fi

# Build deployment package
echo "Building deployment package..."
npm run build:deploy
if [ $? -ne 0 ]; then
    echo "Error: Frontend build failed"
    exit 1
fi

cd ..

echo ""
echo "[3/4] Creating Deployment Package..."
echo "===================================="

# Create main deployment directory
rm -rf deployment
mkdir -p deployment/{backend,frontend,docs}

# Copy backend files
echo "Copying backend files..."
cp -r backend/dist/enhanced-rag-backend deployment/backend/
cp backend/start-backend.bat deployment/backend/
cp backend/start-backend.sh deployment/backend/
cp backend/config.env.template deployment/backend/

# Copy frontend files
echo "Copying frontend files..."
cp -r frontend/deployment/* deployment/frontend/

# Copy documentation
echo "Copying documentation..."
cp DEPLOYMENT_GUIDE.md deployment/docs/
[ -f README.md ] && cp README.md deployment/docs/

# Create main startup scripts
echo "Creating main startup scripts..."

# Windows batch file
cat > deployment/start-all.bat << 'EOF'
@echo off
echo Enhanced RAG System - Complete Startup
echo ========================================
echo.
echo Starting Qdrant...
docker run -d --name enhanced-rag-qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant
echo.
echo Waiting 10 seconds for Qdrant to start...
timeout /t 10 /nobreak > nul
echo.
echo Starting backend in new window...
start "Enhanced RAG Backend" /D "backend" start-backend.bat
echo.
echo Waiting 15 seconds for backend to start...
timeout /t 15 /nobreak > nul
echo.
echo Starting frontend...
start "Enhanced RAG Frontend" /D "frontend" start-frontend.bat
echo.
echo All services starting...
echo Frontend: http://localhost:4200
echo Backend API: http://localhost:8000
echo Qdrant: http://localhost:6333
pause
EOF

# Unix shell script
cat > deployment/start-all.sh << 'EOF'
#!/bin/bash
echo "Enhanced RAG System - Complete Startup"
echo "========================================"
echo ""
echo "Starting Qdrant..."
docker run -d --name enhanced-rag-qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant
echo ""
echo "Waiting 10 seconds for Qdrant to start..."
sleep 10
echo ""
echo "Starting backend..."
cd backend && ./start-backend.sh &
echo ""
echo "Waiting 15 seconds for backend to start..."
sleep 15
echo ""
echo "Starting frontend..."
cd ../frontend && ./start-frontend.sh &
echo ""
echo "All services started!"
echo "Frontend: http://localhost:4200"
echo "Backend API: http://localhost:8000"
echo "Qdrant: http://localhost:6333"
EOF

# Make scripts executable
chmod +x deployment/start-all.sh

# Create README for deployment
cat > deployment/README.md << 'EOF'
# Enhanced RAG System Deployment Package

This package contains everything needed to deploy the Enhanced RAG system.

## Quick Start

1. Ensure Docker is installed and running
2. Ensure Python 3.6+ is installed
3. Install Ollama on the target machine
4. Run start-all.bat (Windows) or ./start-all.sh (Unix)

## Access Points

- Frontend: http://localhost:4200
- Backend API: http://localhost:8000
- Qdrant Dashboard: http://localhost:6333/dashboard

## Manual Startup

If the automatic startup doesn't work:

1. Start Qdrant: `docker run -p 6333:6333 qdrant/qdrant`
2. Start Backend: Run `backend/start-backend.bat` or `backend/start-backend.sh`
3. Start Frontend: Run `frontend/start-frontend.bat` or `frontend/start-frontend.sh`

See docs/DEPLOYMENT_GUIDE.md for detailed instructions.
EOF

echo ""
echo "[4/4] Creating Distribution Archive..."
echo "====================================="

# Create tar.gz file
if command -v tar &> /dev/null; then
    echo "Creating tar.gz archive..."
    tar -czf enhanced-rag-deployment.tar.gz -C deployment .
    echo "Created: enhanced-rag-deployment.tar.gz"
else
    echo "Note: tar not available, skipping archive creation"
    echo "You can manually archive the 'deployment' folder"
fi

echo ""
echo "==========================================="
echo "BUILD COMPLETED SUCCESSFULLY!"
echo "==========================================="
echo ""
echo "Created files:"
echo "- deployment/              (Complete deployment package)"
echo "- enhanced-rag-deployment.tar.gz (Archive for distribution)"
echo ""
echo "Deployment package contents:"
echo "- backend/enhanced-rag-backend/ (Executable backend)"
echo "- frontend/                    (Static frontend with server)"
echo "- docs/                        (Documentation)"
echo "- start-all.sh                 (Complete startup script)"
echo ""
echo "To deploy on target machine:"
echo "1. Copy 'deployment' folder to target machine"
echo "2. Ensure Docker and Python are installed"
echo "3. Install Ollama"
echo "4. Run ./start-all.sh"
echo ""
echo "The application will be available at http://localhost:4200"
echo ""