import requests
import json

# Test document search to debug RAG issue
search_url = "http://localhost:8000/api/documents/search"

# Test search for uploaded document
search_request = {
    "query": "financial report Q4 2023",
    "top_k": 5,
    "similarity_threshold": 0.3,
    "use_reranking": True
}

print("Testing document search...")
try:
    response = requests.post(search_url, json=search_request)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Query: {data.get('query')}")
        print(f"Total results: {data.get('total_results', 0)}")
        print(f"Search time: {data.get('search_time_ms', 0):.2f}ms")
        
        if data.get('results'):
            print("\nFound documents:")
            for i, result in enumerate(data['results'], 1):
                print(f"{i}. Score: {result.get('score', 0):.3f}")
                print(f"   Content: {result.get('content', '')[:100]}...")
                print(f"   Filename: {result.get('document_metadata', {}).get('filename', 'Unknown')}")
                print()
        else:
            print("No results found!")
    else:
        print(f"Error: {response.text}")

except Exception as e:
    print(f"Request failed: {e}")

# Now test chat with same query
print("\n" + "="*50)
print("Testing chat with same query...")

chat_url = "http://localhost:8000/api/chat/message"
chat_request = {
    "message": "Summarize the financial report Q4 2023",
    "use_rag": True,
    "similarity_threshold": 0.3,
    "top_k": 5,
    "temperature": 0.1
}

try:
    response = requests.post(chat_url, json=chat_request)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {data.get('response', '')[:200]}...")
        print(f"Sources found: {data.get('source_count', 0)}")
        print(f"Context used: {data.get('context_used', False)}")
        print(f"Confidence: {data.get('confidence_score', 0):.2f}")
    else:
        print(f"Error: {response.text}")
        
except Exception as e:
    print(f"Request failed: {e}")