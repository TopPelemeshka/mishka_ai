import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage
from src.consumer import RabbitMQConsumer

@pytest.fixture
def mock_graph(mocker):
    return mocker.patch("src.consumer.graph", new_callable=AsyncMock)

@pytest.fixture
def mock_producer(mocker):
    return mocker.patch("src.consumer.producer", new_callable=AsyncMock)

@pytest.mark.asyncio
async def test_process_message_flow(mock_graph, mock_producer):
    consumer = RabbitMQConsumer()
    
    # Mock message
    message = MagicMock()
    message.body = json.dumps({
        "user_id": 1, 
        "chat_id": 100, 
        "text": "Hello"
    }).encode()
    message.process.return_value.__aenter__.return_value = None
    message.process.return_value.__aexit__.return_value = None
    
    # Mock Graph result
    mock_graph.ainvoke.return_value = {
        "messages": [AIMessage(content="Response from AI")]
    }
    
    await consumer.process_message(message)
    
    # Verify graph called
    mock_graph.ainvoke.assert_called_once()
    
    # Verify producer called
    mock_producer.send_response.assert_called_once_with(100, "Response from AI")

@pytest.mark.asyncio
async def test_process_message_empty(mock_graph, mock_producer):
    consumer = RabbitMQConsumer()
    
    # Mock empty message
    message = MagicMock()
    message.body = json.dumps({"text": ""}).encode()
    message.process.return_value.__aenter__.return_value = None
    message.process.return_value.__aexit__.return_value = None
    
    await consumer.process_message(message)
    
    mock_graph.ainvoke.assert_not_called()
    mock_producer.send_response.assert_not_called()
