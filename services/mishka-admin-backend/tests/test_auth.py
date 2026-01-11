import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.main import app
from src.config import settings

client = TestClient(app)

# Use fixture to patch settings for all tests
@pytest.fixture(autouse=True)
def mock_env():
    with patch.object(settings, 'SUPERADMIN_IDS', "123456"), \
         patch.object(settings, 'ADMIN_PASSWORD', "secret_pass"), \
         patch.object(settings, 'JWT_SECRET', "test_secret"):
        yield

def test_status_endpoint():
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_login_success():
    # Mock verify_telegram_auth
    with patch("src.main.verify_telegram_auth", return_value=123456):
        payload = {
            "initData": "dummy_init_data",
            "password": "secret_pass"
        }
        response = client.post("/auth/login", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["role"] == "admin"

def test_login_wrong_password():
    with patch("src.main.verify_telegram_auth", return_value=123456):
        payload = {
            "initData": "dummy_init_data",
            "password": "wrong_pass"
        }
        response = client.post("/auth/login", json=payload)
        assert response.status_code == 401

def test_login_unauthorized_user():
    # User ID 999999 is not in SUPERADMIN_IDS
    with patch("src.main.verify_telegram_auth", return_value=999999):
        payload = {
            "initData": "dummy_init_data",
            "password": "secret_pass"
        }
        response = client.post("/auth/login", json=payload)
        assert response.status_code == 403

def test_protected_route_without_token():
    response = client.get("/stats")
    assert response.status_code == 401

def test_protected_route_with_token():
    # 1. Login to get token
    with patch("src.main.verify_telegram_auth", return_value=123456):
        login_payload = {
            "initData": "dummy_init_data",
            "password": "secret_pass"
        }
        login_res = client.post("/auth/login", json=login_payload)
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        
        print(f"\nDEBUG TEST: Token obtained: {token}")
        
        # 2. Access protected route
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/stats", headers=headers)
        
        assert response.status_code == 200, f"Protected route failed: {response.status_code} - {response.text}"
        assert response.json()["user_requesting"] == 123456
