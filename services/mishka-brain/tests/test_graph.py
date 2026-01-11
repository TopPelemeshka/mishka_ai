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
    
    # Mock get_context
    mock_get_context = mocker.patch("src.graph.get_context", new_callable=AsyncMock)
    mock_get_context.return_value = {
        "history": [
            {"role": "user", "content": "Prev User"},
            {"role": "assistant", "content": "Prev Bot"}
        ]
    }
    
    state = {"messages": [HumanMessage(content="Hi")], "chat_id": 123}
    result = await agent_node(state)
    
    assert "messages" in result
    assert isinstance(result["messages"][0], AIMessage)
    assert result["messages"][0].content == "Hello Human!"
    
    # Verify call to LLM included history
    # We inspect the arguments passed to client.post
    args, kwargs = mock_client.post.call_args
    payload = kwargs["json"]
    messages = payload["messages"]
    
    # Expect: System + User(Prev) + Model(Prev) + User(Current)
    assert len(messages) == 4
    assert messages[1]["content"] == "Prev User"
    assert messages[2]["content"] == "Prev Bot"
    assert messages[3]["content"] == "Hi"

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
    assert "Ошибка Brain" in result["messages"][0].content
