import pytest
from unittest.mock import AsyncMock, MagicMock
from src.producer import RabbitMQProducer

@pytest.mark.asyncio
async def test_producer_connect_success(mocker):
    mock_connect = mocker.patch("aio_pika.connect_robust", new_callable=AsyncMock)
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    
    mock_connect.return_value = mock_connection
    mock_connection.channel.return_value = mock_channel
    
    producer = RabbitMQProducer()
    await producer.connect()
    
    mock_connect.assert_called_once()
    assert producer.channel is mock_channel
    mock_channel.declare_queue.assert_called_with("bot_outbox", durable=True)

@pytest.mark.asyncio
async def test_producer_send_response_success(mocker):
    producer = RabbitMQProducer()
    producer.channel = AsyncMock()
    
    await producer.send_response(123, "Test Response")
    
    producer.channel.default_exchange.publish.assert_called_once()
    args = producer.channel.default_exchange.publish.call_args[0]
    message = args[0]
    assert b"Test Response" in message.body
    assert b"123" in message.body

@pytest.mark.asyncio
async def test_producer_send_not_connected():
    producer = RabbitMQProducer()
    with pytest.raises(RuntimeError):
        await producer.send_response(123, "Text")

@pytest.mark.asyncio
async def test_producer_close(mocker):
    producer = RabbitMQProducer()
    producer.connection = AsyncMock()
    await producer.close()
    producer.connection.close.assert_called_once()
