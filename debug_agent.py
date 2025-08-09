import requests
import json

# Test the individual components to debug the multi-agent system

print("=== DEBUGGING MULTI-AGENT RAG SYSTEM ===")

# 1. Test direct document search (this works)
print("1. Testing direct document search API...")
search_response = requests.post("http://localhost:8000/api/documents/search", json={
    "query": "summarize Q4 financial report",
    "top_k": 5,
    "similarity_threshold": 0.3
})

if search_response.status_code == 200:
    search_data = search_response.json()
    print(f"   Direct search found {search_data.get('total_results', 0)} results")
else:
    print(f"   Direct search failed: {search_response.status_code}")

# 2. Test chat with explicit document request
print("\n2. Testing chat with explicit document reference...")
chat_response = requests.post("http://localhost:8000/api/chat/message", json={
    "message": "Based on the uploaded documents, summarize the Q4 financial report",
    "use_rag": True,
    "similarity_threshold": 0.3,
    "top_k": 5
})

if chat_response.status_code == 200:
    chat_data = chat_response.json()
    print(f"   Sources: {chat_data.get('source_count', 0)}")
    print(f"   Context used: {chat_data.get('context_used', False)}")
    print(f"   Response preview: {chat_data.get('response', '')[:100]}...")
else:
    print(f"   Chat failed: {chat_response.status_code} - {chat_response.text}")

# 3. Test with different phrasing
print("\n3. Testing with different phrasing...")
chat_response2 = requests.post("http://localhost:8000/api/chat/message", json={
    "message": "What information is in my uploaded financial documents?",
    "use_rag": True,
    "similarity_threshold": 0.3,
    "top_k": 5
})

if chat_response2.status_code == 200:
    chat_data2 = chat_response2.json()
    print(f"   Sources: {chat_data2.get('source_count', 0)}")
    print(f"   Context used: {chat_data2.get('context_used', False)}")
    print(f"   Response preview: {chat_data2.get('response', '')[:100]}...")
else:
    print(f"   Chat failed: {chat_response2.status_code}")

print("\n=== DEBUGGING COMPLETE ===")