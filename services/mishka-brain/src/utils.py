import os
import httpx
from loguru import logger

MEMORY_SERVICE_URL = os.getenv("MEMORY_SERVICE_URL", "http://mishka-memory:8000")

async def save_message(chat_id: int, role: str, content: str):
    """Save message to Memory Service."""
    if not content:
        return
        
    async with httpx.AsyncClient() as client:
        try:
            payload = {"role": role, "content": content}
            resp = await client.post(f"{MEMORY_SERVICE_URL}/history/{chat_id}", json=payload)
            resp.raise_for_status()
            logger.debug(f"Saved {role} message to memory for chat {chat_id}")
        except Exception as e:
            logger.error(f"Failed to save message to memory: {e}")

async def get_context(chat_id: int) -> dict:
    """Get context (history + user) from Memory Service."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{MEMORY_SERVICE_URL}/context/{chat_id}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to get context from memory: {e}")
            return {"history": [], "user": None}

async def list_tools() -> list:
    """Fetch available tools from Memory Service."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{MEMORY_SERVICE_URL}/tools/config")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            return []
