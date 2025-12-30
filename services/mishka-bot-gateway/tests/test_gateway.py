import pytest
import datetime
from unittest.mock import AsyncMock, MagicMock
from src.bot import message_handler, send_message_to_user

@pytest.fixture
def mock_rmq(mocker):
    return mocker.patch("src.bot.rmq", new_callable=AsyncMock)

@pytest.fixture
def mock_bot(mocker):
    return mocker.patch("src.bot.bot", new_callable=AsyncMock)

@pytest.mark.asyncio
async def test_message_handler_publishes_to_rmq(mock_rmq):
    # Mock Telegram Message
    message = AsyncMock()
    message.text = "Hello Mishka"
    message.from_user.id = 123
    message.from_user.username = "user"
    message.from_user.full_name = "User Name"
    message.chat.id = 456
    message.date = datetime.datetime.now()

    await message_handler(message)

    # Verify publish called
    mock_rmq.publish.assert_called_once()
    args = mock_rmq.publish.call_args[0]
    queue_name = args[0]
    event = args[1]
    
    assert queue_name == "chat_events"
    assert event["user_id"] == 123
    assert event["text"] == "Hello Mishka"
    assert event["chat_id"] == 456

@pytest.mark.asyncio
async def test_send_message_to_user_uses_bot(mock_bot):
    data = {"chat_id": 789, "text": "Response from Brain"}
    
    await send_message_to_user(data)
    
    # Verify bot.send_message called
    mock_bot.send_message.assert_called_once_with(chat_id=789, text="Response from Brain")

@pytest.mark.asyncio
async def test_send_message_empty_data(mock_bot):
    await send_message_to_user({})
    mock_bot.send_message.assert_not_called()

from src.rmq import RabbitMQClient

@pytest.mark.asyncio
async def test_rabbitmq_client_methods(mocker):
    # Mock aio_pika
    mock_connect = mocker.patch("aio_pika.connect_robust", new_callable=AsyncMock)
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_connect.return_value = mock_connection
    mock_connection.channel.return_value = mock_channel
    
    msg = {"test": "data"}
    
    client = RabbitMQClient()
    await client.connect()
    
    # Check connect
    mock_connect.assert_called_once()
    assert client.channel is mock_channel
    
    # Check publish
    await client.publish("queue", msg)
    mock_channel.default_exchange.publish.assert_called_once()
    
    # Check consume
    mock_queue = AsyncMock()
    mock_channel.declare_queue.return_value = mock_queue
    callback = AsyncMock()
    await client.consume("queue", callback)
    mock_queue.consume.assert_called_once()
    
    # Check close
    await client.close()
    mock_connection.close.assert_called_once()

@pytest.mark.asyncio
async def test_bot_send_message_error(mock_bot):
    # Test error handling
    mock_bot.send_message.side_effect = Exception("Telegram Error")
    data = {"chat_id": 123, "text": "Hi"}
    
    # Should not raise exception (caught/logged)
    await send_message_to_user(data)
    mock_bot.send_message.assert_called_once()
