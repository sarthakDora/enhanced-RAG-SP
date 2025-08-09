import requests
import json

# Direct test of the chat API with detailed response inspection
print("=== DETAILED RAG DEBUGGING ===")

chat_request = {
    "message": "Summarize the uploaded Q4 financial report",
    "use_rag": True,
    "similarity_threshold": 0.3,
    "top_k": 5,
    "temperature": 0.1
}

print(f"Request: {json.dumps(chat_request, indent=2)}")

response = requests.post("http://localhost:8000/api/chat/message", json=chat_request)

print(f"\nStatus Code: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    
    print(f"\nResponse Keys: {list(data.keys())}")
    print(f"Sources Count: {data.get('source_count', 0)}")
    print(f"Context Used: {data.get('context_used', False)}")
    print(f"Confidence Score: {data.get('confidence_score', 0)}")
    print(f"Search Time: {data.get('search_time_ms', 0)}ms")
    print(f"Generation Time: {data.get('generation_time_ms', 0)}ms")
    print(f"Total Time: {data.get('total_time_ms', 0)}ms")
    
    if 'sources' in data and data['sources']:
        print(f"\nSources ({len(data['sources'])}):")
        for i, source in enumerate(data['sources']):
            print(f"  {i+1}. {source}")
    else:
        print("\nNo sources found!")
    
    print(f"\nResponse Text: {data.get('response', '')}")
    
    if 'metadata' in data:
        print(f"\nMetadata: {data.get('metadata')}")
        
else:
    print(f"Error: {response.text}")

print("\n=== DEBUG COMPLETE ===")