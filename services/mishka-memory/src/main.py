from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from src.database import get_db, init_db
from src.redis_manager import redis_manager
from src.models import User
from src.schemas import UserCreate, UserResponse, HistoryMessage, ContextResponse
import httpx
import os
from pydantic import BaseModel
from src.qdrant import qdrant_manager

LLM_EMBEDDING_URL = os.getenv("LLM_EMBEDDING_URL", "http://mishka-llm-provider:8000/v1/embeddings")

class FactRequest(BaseModel):
    text: str
    metadata: dict = {}

class SearchRequest(BaseModel):
    query: str
    limit: int = 5

app = FastAPI()

@app.on_event("startup")
async def startup():
    await init_db()
    await redis_manager.connect()

@app.on_event("shutdown")
async def shutdown():
    await redis_manager.close()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/users", response_model=UserResponse)
async def upsert_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user.id))
    db_user = result.scalars().first()
    
    if db_user:
        db_user.username = user.username
        db_user.first_name = user.first_name
    else:
        db_user = User(id=user.id, username=user.username, first_name=user.first_name)
        db.add(db_user)
    
    await db.commit()
    await db.refresh(db_user)
    return db_user

@app.post("/history/{chat_id}")
async def add_history(chat_id: int, message: HistoryMessage):
    if not message.timestamp:
        message.timestamp = datetime.utcnow().isoformat()
    
    await redis_manager.add_message(
        chat_id=chat_id, 
        role=message.role, 
        content=message.content, 
        timestamp=message.timestamp,
        user_name=message.user_name,
        created_at=message.created_at or message.timestamp
    )
    return {"status": "added"}

@app.get("/context/{chat_id}", response_model=ContextResponse)
async def get_context(chat_id: int, user_id: int = None, db: AsyncSession = Depends(get_db)):
    # 1. Get History from Redis
    history = await redis_manager.get_history(chat_id)
    
    # 2. Get User from Postgres (if user_id provided)
    user_data = None
    if user_id:
        result = await db.execute(select(User).where(User.id == user_id))
        user_data = result.scalars().first()
    
    return ContextResponse(
        user=user_data,
        history=history
    )

@app.get("/tools/config")
async def get_tools_config():
    """Return available tools manifests."""
    return [
        {
            "name": "get_weather",
            "description": "Узнать текущую погоду в указанном городе.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Название города (например, Москва, Токио)"
                    }
                },
                "required": ["city"]
            },
            "endpoint": "http://tool-weather:8000/weather"
        },
        {
            "name": "remember_fact",
            "description": "Сохранить факт в долгосрочную память. Используй, если пользователь просит запомнить или сообщает важную информацию о себе.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Текст факта (например, 'Влад любит суши')."
                    }
                },
                "required": ["text"]
            },
            "endpoint": "http://tool-memory:8000/run"
        }
    ]

@app.post("/facts/add")
async def add_fact(request: FactRequest):
    if not qdrant_manager:
        raise HTTPException(status_code=503, detail="Vector DB not available")
    
    # 1. Get Embedding
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                LLM_EMBEDDING_URL,
                json={
                    "content": request.text,
                    "task_type": "retrieval_document"
                },
                timeout=30.0
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"LLM Error: {resp.text}")
            
            embedding = resp.json().get("embedding")
    except Exception as e:
         raise HTTPException(status_code=502, detail=f"Embedding failed: {e}")

    # 2. Save to Qdrant
    point_id = qdrant_manager.add_fact(request.text, embedding, request.metadata)
    return {"status": "ok", "id": point_id}


@app.post("/facts/search")
async def search_facts(request: SearchRequest):
    if not qdrant_manager:
        raise HTTPException(status_code=503, detail="Vector DB not available")

    # 1. Get Embedding for Query
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                LLM_EMBEDDING_URL,
                json={
                    "content": request.query,
                    "task_type": "retrieval_query"
                },
                timeout=30.0
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"LLM Error: {resp.text}")
            
            embedding = resp.json().get("embedding")
    except Exception as e:
         raise HTTPException(status_code=502, detail=f"Embedding failed: {e}")

    # 2. Search Qdrant
    results = qdrant_manager.search_facts(embedding, limit=request.limit)
    return {"results": results}
