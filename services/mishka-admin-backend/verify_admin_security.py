
import requests
import hmac
import hashlib
import json
import os
import time
from urllib.parse import quote


def load_env_vars():
    """Manually load .env variables."""
    env_vars = {}
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    except FileNotFoundError:
        print("Warning: .env not found")
    return env_vars

ENV = load_env_vars()
BASE_URL = "http://localhost:8081" 
BOT_TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
ADMIN_PASSWORD = ENV.get("ADMIN_PASSWORD", "changeme")
SUPERADMIN_ID = int(ENV.get("SUPERADMIN_ID", 12345678))
VIEWER_ID = int(ENV.get("VIEWER_IDS", "11223344").split(",")[0])
RANDOM_ID = 99999999

def generate_init_data(user_id: int):
    """Generates valid signed initData for a given user_id."""
    # Data to sign
    # Telegram sends minified JSON usually, so strict constraints for hash
    user_json = json.dumps({"id": user_id, "first_name": "TestUser", "username": "tester"}, separators=(',', ':'))
    auth_date = str(int(time.time()))
    
    # Key-value pairs sorted alphabetically
    data_check_string = "\n".join([
        f"auth_date={auth_date}",
        f"user={user_json}"
    ])
    
    # Secret key
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    # Hash
    hash_value = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    # Final string (url encoded likely needed for real apps, but usually just k=v&k=v)
    # But backend parse_qs expects std query string.
    user_encoded = quote(user_json) # Actually parse_qs handles raw strings usually, but cleaner to encode
    # Wait, backend just uses parse_qs on the string.
    # Let's construct it exactly as data_check_string but with hash appended.
    # Actually, order in string doesn't matter for parse_qs, but matters for hash. 
    # But the hash verification reconstructs the string from params.
    # So we just need to send the params.
    
    return f"auth_date={auth_date}&user={user_json}&hash={hash_value}"

def login(user_id, password=ADMIN_PASSWORD):
    init_data = generate_init_data(user_id)
    resp = requests.post(f"{BASE_URL}/auth/login", json={"initData": init_data, "password": password})
    return resp

def run_tests():
    print(f"--- Verify Admin Security on {BASE_URL} ---")
    
    # 1. Test Superadmin Login
    print("\n[1] Testing Superadmin Login...")
    resp = login(SUPERADMIN_ID)
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        role = resp.json()["role"]
        print(f"SUCCESS: Logged in as {role}")
        admin_headers = {"Authorization": f"Bearer {token}"}
    else:
        print(f"FAILURE: {resp.status_code} {resp.text}")
        return

    # 2. Test Viewer Login
    print("\n[2] Testing Viewer Login...")
    resp_v = login(VIEWER_ID)
    if resp_v.status_code == 200:
        token_v = resp_v.json()["access_token"]
        role_v = resp_v.json()["role"]
        print(f"SUCCESS: Logged in as {role_v}")
        viewer_headers = {"Authorization": f"Bearer {token_v}"}
    else:
        print(f"FAILURE: {resp_v.status_code} {resp_v.text}")
        return

    # 3. Test Unauthorized Login
    print("\n[3] Testing Random User Login...")
    resp_r = login(RANDOM_ID)
    if resp_r.status_code == 403:
        print("SUCCESS: Random user denied (403)")
    else:
        print(f"FAILURE: Unexpected status {resp_r.status_code}")

    # 4. Test endpoints as Superadmin
    print("\n[4] Testing Endpoints (Superadmin)...")
    
    # Stats
    r = requests.get(f"{BASE_URL}/dashboard/stats", headers=admin_headers)
    print(f"Stats: {r.status_code}")
    
    # Logs
    r = requests.get(f"{BASE_URL}/logs", headers=admin_headers, stream=True)
    if r.status_code == 200:
        print("Logs: Access Granted (200)")
        # content = next(r.iter_lines()).decode()
        # print(f"First log line: {content}")
    else:
        print(f"Logs: Access Denied ({r.status_code}) - FAILURE")

    # 5. Test endpoints as Viewer
    print("\n[5] Testing Endpoints (Viewer)...")
    
    # Stats
    r = requests.get(f"{BASE_URL}/dashboard/stats", headers=viewer_headers)
    print(f"Stats: {r.status_code}")
    
    # Logs (Should Fail)
    r = requests.get(f"{BASE_URL}/logs", headers=viewer_headers)
    if r.status_code == 403:
        print("Logs: Access Denied (403) - SUCCESS")
    else:
        print(f"Logs: Access ({r.status_code}) - FAILURE (Should be 403)")

    # Tools Sanitization (Requires a tool in memory, might be empty but we check response type)
    print("\n[6] Testing Tools Sanitization...")
    r = requests.get(f"{BASE_URL}/tools", headers=viewer_headers)
    print(f"Tools response: {r.status_code}")
    if r.status_code == 200:
        tools = r.json()
        print(f"Tools count: {len(tools)}")
        # Check if any sensitive key is masked if tools exist
        # Manual check: "password" -> "********"
    

if __name__ == "__main__":
    # We need to install requests if not present? 
    # Assuming standard python env or user has requests.
    try:
        run_tests()
    except Exception as e:
        print(f"Error: {e}")
