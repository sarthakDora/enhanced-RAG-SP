#!/usr/bin/env python3

import requests
import json

def test_qdrant_api():
    """Debug the Qdrant API endpoints"""
    base_url = "http://localhost:6333"
    collection_name = "financial_documents"
    
    print("Testing Qdrant API endpoints...")
    print("=" * 50)
    
    # Test 1: Get collections
    print("1. Testing GET /collections")
    try:
        response = requests.get(f"{base_url}/collections")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            collections = response.json()
            print(f"Collections: {[c['name'] for c in collections.get('result', {}).get('collections', [])]}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    print()
    
    # Test 2: Get collection info
    print(f"2. Testing GET /collections/{collection_name}")
    try:
        response = requests.get(f"{base_url}/collections/{collection_name}")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            info = response.json()
            print(f"Points count: {info.get('result', {}).get('points_count', 0)}")
            print(f"Status: {info.get('result', {}).get('status', 'unknown')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    print()
    
    # Test 3: Try a simple point insertion
    print("3. Testing point insertion")
    test_point = {
        "points": [
            {
                "id": "test-123",
                "vector": [0.1] * 768,  # 768-dim vector
                "payload": {
                    "content": "Test content",
                    "document_id": "test-doc",
                    "filename": "test.txt"
                }
            }
        ]
    }
    
    # Try different endpoints
    endpoints_to_try = [
        f"/collections/{collection_name}/points",
        f"/collections/{collection_name}/points/upsert"
    ]
    
    for endpoint in endpoints_to_try:
        print(f"Trying PUT {endpoint}")
        try:
            response = requests.put(
                f"{base_url}{endpoint}",
                json=test_point,
                headers={"Content-Type": "application/json"}
            )
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            
            if response.status_code in [200, 201]:
                print("  SUCCESS!")
                break
        except Exception as e:
            print(f"  Error: {e}")
        print()
    
    print()
    
    # Test 4: Check points after insertion
    print("4. Checking points count after insertion")
    try:
        response = requests.get(f"{base_url}/collections/{collection_name}")
        if response.status_code == 200:
            info = response.json()
            print(f"Points count now: {info.get('result', {}).get('points_count', 0)}")
        else:
            print(f"Error checking count: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_qdrant_api()