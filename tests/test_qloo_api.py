import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_qloo_api():
    api_key = os.getenv("QLOO_API_KEY")
    if not api_key:
        print("❌ QLOO_API_KEY not found in .env")
        return
    
    queries = ["The Beatles", "Italian cuisine", "The Matrix"]
    
    for query in queries:
        print(f"\n🔍 Testing: {query}")
        url = "https://hackathon.api.qloo.com/search"
        headers = {"x-api-key": api_key, "Content-Type": "application/json"}
        
        try:
            response = requests.get(url, headers=headers, params={"query": query})
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                print(f"✅ Found {len(results)} results")
                if results:
                    print(f"Top result: {results[0].get('name')} (types: {results[0].get('types')})")
            else:
                print(f"❌ Error: {response.text}")
        except Exception as e:
            print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_qloo_api()
