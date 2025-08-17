@echo off
echo Setting up Enhanced RAG System for Financial Institution...

REM Create virtual environment
echo Creating Python virtual environment...
C:\Users\patha\AppData\Local\Programs\Python\Python312\python.exe -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo Installing Python dependencies...
pip install -r requirements.txt

REM Create necessary directories
echo Creating project directories...
mkdir backend\app\models 2>nul
mkdir backend\app\services 2>nul
mkdir backend\app\routers 2>nul
mkdir backend\app\utils 2>nul
mkdir backend\app\core 2>nul
mkdir frontend\src\app\components 2>nul
mkdir frontend\src\app\services 2>nul
mkdir frontend\src\app\models 2>nul
mkdir uploads 2>nul
mkdir processed 2>nul
mkdir logs 2>nul
mkdir sample_documents 2>nul

REM Start Docker services
echo Starting Docker services...
docker-compose up -d

echo Setup complete! 
echo.
echo Next steps:
echo 1. Install Ollama from https://ollama.ai
echo 2. Run: ollama pull nomic-embed-text
echo 3. Run: ollama pull Gemma3:12b
echo 4. Install Node.js and Angular CLI for frontend
echo 5. Run the backend: python backend\main.py
echo.
pause