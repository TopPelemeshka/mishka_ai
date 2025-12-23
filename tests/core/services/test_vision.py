import pytest
from unittest.mock import AsyncMock, patch
from src.core.services.vision import VisionService

@pytest.mark.asyncio
async def test_describe_image(mocker):
    """Тест описания изображения."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value.content = "A funny bear"
    
    # Патчим класс ChatGoogleGenerativeAI в модуле vision
    with patch("src.core.services.vision.ChatGoogleGenerativeAI", return_value=mock_llm):
        service = VisionService()
        description = await service.describe_image(b"fake_image_bytes")
        
        assert description == "A funny bear"
        mock_llm.ainvoke.assert_called_once()
