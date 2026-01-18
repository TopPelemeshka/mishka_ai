import asyncio
import os
import httpx
import json
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import pytz

MEMORY_API_URL = os.getenv("MEMORY_API_URL", "http://mishka-memory:8000")
LLM_PROVIDER_URL = os.getenv("LLM_PROVIDER_URL", "http://mishka-llm-provider:8000/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")

from fastapi import FastAPI
import uvicorn
from src.log_handler import setup_logger, start_log_handler, stop_log_handler

app = FastAPI(title="Mishka Archivist")
scheduler = AsyncIOScheduler()

# Initialize Logging
setup_logger()

async def extract_facts_from_chunk(chunk, user_id):
    """Sends chunk to LLM to extract facts."""
    dialog_text = "\n".join([f"{m['role']} ({m.get('created_at','')}): {m['content']}" for m in chunk])
    
    prompt = f"""
    Analyze this dialogue chunk from user {user_id}.
    Extract KEY facts about the user's life, preferences, relationships, or plans.
    Ignore trivial chatter.
    Return a valid JSON list of strings.
    Example: ["User likes sushi", "User has a cat named Luna"]
    
    Dialogue:
    {dialog_text}
    """
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                LLM_PROVIDER_URL,
                json={
                    "model": LLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"}
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                # Clean markdown if present
                if "```json" in content:
                    content = content.replace("```json", "").replace("```", "")
                
                result = json.loads(content)
                # Handle various JSON structures LLM might return
                if isinstance(result, list): return result
                if isinstance(result, dict):
                    # Try to find list values
                    for k, v in result.items():
                        if isinstance(v, list): return v
                return []
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return []

async def save_fact(fact, chat_id):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{MEMORY_API_URL}/facts/add",
                json={
                    "text": fact,
                    "metadata": {"source": "archivist", "chat_id": chat_id, "date": datetime.utcnow().isoformat()}
                }
            )
            logger.info(f"Saved fact: {fact}")
    except Exception as e:
        logger.error(f"Failed to save fact: {e}")

async def run_archivist_job():
    logger.info("Starting Daily Archival Job...")
    
    try:
        # 1. Get Active Chats
        active_chats = []
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{MEMORY_API_URL}/chats/active", timeout=10.0)
                if resp.status_code == 200:
                    active_chats = resp.json()
            except Exception as e:
                logger.error(f"Failed to fetch active chats: {e}")
                
        logger.info(f"Found {len(active_chats)} active chats.")
        
        for chat_id in active_chats:
            # 2. Get 24h History
            async with httpx.AsyncClient() as client:
                try:
                    resp = await client.get(f"{MEMORY_API_URL}/context/{chat_id}", params={"hours": 24, "limit": 1000}, timeout=10.0)
                    if resp.status_code != 200: continue
                    history = resp.json().get("history", [])
                except Exception:
                    continue
            
            if not history: continue
            logger.info(f"Processing {len(history)} messages for chat {chat_id}")
            
            # 3. Chunking (Window 50, Overlap 10)
            window = 50
            overlap = 10
            step = window - overlap
            
            for i in range(0, len(history), step):
                chunk = history[i:i+window]
                if len(chunk) < 5: continue # Skip tiny chunks
                
                facts = await extract_facts_from_chunk(chunk, chat_id)
                for fact in facts:
                    await save_fact(fact, chat_id)
                    
    except Exception as e:
        logger.exception(f"Archivist Job Failed: {e}")
    
    logger.info("Job Complete.")

@app.on_event("startup")
async def startup():
    await start_log_handler()
    # Schedule at 03:00 AM UTC
    scheduler.add_job(run_archivist_job, 'cron', hour=3, minute=0)
    scheduler.start()
    logger.info("Mishka Archivist started (Schedule: 03:00)")

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()
    await stop_log_handler()

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
