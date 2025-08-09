#!/usr/bin/env python3

import requests
import json

def debug_metadata_state():
    """Debug the metadata store state"""
    base_url = "http://localhost:8000/api"
    
    print("=== DEBUGGING METADATA STATE ===")
    
    # Try to access the debug endpoint
    try:
        response = requests.get(f"{base_url}/chat/debug/metadata")
        print(f"Debug metadata endpoint status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Shared metadata count: {data.get('shared_metadata_count', 0)}")
            print(f"Shared metadata keys: {data.get('shared_metadata_keys', [])}")
        else:
            print(f"Debug endpoint error: {response.text}")
    except Exception as e:
        print(f"Debug endpoint failed: {e}")
    
    # Upload a new document to see if it populates the metadata store
    print("\n=== UPLOADING NEW TEST DOCUMENT ===")
    try:
        # Create a simple test document
        test_content = """TEST FINANCIAL REPORT Q4 2023
        
Revenue: $100 million
EBITDA: $30 million  
Net Income: $20 million

This is a test document for debugging the metadata store issue."""
        
        files = {'files': ('test_debug_doc.txt', test_content, 'text/plain')}
        data = {
            'document_type': 'financial_report',
            'tags': 'test,debug,Q4'
        }
        
        upload_response = requests.post(f"{base_url}/documents/upload", files=files, data=data)
        print(f"Upload status: {upload_response.status_code}")
        
        if upload_response.status_code == 200:
            upload_data = upload_response.json()
            print(f"Upload successful: {upload_data['message']}")
            
            # Now check if the metadata store is populated
            debug_response = requests.get(f"{base_url}/chat/debug/metadata")
            if debug_response.status_code == 200:
                debug_data = debug_response.json()
                print(f"After upload - Shared metadata count: {debug_data.get('shared_metadata_count', 0)}")
            
            # Test RAG immediately
            print("\n=== TESTING RAG AFTER UPLOAD ===")
            chat_payload = {
                "message": "What is the revenue in the test financial report?",
                "use_rag": True,
                "similarity_threshold": 0.3,
                "top_k": 5,
                "temperature": 0.1
            }
            
            # Create session and test
            session_response = requests.post(f"{base_url}/chat/sessions", 
                                           headers={"Content-Type": "application/json"},
                                           json={"title": "Debug Session"})
            
            if session_response.status_code == 200:
                session_data = session_response.json()
                chat_payload["session_id"] = session_data["session_id"]
                
                chat_response = requests.post(f"{base_url}/chat/message",
                                            headers={"Content-Type": "application/json"},
                                            json=chat_payload)
                
                if chat_response.status_code == 200:
                    chat_data = chat_response.json()
                    print(f"RAG test - Sources found: {len(chat_data.get('sources', []))}")
                    print(f"Context used: {chat_data.get('context_used', False)}")
                    
                    if chat_data.get('sources'):
                        print("SUCCESS: RAG found sources after fresh upload!")
                    else:
                        print("PROBLEM: RAG still not finding sources even after fresh upload")
        
    except Exception as e:
        print(f"Upload test failed: {e}")
    
    print("\n=== DEBUG COMPLETE ===")

if __name__ == "__main__":
    debug_metadata_state()