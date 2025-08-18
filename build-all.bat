@echo off
echo Enhanced RAG System - Complete Build Script
echo ==========================================
echo.

REM Check if we're in the correct directory
if not exist "backend\main.py" (
    echo Error: Please run this script from the project root directory
    echo Expected structure: backend\main.py and frontend\package.json
    pause
    exit /b 1
)

if not exist "frontend\package.json" (
    echo Error: Frontend directory not found
    pause
    exit /b 1
)

echo Starting complete build process...
echo.

echo [1/4] Building Backend Executable...
echo =====================================
cd backend

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.8+ and add to PATH
    pause
    exit /b 1
)

REM Install build dependencies
echo Installing build dependencies...
python -m pip install -r requirements-exe.txt
if errorlevel 1 (
    echo Error: Failed to install backend dependencies
    pause
    exit /b 1
)

REM Build executable
echo Building executable...
python build_exe.py
if errorlevel 1 (
    echo Error: Backend build failed
    pause
    exit /b 1
)

cd ..

echo.
echo [2/4] Building Frontend Package...
echo ==================================
cd frontend

REM Check if Node.js is available
node --version >nul 2>&1
if errorlevel 1 (
    echo Error: Node.js not found. Please install Node.js 18+ and add to PATH
    pause
    exit /b 1
)

REM Install dependencies
echo Installing frontend dependencies...
call npm install
if errorlevel 1 (
    echo Error: Failed to install frontend dependencies
    pause
    exit /b 1
)

REM Build deployment package
echo Building deployment package...
call npm run build:deploy
if errorlevel 1 (
    echo Error: Frontend build failed
    pause
    exit /b 1
)

cd ..

echo.
echo [3/4] Creating Deployment Package...
echo ===================================

REM Create main deployment directory
if exist deployment rmdir /s /q deployment
mkdir deployment
mkdir deployment\backend
mkdir deployment\frontend
mkdir deployment\docs

REM Copy backend files
echo Copying backend files...
xcopy /E /I backend\dist\enhanced-rag-backend deployment\backend\enhanced-rag-backend
copy backend\start-backend.bat deployment\backend\
copy backend\start-backend.sh deployment\backend\
copy backend\config.env.template deployment\backend\

REM Copy frontend files
echo Copying frontend files...
xcopy /E /I frontend\deployment deployment\frontend\

REM Copy documentation
echo Copying documentation...
copy DEPLOYMENT_GUIDE.md deployment\docs\
copy README.md deployment\docs\

REM Create main startup scripts
echo Creating main startup scripts...

echo @echo off > deployment\start-all.bat
echo echo Enhanced RAG System - Complete Startup >> deployment\start-all.bat
echo echo ======================================== >> deployment\start-all.bat
echo echo. >> deployment\start-all.bat
echo echo Starting Qdrant... >> deployment\start-all.bat
echo docker run -d --name enhanced-rag-qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant >> deployment\start-all.bat
echo echo. >> deployment\start-all.bat
echo echo Waiting 10 seconds for Qdrant to start... >> deployment\start-all.bat
echo timeout /t 10 /nobreak >> deployment\start-all.bat
echo echo. >> deployment\start-all.bat
echo echo Starting backend in new window... >> deployment\start-all.bat
echo start "Enhanced RAG Backend" /D "backend" start-backend.bat >> deployment\start-all.bat
echo echo. >> deployment\start-all.bat
echo echo Waiting 15 seconds for backend to start... >> deployment\start-all.bat
echo timeout /t 15 /nobreak >> deployment\start-all.bat
echo echo. >> deployment\start-all.bat
echo echo Starting frontend... >> deployment\start-all.bat
echo start "Enhanced RAG Frontend" /D "frontend" start-frontend.bat >> deployment\start-all.bat
echo echo. >> deployment\start-all.bat
echo echo All services starting... >> deployment\start-all.bat
echo echo Frontend: http://localhost:4200 >> deployment\start-all.bat
echo echo Backend API: http://localhost:8000 >> deployment\start-all.bat
echo echo Qdrant: http://localhost:6333 >> deployment\start-all.bat
echo pause >> deployment\start-all.bat

REM Create Unix startup script
echo #!/bin/bash > deployment\start-all.sh
echo echo "Enhanced RAG System - Complete Startup" >> deployment\start-all.sh
echo echo "========================================" >> deployment\start-all.sh
echo echo "" >> deployment\start-all.sh
echo echo "Starting Qdrant..." >> deployment\start-all.sh
echo docker run -d --name enhanced-rag-qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant >> deployment\start-all.sh
echo echo "" >> deployment\start-all.sh
echo echo "Waiting 10 seconds for Qdrant to start..." >> deployment\start-all.sh
echo sleep 10 >> deployment\start-all.sh
echo echo "" >> deployment\start-all.sh
echo echo "Starting backend..." >> deployment\start-all.sh
echo cd backend ^&^& ./start-backend.sh ^& >> deployment\start-all.sh
echo echo "" >> deployment\start-all.sh
echo echo "Waiting 15 seconds for backend to start..." >> deployment\start-all.sh
echo sleep 15 >> deployment\start-all.sh
echo echo "" >> deployment\start-all.sh
echo echo "Starting frontend..." >> deployment\start-all.sh
echo cd ../frontend ^&^& ./start-frontend.sh >> deployment\start-all.sh
echo echo "" >> deployment\start-all.sh
echo echo "All services started!" >> deployment\start-all.sh
echo echo "Frontend: http://localhost:4200" >> deployment\start-all.sh
echo echo "Backend API: http://localhost:8000" >> deployment\start-all.sh
echo echo "Qdrant: http://localhost:6333" >> deployment\start-all.sh

REM Make Unix script executable (if on Unix-like system)
if exist "C:\Windows\System32\bash.exe" (
    C:\Windows\System32\bash.exe -c "chmod +x deployment/start-all.sh"
)

REM Create README for deployment
echo # Enhanced RAG System Deployment Package > deployment\README.md
echo. >> deployment\README.md
echo This package contains everything needed to deploy the Enhanced RAG system. >> deployment\README.md
echo. >> deployment\README.md
echo ## Quick Start >> deployment\README.md
echo. >> deployment\README.md
echo 1. Ensure Docker is installed and running >> deployment\README.md
echo 2. Ensure Python 3.6+ is installed >> deployment\README.md
echo 3. Install Ollama on the target machine >> deployment\README.md
echo 4. Run start-all.bat (Windows) or ./start-all.sh (Unix) >> deployment\README.md
echo. >> deployment\README.md
echo ## Access Points >> deployment\README.md
echo. >> deployment\README.md
echo - Frontend: http://localhost:4200 >> deployment\README.md
echo - Backend API: http://localhost:8000 >> deployment\README.md
echo - Qdrant Dashboard: http://localhost:6333/dashboard >> deployment\README.md
echo. >> deployment\README.md
echo ## Manual Startup >> deployment\README.md
echo. >> deployment\README.md
echo If the automatic startup doesn't work: >> deployment\README.md
echo. >> deployment\README.md
echo 1. Start Qdrant: `docker run -p 6333:6333 qdrant/qdrant` >> deployment\README.md
echo 2. Start Backend: Run `backend\start-backend.bat` >> deployment\README.md
echo 3. Start Frontend: Run `frontend\start-frontend.bat` >> deployment\README.md
echo. >> deployment\README.md
echo See docs\DEPLOYMENT_GUIDE.md for detailed instructions. >> deployment\README.md

echo.
echo [4/4] Creating Distribution Archive...
echo ====================================

REM Create zip file (if PowerShell is available)
powershell -Command "& {if (Test-Path 'enhanced-rag-deployment.zip') {Remove-Item 'enhanced-rag-deployment.zip'}; Compress-Archive -Path 'deployment\*' -DestinationPath 'enhanced-rag-deployment.zip'}" 2>nul
if errorlevel 1 (
    echo Note: Could not create ZIP file automatically
    echo You can manually zip the 'deployment' folder
) else (
    echo Created: enhanced-rag-deployment.zip
)

echo.
echo ==========================================
echo BUILD COMPLETED SUCCESSFULLY!
echo ==========================================
echo.
echo Created files:
echo - deployment\              (Complete deployment package)
echo - enhanced-rag-deployment.zip (Zip archive for distribution)
echo.
echo Deployment package contents:
echo - backend\enhanced-rag-backend\ (Executable backend)
echo - frontend\                    (Static frontend with server)
echo - docs\                        (Documentation)
echo - start-all.bat               (Complete startup script)
echo.
echo To deploy on target machine:
echo 1. Copy 'deployment' folder to target machine
echo 2. Ensure Docker and Python are installed
echo 3. Install Ollama
echo 4. Run start-all.bat
echo.
echo The application will be available at http://localhost:4200
echo.
pause