#!/usr/bin/env python3
"""
Build script to create executable for the Enhanced RAG backend.
This script creates a standalone executable that can run without Python installation.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

def install_pyinstaller():
    """Install PyInstaller if not already installed"""
    try:
        import PyInstaller
        print("PyInstaller already installed")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def create_spec_file():
    """Create PyInstaller spec file with custom configuration"""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

# Collect data files for various packages
datas = []
datas += collect_data_files('sentence_transformers')
datas += collect_data_files('transformers')
datas += collect_data_files('torch')
datas += collect_data_files('nltk')

# Collect hidden imports
hiddenimports = []
hiddenimports += collect_submodules('sentence_transformers')
hiddenimports += collect_submodules('transformers')
hiddenimports += collect_submodules('torch')
hiddenimports += collect_submodules('sklearn')
hiddenimports += collect_submodules('numpy')
hiddenimports += collect_submodules('pandas')
hiddenimports += collect_submodules('fastapi')
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('qdrant_client')
hiddenimports += collect_submodules('langchain')
hiddenimports += collect_submodules('langchain_community')
hiddenimports += collect_submodules('langchain_core')
hiddenimports += collect_submodules('langchain_experimental')
hiddenimports += collect_submodules('langchain_ollama')
hiddenimports += collect_submodules('pydantic')
hiddenimports += collect_submodules('httpx')
hiddenimports += collect_submodules('aiohttp')

# Additional specific imports that might be missed
hiddenimports += [
    'uvicorn.workers.UvicornWorker',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan.on',
    'asyncio',
    'multiprocessing',
    'concurrent.futures',
    'email.mime.multipart',
    'email.mime.text',
    'socket',
    'ssl'
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='enhanced-rag-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='enhanced-rag-backend'
)
"""
    
    with open('enhanced-rag-backend.spec', 'w') as f:
        f.write(spec_content)
    
    print("Created PyInstaller spec file: enhanced-rag-backend.spec")

def build_executable():
    """Build the executable using PyInstaller"""
    try:
        print("Building executable...")
        subprocess.check_call([
            sys.executable, "-m", "PyInstaller", 
            "--clean",
            "enhanced-rag-backend.spec"
        ])
        print("Executable built successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        return False

def create_startup_script():
    """Create startup scripts for the executable"""
    # Windows batch file
    batch_content = """@echo off
echo Starting Enhanced RAG Backend...
echo.
echo Make sure Qdrant is running (docker run -p 6333:6333 qdrant/qdrant)
echo Ollama should be running on localhost:11434
echo.
cd /d "%~dp0"
enhanced-rag-backend\\enhanced-rag-backend.exe
pause
"""
    
    with open('start-backend.bat', 'w') as f:
        f.write(batch_content)
    
    # Shell script for Unix systems
    shell_content = """#!/bin/bash
echo "Starting Enhanced RAG Backend..."
echo ""
echo "Make sure Qdrant is running (docker run -p 6333:6333 qdrant/qdrant)"
echo "Ollama should be running on localhost:11434"
echo ""
cd "$(dirname "$0")"
./enhanced-rag-backend/enhanced-rag-backend
"""
    
    with open('start-backend.sh', 'w') as f:
        f.write(shell_content)
    
    # Make shell script executable
    try:
        os.chmod('start-backend.sh', 0o755)
    except:
        pass  # Windows doesn't support chmod
    
    print("Created startup scripts: start-backend.bat and start-backend.sh")

def create_config_template():
    """Create configuration template"""
    config_content = """# Enhanced RAG Backend Configuration
# Copy this file to .env and modify as needed

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# Qdrant Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Ollama Configuration
OLLAMA_HOST=localhost
OLLAMA_PORT=11434

# File Upload Configuration
MAX_REQUEST_SIZE=104857600  # 100MB
UPLOAD_FOLDER=uploads

# Model Configuration
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHAT_MODEL=llama2

# Logging
LOG_LEVEL=INFO
"""
    
    with open('config.env.template', 'w') as f:
        f.write(config_content)
    
    print("Created configuration template: config.env.template")

def main():
    """Main build process"""
    print("Enhanced RAG Backend Executable Builder")
    print("=" * 40)
    
    # Check if we're in the backend directory
    if not os.path.exists('main.py'):
        print("Error: main.py not found. Please run this script from the backend directory.")
        sys.exit(1)
    
    # Install PyInstaller
    install_pyinstaller()
    
    # Create spec file
    create_spec_file()
    
    # Build executable
    if build_executable():
        # Create additional files
        create_startup_script()
        create_config_template()
        
        print("\n" + "=" * 40)
        print("Build completed successfully!")
        print("\nFiles created:")
        print("- dist/enhanced-rag-backend/ (executable directory)")
        print("- start-backend.bat (Windows startup script)")
        print("- start-backend.sh (Unix startup script)")
        print("- config.env.template (configuration template)")
        print("\nTo deploy:")
        print("1. Copy the entire 'dist/enhanced-rag-backend' directory to target machine")
        print("2. Copy startup scripts and config template")
        print("3. Ensure Qdrant is running (docker run -p 6333:6333 qdrant/qdrant)")
        print("4. Ensure Ollama is installed and running")
        print("5. Run start-backend.bat (Windows) or start-backend.sh (Unix)")
    else:
        print("Build failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()