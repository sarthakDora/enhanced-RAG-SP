#!/usr/bin/env python3

import asyncio
import sys
import os
import logging
from pathlib import Path
import requests
import json

# Add the backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.append(str(backend_dir))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_server_running():
    """Check if server is running"""
    try:
        response = requests.get("http://127.0.0.1:8000/api/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def test_endpoints():
    """Test all debug endpoints"""
    base_url = "http://127.0.0.1:8000/api"
    
    print("Testing Endpoints:")
    print("-" * 30)
    
    # Test Qdrant status
    try:
        response = requests.get(f"{base_url}/documents/debug/qdrant-status", timeout=10)
        print(f"Qdrant Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Collection: {data.get('collection_name')}")
            print(f"  Connection: {data.get('connection_status')}")
            print(f"  Exists: {data.get('collection_exists')}")
            print(f"  Points: {data.get('point_count')}")
        else:
            print(f"  Error: {response.text}")
    except Exception as e:
        print(f"Qdrant Status Error: {e}")
    
    print()
    
    # Test document list
    try:
        response = requests.get(f"{base_url}/documents/list", timeout=10)
        print(f"Document List: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Documents: {data.get('total_count', 0)}")
            if data.get('debug_info'):
                print(f"  Debug: {data['debug_info'].get('status', 'unknown')}")
        else:
            print(f"  Error: {response.text}")
    except Exception as e:
        print(f"Document List Error: {e}")
    
    print()
    
    # Test metadata cache
    try:
        response = requests.get(f"{base_url}/chat/debug/metadata", timeout=10)
        print(f"Metadata Cache: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Count: {data.get('shared_metadata_count', 0)}")
        else:
            print(f"  Error: {response.text}")
    except Exception as e:
        print(f"Metadata Cache Error: {e}")
    
    print()
    
    # Test auto-repair
    try:
        response = requests.post(f"{base_url}/chat/debug/auto-repair", timeout=30)
        print(f"Auto-Repair: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Status: {data.get('system_status')}")
            print(f"  Documents: {data.get('documents_found', 0)}")
            print(f"  Fixes: {len(data.get('fixes_applied', []))}")
            for fix in data.get('fixes_applied', []):
                print(f"    - {fix}")
        else:
            print(f"  Error: {response.text}")
    except Exception as e:
        print(f"Auto-Repair Error: {e}")
    
    print()
    
    # Test chat query
    try:
        payload = {
            "message": "Summarize Performance attribution",
            "use_rag": True,
            "temperature": 0.7
        }
        response = requests.post(f"{base_url}/chat/message", 
                               json=payload, 
                               headers={"Content-Type": "application/json"},
                               timeout=60)
        print(f"Chat Query: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Response length: {len(data.get('response', ''))}")
            print(f"  Sources: {data.get('source_count', 0)}")
            print(f"  Confidence: {data.get('confidence_score', 0)}")
            print(f"  First 100 chars: {data.get('response', '')[:100]}...")
        else:
            print(f"  Error: {response.text}")
            print(f"  Response: {response.content.decode()}")
    except Exception as e:
        print(f"Chat Query Error: {e}")

def main():
    print("Enhanced RAG System - Simple Diagnostic")
    print("=" * 50)
    
    # Check if server is running
    if not test_server_running():
        print("ERROR: Server is not running on http://127.0.0.1:8000")
        print("Please start the server with: cd backend && uvicorn main:app --reload --host 127.0.0.1 --port 8000")
        return
    
    print("Server is running - proceeding with tests...")
    print()
    
    test_endpoints()
    
    print("\nNext Steps:")
    print("1. If Qdrant shows 0 points: Upload documents via /documents/upload")
    print("2. If documents found but chat fails: Check Ollama connection")
    print("3. If auto-repair shows errors: Check logs for specific issues")
    print("4. Try the chat query again after auto-repair")

if __name__ == "__main__":
    main()