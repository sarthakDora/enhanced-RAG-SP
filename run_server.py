#!/usr/bin/env python3
import os
import sys
import subprocess
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

try:
    # Start the uvicorn server
    result = subprocess.run([
        str(venv_python),
        "-m", "uvicorn",
        "main:app",
        "--host", "127.0.0.1",
        "--port", "8000",
        "--reload"
    ], cwd=str(backend_dir), check=True)
except KeyboardInterrupt:
    print("\nServer stopped by user")
except Exception as e:
    print(f"Error starting server: {e}")