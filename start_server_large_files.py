#!/usr/bin/env python3
"""
Enhanced RAG Server with Large File Upload Support
"""

import os
import sys
import uvicorn
from pathlib import Path

# Add backend to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

# Import the app
from main import app
from app.core.config import settings

def start_server():
    """Start the Enhanced RAG server with large file upload support"""
    
    print("=" * 60)
    print("🚀 Starting Enhanced RAG Server with Large File Support")
    print("=" * 60)
    print(f"📂 Working Directory: {os.getcwd()}")
    print(f"🌐 Server URL: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"📤 Max File Size: {settings.MAX_FILE_SIZE / (1024*1024):.0f} MB")
    print(f"📁 Allowed Extensions: {settings.ALLOWED_EXTENSIONS}")
    print(f"🔧 Debug Mode: {settings.DEBUG}")
    print("=" * 60)
    
    try:
        # Configure uvicorn with settings optimized for large file uploads
        config = uvicorn.Config(
            app=app,
            host=settings.API_HOST,
            port=settings.API_PORT,
            reload=False,  # Disable reload for stability with large files
            log_level="info",
            access_log=True,
            # Large file upload optimizations
            loop="asyncio",
            http="httptools",
            ws="websockets",
            # Connection limits
            limit_max_requests=1000,
            limit_concurrency=100,
            # Timeouts (important for large files)
            timeout_keep_alive=30,
            timeout_notify=300,  # 5 minutes for large file notifications
            # Enable h11 for better large request handling
            server_header=True,
            # Additional settings for large files
            h11_max_incomplete_event_size=1073741824,  # 1GB for large uploads
        )
        
        server = uvicorn.Server(config)
        print("✅ Server configuration complete")
        print("⏳ Starting server... (Press Ctrl+C to stop)")
        print("-" * 60)
        
        server.run()
        
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("🛑 Server stopped by user")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    start_server()