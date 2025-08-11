#!/usr/bin/env python3

import requests
import json

def test_search():
    print("Testing direct document search...")
    
    search_data = {
        'query': 'performance attribution',
        'top_k': 5,
        'similarity_threshold': 0.1
    }
    
    resp = requests.post('http://localhost:8000/api/documents/search', json=search_data)
    
    if resp.status_code == 200:
        results = resp.json()
        print(f"Found {len(results)} documents")
        
        for i, doc in enumerate(results):
            if i >= 3: break
            print(f"\nDocument {i+1}:")
            print(f"  Score: {doc['score']:.3f}")
            print(f"  Content: {doc['content'][:150]}...")
            
            if 'document_metadata' in doc and doc['document_metadata']:
                metadata = doc['document_metadata']
                print(f"  Filename: {metadata.get('filename', 'unknown')}")
                print(f"  Type: {metadata.get('document_type', 'unknown')}")
            else:
                print("  No metadata found")
    else:
        print(f"Search failed: {resp.status_code}")
        print(resp.text)

def test_chat_search():
    print("\n" + "="*50)
    print("Testing chat with document_type filter...")
    
    # Create session
    session_resp = requests.post('http://localhost:8000/api/chat/sessions')
    if session_resp.status_code != 200:
        print(f"Failed to create session: {session_resp.status_code}")
        return
    
    session_id = session_resp.json()['session_id']
    print(f"Session ID: {session_id}")
    
    # Test query with document type filter
    query_data = {
        'message': 'Show me top contributors from performance attribution',
        'session_id': session_id,
        'use_rag': True,
        'document_type': 'performance_attribution',
        'temperature': 0.7
    }
    
    print(f"Query: {query_data['message']}")
    print(f"Document type filter: {query_data['document_type']}")
    
    resp = requests.post('http://localhost:8000/api/chat/message', json=query_data)
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"\nResult:")
        print(f"  Source count: {data['source_count']}")
        print(f"  Context used: {data['context_used']}")
        print(f"  Confidence: {data['confidence_score']:.2f}")
        print(f"  Generation time: {data['generation_time_ms']:.0f}ms")
        
        if data['source_count'] > 0:
            print("\n  Sources:")
            for i, source in enumerate(data['sources']):
                print(f"    {i+1}. {source['document_metadata']['filename']} (score: {source['score']:.3f})")
        else:
            print("\n  No sources found - documents not matching filter or not indexed properly")
            
        print(f"\n  Response preview: {data['response'][:200]}...")
    else:
        print(f"Chat failed: {resp.status_code}")
        print(resp.text)

if __name__ == "__main__":
    test_search()
    test_chat_search()