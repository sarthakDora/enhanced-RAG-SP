import requests
import json

# Simple test of multi-agent system
url = "http://localhost:8000/api/chat/message"

payload = {
    "message": "What is EBITDA and how is it calculated?",
    "use_rag": False,
    "temperature": 0.7,
    "max_tokens": 500
}

try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("Success!")
        print(f"Response: {data.get('response', 'No response')[:200]}...")
        print(f"Confidence: {data.get('confidence_score', 0):.2f}")
        print(f"Generation Time: {data.get('generation_time_ms', 0):.2f}ms")
    else:
        print("Error!")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"Request failed: {e}")