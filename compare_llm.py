import requests
import time
import re

LOCAL_LLM_URL = "http://localhost:8000/api/public/assistant/"
GEMINI_LLM_URL = "http://localhost:8001/api/public/assistant/"

test_cases = [
    {
        "query": "What is the instructor talking about in 34:17 ?",
        "video_id": "1131624533"
    },
    {
        "query": "Summarize this video.",
        "video_id": "1131624533"
    },
    {
        "query": "Explain the code used in the beginning.",
        "video_id": "1131624533"
    }
]

def parse_timestamp_from_query(query):
    match = re.search(r'(\d+):(\d+)', query)
    if match:
        minutes, seconds = map(int, match.groups())
        return float(minutes * 60 + seconds)
    return 0.0

def query_llm(name, url, query, video_id):
    timestamp = parse_timestamp_from_query(query)
    
    payload = {
        "query": query,
        "video_id": video_id,
        "timestamp": timestamp,
        "force_new": True
    }
    
    start_time = time.time()
    try:
        response = requests.post(url, json=payload)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            return response.json().get('answer'), duration
        else:
            return f"Error: {response.status_code}", duration
            
    except requests.exceptions.ConnectionError:
        return "Connection Failed", 0

print(f"{'='*20} LLM COMPARISON TEST {'='*20}\n")

for case in test_cases:
    q = case["query"]
    vid = case["video_id"]
    
    print(f"Video ID: {vid}")
    print(f"Question: {q}")
    print("-" * 60)
    
    ans_local, time_local = query_llm("Local", LOCAL_LLM_URL, q, vid)
    print(f"Local LLM (Ollama): {time_local:.2f}s")
    print(f"Answer: {ans_local}")
    print("-" * 30)

    ans_gemini, time_gemini = query_llm("Gemini", GEMINI_LLM_URL, q, vid)
    print(f"InCuiseniX 2.0 (Gemini): {time_gemini:.2f}s")
    print(f"Answer: {ans_gemini}")
    
    print("\n" + "="*60 + "\n")