import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:8081" # Admin Backend External Port
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")

async def verify():
    async with httpx.AsyncClient() as client:
        # 1. Login
        # Dev mode might bypass initData check but we need token.
        # Let's use a mock initData or relies on DEV_MODE=true in docker-compose.
        # Login endpoint: /auth/login
        # Payload: {initData: "...", password: "..."}
        
        login_payload = {
            "initData": "dev",
            "password": ADMIN_PASSWORD
        }
        
        try:
            resp = await client.post(f"{BASE_URL}/auth/login", json=login_payload)
            if resp.status_code != 200:
                print(f"Login failed: {resp.text}")
                return
                
            token = resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("Login successful")
        except Exception as e:
             print(f"Login error: {e}")
             return

        # 2. Post Config
        # Test Initiative
        await client.post(f"{BASE_URL}/admin/configs", json={
            "service": "mishka-initiative",
            "key": "llm_model",
            "value": "gemini-1.5-flash",
            "type": "string"
        }, headers=headers)

        # Test Brain
        resp = await client.post(f"{BASE_URL}/admin/configs", json={
            "service": "mishka-brain",
            "key": "rag_fact_limit",
            "value": "5",
            "type": "int"
        }, headers=headers)
        
        # Test LLM Provider
        resp = await client.post(f"{BASE_URL}/admin/configs", json={
            "service": "mishka-llm-provider",
            "key": "request_timeout",
            "value": "60.0",
            "type": "float"
        }, headers=headers)
        print(f"Post Config: {resp.status_code} {resp.text}")
        
        # 3. Get Configs
        resp = await client.get(f"{BASE_URL}/admin/configs", headers=headers)
        print(f"Get Configs: {resp.json()}")

if __name__ == "__main__":
    asyncio.run(verify())
