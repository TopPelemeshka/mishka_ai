import requests
import time

MEMORY_URL = "http://localhost:8003" # Mapped in docker-compose

# mishka-memory is NOT mapped to host port 8000 in docker-compose!
# Let's check docker-compose.yml again.
# mishka-memory has:
#    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
#    (No ports mapping section in check, wait let me re-verify)

def test_rag():
    print("Testing RAG Flow...")
    
    # 1. Add Fact
    print("\n[1] Adding Fact: 'Mishka loves honey'")
    try:
        resp = requests.post(f"{MEMORY_URL}/facts/add", json={
            "text": "Мишка очень любит мед и малину",
            "metadata": {"category": "preferences"}
        })
        print(f"Add Response: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"Add Failed: {e}")
        return

    # 2. Search Fact
    print("\n[2] Searching: 'What does Mishka like?'")
    try:
        resp = requests.post(f"{MEMORY_URL}/facts/search", json={
            "query": "Что любит Мишка?",
            "limit": 3
        })
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            print(f"Found {len(results)} results:")
            for r in results:
                print(f" - [{r['score']:.4f}] {r['text']}")
        else:
            print(f"Search Failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"Search Failed: {e}")

if __name__ == "__main__":
    test_rag()
