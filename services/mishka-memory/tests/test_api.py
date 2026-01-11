import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app

@pytest.fixture
def mock_redis(mocker):
    # Mock RedisManager methods
    mock = mocker.patch("src.main.redis_manager")
    mock.connect = mocker.AsyncMock()
    mock.close = mocker.AsyncMock()
    mock.add_message = mocker.AsyncMock()
    mock.get_history = mocker.AsyncMock(return_value=[
        {"role": "user", "content": "Hello", "timestamp": "2024-01-01T12:00:00"}
    ])
    return mock

from src.database import get_db

@pytest.fixture
def mock_db(mocker):
    # Mock Database session
    mock_session = mocker.AsyncMock()
    
    # Mock Result object
    mock_result = mocker.MagicMock()
    mock_scalars = mocker.MagicMock()
    mock_scalars.first.return_value = {
        "id": 123, 
        "username": "test", 
        "first_name": "Test",
        "created_at": "2024-01-01T12:00:00"
    }
    mock_result.scalars.return_value = mock_scalars
    
    mock_session.execute = mocker.AsyncMock(return_value=mock_result)
    mock_session.commit = mocker.AsyncMock()
    mock_session.refresh = mocker.AsyncMock()
    
    # Mock get_db dependency
    async def override_get_db():
        yield mock_session
        
    app.dependency_overrides[get_db] = override_get_db
    
    # Mock init_db to prevent startup connection
    mocker.patch("src.main.init_db", mocker.AsyncMock())
    
    return mock_session

@pytest.mark.asyncio
async def test_health_check(mock_redis):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_add_history(mock_redis):
    payload = {"role": "user", "content": "Test message"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/history/123", json=payload)
    
    assert response.status_code == 200
    assert response.json() == {"status": "added"}
    mock_redis.add_message.assert_called_once()
    
@pytest.mark.asyncio
async def test_get_context(mock_redis, mock_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/context/123?user_id=456")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["history"]) == 1
    assert data["history"][0]["content"] == "Hello"    
