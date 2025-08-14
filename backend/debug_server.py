#!/usr/bin/env python3
"""
Debug script to test if attribution router is properly loaded
"""

import requests
import sys

def test_endpoints():
    base_url = "http://localhost:8000"
    
    print("Testing Backend Endpoints...")
    print("=" * 50)
    
    # Test basic health
    try:
        response = requests.get(f"{base_url}/api/health", timeout=5)
        print(f"[OK] Health endpoint: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Health endpoint failed: {e}")
        return
    
    # Test documents endpoint (known working)
    try:
        response = requests.post(f"{base_url}/api/documents/upload", timeout=5)
        print(f"[OK] Documents upload: {response.status_code} (422 = route exists)")
    except Exception as e:
        print(f"[ERROR] Documents upload failed: {e}")
    
    # Test attribution endpoint (problematic)
    try:
        response = requests.post(f"{base_url}/api/attribution/upload", timeout=5)
        print(f"[TEST] Attribution upload: {response.status_code}")
        if response.status_code == 404:
            print("[ERROR] Attribution route NOT FOUND!")
        elif response.status_code == 422:
            print("[OK] Attribution route exists (expects file upload)")
    except Exception as e:
        print(f"[ERROR] Attribution upload failed: {e}")
    
    # Test attribution health endpoint
    try:
        response = requests.get(f"{base_url}/api/attribution/health", timeout=5)
        print(f"[TEST] Attribution health: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"[ERROR] Attribution health failed: {e}")
    
    # Get OpenAPI spec to see all routes
    try:
        response = requests.get(f"{base_url}/openapi.json", timeout=5)
        if response.status_code == 200:
            openapi = response.json()
            paths = openapi.get("paths", {})
            attribution_paths = [path for path in paths.keys() if "attribution" in path]
            print(f"\nAttribution paths in OpenAPI spec:")
            for path in attribution_paths:
                print(f"  {path}")
    except Exception as e:
        print(f"❌ Failed to get OpenAPI spec: {e}")

if __name__ == "__main__":
    test_endpoints()