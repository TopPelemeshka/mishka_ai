import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from src.graph import agent_node, tool_node, should_continue, AgentState

@pytest.mark.asyncio
async def test_tool_calling_flow(mocker):
    # 1. Mock list_tools
    mocker.patch("src.graph.list_tools", return_value=[
        {
            "name": "get_weather",
            "endpoint": "http://tool-weather:8000/weather"
        }
    ])
    
    # 2. Mock get_context (empty)
    mocker.patch("src.graph.get_context", return_value={"history": []})
    
    # 3. Mock LLM - Step 1: LLM decides to call a tool
    mock_llm_response = MagicMock()
    mock_llm_response.status_code = 200
    mock_llm_response.json.return_value = {
        "choices": [{"message": {"content": '{"tool": "get_weather", "args": {"city": "Moscow"}}'}}]
    }
    
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_llm_response
    mock_client.__aenter__.return_value = mock_client
    
    mocker.patch("httpx.AsyncClient", return_value=mock_client)
    
    # Run agent_node
    state = {"messages": [HumanMessage(content="Какая погода в Москве?")]}
    result = await agent_node(state)
    
    assert "messages" in result
    assert result["messages"][0].content == '{"tool": "get_weather", "args": {"city": "Moscow"}}'
    
    # 4. Check should_continue
    state["messages"].extend(result["messages"])
    state["tools"] = result["tools"]
    next_step = should_continue(state)
    assert next_step == "tools"
    
    # 5. Mock tool execution
    mock_tool_resp = MagicMock()
    mock_tool_resp.status_code = 200
    mock_tool_resp.json.return_value = {"temperature": "+15°C"}
    
    # Need to re-mock or use another mock for the tool call
    # Let's mock httpx.AsyncClient.post again for the tool_node
    mock_client.post.return_value = mock_tool_resp
    
    tool_result = await tool_node(state)
    assert "Результат get_weather" in tool_result["messages"][0].content
    assert "+15°C" in tool_result["messages"][0].content
