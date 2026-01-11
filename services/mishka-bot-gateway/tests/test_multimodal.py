import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.bot import message_handler
from aiogram.types import Message, Chat, User, PhotoSize, Voice
from datetime import datetime

@pytest.mark.asyncio
async def test_image_message_handling():
    """
    Test that an image message triggers the correct event processing:
    1. Download file.
    2. Publish 'image_message' event to RabbitMQ.
    """
    # Mock Objects
    mock_bot = AsyncMock()
    mock_rmq = AsyncMock()
    
    # Mock File Info
    mock_file = MagicMock()
    mock_file.file_id = "test_file_id"
    mock_file.file_unique_id = "unique_id"
    mock_file.file_path = "photos/file_0.jpg"
    
    mock_bot.get_file.return_value = mock_file
    mock_bot.download_file.return_value = None
    
    # Mock User Message
    mock_message = MagicMock(spec=Message)
    mock_message.text = None
    mock_message.caption = "Look at this cat"
    mock_message.photo = [MagicMock(spec=PhotoSize)]
    mock_message.photo[-1].file_id = "test_file_id"
    mock_message.voice = None
    
    mock_message.chat = Chat(id=123, type="private")
    mock_message.from_user = User(id=456, is_bot=False, first_name="TestUser", username="testuser")
    mock_message.date = datetime.now()
    
    # Patch dependencies
    with patch("src.bot.bot", mock_bot), \
         patch("src.bot.rmq", mock_rmq), \
         patch("src.bot.is_chat_allowed", return_value=True):
         
         await message_handler(mock_message)
         
         # Verification
         # 1. Check get_file called
         mock_bot.get_file.assert_called_with("test_file_id")
         
         # 2. Check download called with correct path
         expected_path = "/media/unique_id.jpg"
         mock_bot.download_file.assert_called()
         args = mock_bot.download_file.call_args
         assert args[0][1] == expected_path
         
         # 3. Check RMQ publish
         mock_rmq.publish.assert_called()
         event = mock_rmq.publish.call_args[0][1]
         assert event["type"] == "image_message"
         assert event["file_path"] == expected_path
         assert event["text"] == "Look at this cat"
