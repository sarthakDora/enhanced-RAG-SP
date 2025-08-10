#!/usr/bin/env python3

import asyncio
import sys
import os
import requests
from pathlib import Path

# Test manual document insertion to verify the end-to-end pipeline
async def test_manual_insertion():
    """Manually insert a test document to verify the pipeline"""
    
    # Test document content
    test_content = """
    Performance Attribution Analysis - Q3 2024
    
    Executive Summary:
    - Portfolio outperformed benchmark by +0.8 pp in Q3 2024
    - Technology sector selection (+0.5 pp) was the primary positive driver
    - Healthcare security selection contributed +0.3 pp to relative performance
    - Energy sector allocation detracted -0.2 pp from returns
    
    Top Contributors:
    1. Information Technology: +0.5 pp (sector selection and security selection)
    2. Healthcare: +0.3 pp (strong security selection in biotech)
    3. Consumer Discretionary: +0.2 pp
    
    Top Detractors:
    1. Energy: -0.2 pp (underweight position hurt performance)
    2. Utilities: -0.1 pp (allocation effect)
    """
    
    # Prepare the payload for direct API testing
    api_base = "http://127.0.0.1:8000/api"
    
    print("Testing manual document creation...")
    
    # Since direct Qdrant insertion is complex, let's test if the issue is with 
    # the file processing by creating a simple text file and uploading it
    
    # Create test file
    test_file_path = "simple_test.txt"
    with open(test_file_path, "w") as f:
        f.write(test_content)
    
    try:
        # Upload the simple file
        with open(test_file_path, "rb") as f:
            files = {"files": (test_file_path, f, "text/plain")}
            data = {
                "document_type": "other",
                "tags": "test,performance,attribution"
            }
            
            print("Uploading test document...")
            response = requests.post(f"{api_base}/documents/upload", files=files, data=data, timeout=30)
            print(f"Upload response: {response.status_code}")
            print(f"Upload content: {response.text}")
            
        # Check Qdrant status after upload
        print("\nChecking Qdrant status...")
        response = requests.get(f"{api_base}/documents/debug/qdrant-status")
        print(f"Qdrant status: {response.json()}")
        
        # Force sync
        print("\nForcing metadata sync...")
        response = requests.post(f"{api_base}/chat/debug/force-sync")
        print(f"Sync result: {response.json()}")
        
        # Test query
        print("\nTesting performance attribution query...")
        query_data = {
            "message": "What were the top contributors in Q3?",
            "use_rag": True,
            "temperature": 0.7
        }
        response = requests.post(f"{api_base}/chat/message", json=query_data, timeout=60)
        result = response.json()
        print(f"Query response length: {len(result.get('response', ''))}")
        print(f"Sources found: {result.get('source_count', 0)}")
        print(f"Confidence: {result.get('confidence_score', 0)}")
        print(f"Response: {result.get('response', '')[:200]}...")
        
    finally:
        # Clean up
        if os.path.exists(test_file_path):
            os.remove(test_file_path)

if __name__ == "__main__":
    asyncio.run(test_manual_insertion())