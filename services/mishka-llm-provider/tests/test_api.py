import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app
from unittest.mock import MagicMock

@pytest.fixture
def mock_genai(mocker):
    """Mock google.generativeai module"""
    mock = mocker.patch("src.main.genai")
    
    # Mock model and chat
    mock_model = MagicMock()
    mock.GenerativeModel.return_value = mock_model
    
    mock_chat = MagicMock()
    mock_model.start_chat.return_value = mock_chat
    
    # Mock send_message response
    mock_response = MagicMock()
    mock_response.text = "Hello from Mock Gemini!"
    mock_chat.send_message.return_value = mock_response
    
    return mock

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_chat_completions_no_api_key(mocker):
    # Ensure no ENV key
    mocker.patch.dict("os.environ", {}, clear=True)
    mocker.patch("src.main.GOOGLE_API_KEY", None) # Patch global var if it was already loaded
    
    payload = {
        "model": "gemini-pro",
        "messages": [{"role": "user", "content": "Hi"}]
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/v1/chat/completions", json=payload)
    
    assert response.status_code == 401
    assert "API Key not provided" in response.json()["detail"]

@pytest.mark.asyncio
async def test_chat_completions_success(mock_genai, mocker):
    mocker.patch("src.main.GOOGLE_API_KEY", "dummy_env_key")
    
    payload = {
        "model": "gemini-pro",
        "messages": [{"role": "user", "content": "Tell me a joke"}]
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/v1/chat/completions", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "choices" in data
    assert data["choices"][0]["message"]["content"] == "Hello from Mock Gemini!"
    
    # Verify mock usage
    mock_genai.GenerativeModel.assert_called_with("gemini-pro")

@pytest.mark.asyncio
async def test_chat_completions_invalid_role(mocker):
    mocker.patch("src.main.GOOGLE_API_KEY", "dummy_env_key")
    
    payload = {
        "model": "gemini-pro",
        "messages": [{"role": "system", "content": "You are a bot"}]
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/v1/chat/completions", json=payload)
    
    assert response.status_code == 400
    assert "Last message must be from user" in response.json()["detail"]
