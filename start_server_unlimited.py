#!/usr/bin/env python3
"""
Enhanced RAG Server with Unlimited File Upload Support
Uses gunicorn with custom configuration to bypass uvicorn limits
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
    """Start the Enhanced RAG server with unlimited file upload support"""
    
    print("=" * 60)
    print("🚀 Starting Enhanced RAG Server - Unlimited Upload Mode")
    print("=" * 60)
    print(f"📂 Working Directory: {os.getcwd()}")
    print(f"🌐 Server URL: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"📤 Max File Size: {settings.MAX_FILE_SIZE / (1024*1024):.0f} MB")
    print(f"📥 Max Request Size: {settings.MAX_REQUEST_SIZE / (1024*1024):.0f} MB")
    print(f"📁 Allowed Extensions: {settings.ALLOWED_EXTENSIONS}")
    print(f"🔧 Debug Mode: {settings.DEBUG}")
    print("=" * 60)
    
    try:
        # Use hypercorn which supports larger request bodies better
        try:
            import hypercorn.asyncio
            import hypercorn.config
            import asyncio
            
            config = hypercorn.config.Config()
            config.bind = [f"{settings.API_HOST}:{settings.API_PORT}"]
            config.keep_alive_timeout = 30
            config.graceful_timeout = 300
            config.max_request_size = settings.MAX_REQUEST_SIZE  # This is the key setting!
            config.body_timeout = 300
            config.access_log_format = "%(h)s %(r)s %(s)s %(b)s %(D)s"
            config.accesslog = "-"
            config.errorlog = "-"
            
            print("✅ Using Hypercorn server for unlimited uploads")
            print("⏳ Starting server... (Press Ctrl+C to stop)")
            print("-" * 60)
            
            asyncio.run(hypercorn.asyncio.serve(app, config))
            
        except ImportError:
            # Fallback to uvicorn with custom settings
            print("⚠️  Hypercorn not available, using uvicorn with custom settings")
            
            # Use a different HTTP implementation
            config = uvicorn.Config(
                app=app,
                host=settings.API_HOST,
                port=settings.API_PORT,
                reload=False,
                log_level="info",
                access_log=True,
                # Try using h11 for better large file support
                http="h11",
                loop="asyncio",
                # Connection settings
                limit_max_requests=1000,
                limit_concurrency=100,
                # Extended timeouts
                timeout_keep_alive=30,
                timeout_notify=600,  # 10 minutes
                # Large file settings
                h11_max_incomplete_event_size=settings.MAX_REQUEST_SIZE,
                server_header=True,
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
        
        # Provide installation instructions
        print("\n" + "=" * 60)
        print("💡 For better large file support, install hypercorn:")
        print("   pip install hypercorn")
        print("=" * 60)

if __name__ == "__main__":
    start_server()