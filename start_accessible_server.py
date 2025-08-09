#!/usr/bin/env python3
import os
import sys
import uvicorn
from pathlib import Path

# Get the project root and backend directories
project_root = Path(__file__).parent.absolute()
backend_dir = project_root / "backend"

# Change to backend directory and update Python path
os.chdir(backend_dir)
sys.path.insert(0, str(backend_dir))

print(f"Starting Enhanced RAG Server...")
print(f"Backend directory: {backend_dir}")
print(f"Current working directory: {os.getcwd()}")

# Import and test the app first
try:
    from main import app
    print("✓ Successfully imported FastAPI app")
    
    # Import key services to verify they work
    from app.core.config import settings
    print(f"✓ Config loaded - API Port: {settings.API_PORT}")
    
    from app.services.qdrant_service import QdrantService
    from app.services.ollama_service import OllamaService
    print("✓ Services imported successfully")
    
except Exception as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

# Start the server
try:
    print(f"\n🚀 Starting server on http://localhost:8000")
    print("   Press Ctrl+C to stop the server")
    print("=" * 50)
    
    uvicorn.run(
        app=app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
        access_log=True
    )
    
except KeyboardInterrupt:
    print("\n🛑 Server stopped by user")
except Exception as e:
    print(f"✗ Server error: {e}")
    import traceback
    traceback.print_exc()