import pytest
from unittest.mock import MagicMock, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage
from src.graph import agent_node, AgentState

@pytest.mark.asyncio
async def test_agent_node_success(mocker):
    # Mock httpx.AsyncClient
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello Human!"}}]
    }
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    
    mocker.patch("httpx.AsyncClient", return_value=mock_client)
    
    state = {"messages": [HumanMessage(content="Hi")]}
    result = await agent_node(state)
    
    assert "messages" in result
    assert isinstance(result["messages"][0], AIMessage)
    assert result["messages"][0].content == "Hello Human!"

@pytest.mark.asyncio
async def test_agent_node_error(mocker):
    # Mock httpx error
    mock_client = AsyncMock()
    mock_client.post.side_effect = Exception("Connection Error")
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    
    mocker.patch("httpx.AsyncClient", return_value=mock_client)
    
    state = {"messages": [HumanMessage(content="Hi")]}
    result = await agent_node(state)
    
    assert "messages" in result
    assert "Ошибка LLM" in result["messages"][0].content
