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
        print("Resetting threshold to 70...")
        await client.post(f"{BASE_URL}/admin/configs", json={
            "service": "mishka-initiative",
            "key": "threshold",
            "value": "70",
            "type": "int"
        }, headers=headers)
        
        print("Updating soft_rule_instructions...")
        instructions = """
        Criteria:
        - Reply IMMEDIATELY (Score 100) if the user addresses you by Name or Alias (e.g. "Mishka, you here?", "Mishka help").
        - Reply (Score 95+) if the message is a direct response to YOUR last message in the context.
        - Reply (Score 80+) if the user asks a question relevant to you or general knowledge.
        - Reply (Score 75+) if the user is venting/emotional and a supportive comment fits the persona.
        - Ignore (Score < 50) short, irrelevant, or phatic expressions (e.g. "ok", "lol", "cool") unless they address you.
        - Ignore (Score < 30) internal discussions between other people if they do not concern you.
        """
        await client.post(f"{BASE_URL}/admin/configs", json={
            "service": "mishka-initiative",
            "key": "soft_rule_instructions",
            "value": instructions,
            "type": "string"
        }, headers=headers)
        
        # Get Configs
        print("Getting current configs...")
        resp = await client.get(f"{BASE_URL}/admin/configs", headers=headers)
        print(f"Get Configs: {resp.json()}")
        
        # 3. Get Configs
        resp = await client.get(f"{BASE_URL}/admin/configs", headers=headers)
        print(f"Get Configs: {resp.json()}")

if __name__ == "__main__":
    asyncio.run(verify())
