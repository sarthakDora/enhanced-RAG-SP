import os
import sys
import subprocess

# Get absolute paths
project_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(project_dir, 'backend')
python_path = os.path.join(project_dir, 'venv', 'Scripts', 'python.exe')

# Change to backend directory
os.chdir(backend_dir)

# Start the server from backend directory
subprocess.run([
    python_path, 
    '-m', 'uvicorn', 
    'main:app', 
    '--host', '127.0.0.1', 
    '--port', '8000', 
    '--reload'
], cwd=backend_dir)