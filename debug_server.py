#!/usr/bin/env python3
import os
import sys
import traceback
from pathlib import Path

# Get the project root directory
project_root = Path(__file__).parent.absolute()
backend_dir = project_root / "backend"
venv_python = project_root / "venv" / "Scripts" / "python.exe"

# Change to backend directory
os.chdir(backend_dir)

# Add backend to Python path
sys.path.insert(0, str(backend_dir))

print(f"Starting server from: {backend_dir}")
print(f"Using Python: {venv_python}")
print(f"Current working directory: {os.getcwd()}")
print(f"Python path: {sys.path[:3]}")

try:
    # Try importing the app first
    print("\n=== Testing imports ===")
    from main import app
    print("✅ Successfully imported app from main.py")
    
    # Try importing all dependencies
    print("\n=== Testing dependencies ===")
    from app.core.config import settings
    print(f"✅ Config loaded - API Host: {settings.API_HOST}, Port: {settings.API_PORT}")
    
    from app.services.qdrant_service import QdrantService
    print("✅ QdrantService imported")
    
    from app.services.ollama_service import OllamaService
    print("✅ OllamaService imported")
    
    print("\n=== Starting server ===")
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info"
    )
    
except Exception as e:
    print(f"❌ Error occurred: {e}")
    print(f"Error type: {type(e).__name__}")
    print("\n=== Full traceback ===")
    traceback.print_exc()
    print("\n=== Environment info ===")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Python executable: {sys.executable}")