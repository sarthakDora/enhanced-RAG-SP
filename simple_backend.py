#!/usr/bin/env python3
import os
import sys
import uvicorn
from pathlib import Path

# Set up paths
backend_dir = Path("C:/Projects/enhanced-RAG-3/backend")
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

print(f"Starting from: {backend_dir}")
print(f"Working directory: {os.getcwd()}")

try:
    # Direct uvicorn run with string module reference
    print("Starting uvicorn server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0", 
        port=8000,
        reload=False,
        log_level="info",
        workers=1
    )
except Exception as e:
    print(f"Server error: {e}")
    import traceback
    traceback.print_exc()