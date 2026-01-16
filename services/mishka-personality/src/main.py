from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from typing import List
import uuid

from src.database import get_db, engine, Base
from src.models import Personality, EvolutionLog
from src.schemas import PersonalityCreate, PersonalityResponse, EvolutionLogResponse, CurrentPromptResponse, EvolveRequest

app = FastAPI(title="Mishka Personality Service")

# --- CRUD Operations ---

@app.on_event("startup")
async def startup_event():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Seed default personality
    async with engine.begin() as conn:
        # We need a session to seed
        pass # Handling seeding in a separate function below to use session

    # Simple seed hack:
    async for session in get_db():
        result = await session.execute(select(Personality).where(Personality.name == "Mishka Default"))
        existing = result.scalars().first()
        if not existing:
            default_p = Personality(
                name="Mishka Default",
                base_prompt="You are Mishka, a friendly and helpful AI assistant.",
                is_active=True
            )
            session.add(default_p)
            await session.commit()
            print("Seeded default personality.")
        break # Run once


@app.get("/personalities", response_model=List[PersonalityResponse])
async def list_personalities(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Personality))
    return result.scalars().all()

@app.post("/personalities", response_model=PersonalityResponse)
async def create_personality(p: PersonalityCreate, db: AsyncSession = Depends(get_db)):
    new_p = Personality(name=p.name, base_prompt=p.base_prompt)
    db.add(new_p)
    await db.commit()
    await db.refresh(new_p)
    return new_p

@app.put("/personalities/{p_id}", response_model=PersonalityResponse)
async def update_personality(p_id: uuid.UUID, p: PersonalityCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Personality).where(Personality.id == p_id))
    existing = result.scalars().first()
    if not existing:
        raise HTTPException(status_code=404, detail="Personality not found")
    
    existing.name = p.name
    existing.base_prompt = p.base_prompt
    
    await db.commit()
    await db.refresh(existing)
    return existing

@app.post("/personalities/{p_id}/activate", response_model=PersonalityResponse)
async def activate_personality(p_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # Deactivate all
    await db.execute(update(Personality).values(is_active=False))
    
    # Activate one
    result = await db.execute(select(Personality).where(Personality.id == p_id))
    p = result.scalars().first()
    if not p:
        raise HTTPException(status_code=404, detail="Personality not found")
    
    p.is_active = True
    await db.commit()
    await db.refresh(p)
    return p

@app.get("/current", response_model=CurrentPromptResponse)
async def get_current_prompt(db: AsyncSession = Depends(get_db)):
    # Get active personality
    result = await db.execute(select(Personality).where(Personality.is_active == True))
    p = result.scalars().first()
    
    if not p:
        # Fallback if no active (should check seed)
        return CurrentPromptResponse(text="You are a helpful assistant.", traits=None)
    
    # Get latest evolution log
    log_result = await db.execute(
        select(EvolutionLog)
        .where(EvolutionLog.personality_id == p.id)
        .order_by(EvolutionLog.created_at.desc())
        .limit(1)
    )
    last_log = log_result.scalars().first()
    traits = last_log.traits if last_log else None
    
    full_text = p.base_prompt
    if traits:
        full_text += f"\n\nAcquired Traits:\n{traits}"
        
    return CurrentPromptResponse(text=full_text, traits=traits)

@app.post("/evolve")
async def evolve_personality(req: EvolveRequest, db: AsyncSession = Depends(get_db)):
    import os
    import httpx
    
    ALLOWED_GROUP_ID = os.getenv("ALLOWED_GROUP_ID")
    MEMORY_API_URL = os.getenv("MEMORY_API_URL", "http://mishka-memory:8000")
    LLM_PROVIDER_URL = os.getenv("LLM_PROVIDER_URL", "http://mishka-llm-provider:8000/v1/chat/completions")
    
    if not ALLOWED_GROUP_ID:
        raise HTTPException(status_code=400, detail="ALLOWED_GROUP_ID not configured")

    # 1. Fetch History
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{MEMORY_API_URL}/context/{ALLOWED_GROUP_ID}")
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Failed to fetch memory")
            data = resp.json()
            history = data.get("history", [])
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Memory Error: {e}")

    if not history:
        return {"status": "skipped", "reason": "No history found"}

    # 2. Prepare Prompt
    # Get current traits
    current_res = await get_current_prompt(db)
    current_traits = current_res.traits or "None"
    
    dialog_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-50:]])
    
    system_prompt = (
        "You are an expert psychologist AI. Your goal is to analyze the chat history of an AI bot "
        "and evolve its personality traits based on its experiences.\n"
        "Output ONLY the new list of traits as bullet points. No other text."
    )
    
    user_prompt = (
        f"Analyze this dialogue:\n---\n{dialog_text}\n---\n\n"
        f"Current Traits:\n{current_traits}\n\n"
        "How has the bot's experience changed? What topics does it like? How does it relate to users? "
        "Update the list of Traits to reflect this experience. Return only the text of the traits."
    )

    # 3. Call LLM
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            llm_resp = await client.post(
                LLM_PROVIDER_URL,
                json={
                    "model": os.getenv("LLM_MODEL", "gemini-1.5-flash"), # Use configured model
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7
                }
            )
            if llm_resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"LLM Error: {llm_resp.text}")
            
            llm_data = llm_resp.json()
            new_traits = llm_data["choices"][0]["message"]["content"].strip()
            
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM Call Failed: {e}")

    # 4. Save to DB
    # Get active personality ID
    result = await db.execute(select(Personality).where(Personality.is_active == True))
    p = result.scalars().first()
    if not p:
         raise HTTPException(status_code=404, detail="No active personality")

    new_log = EvolutionLog(
        personality_id=p.id,
        traits=new_traits,
        reason=req.reason
    )
    db.add(new_log)
    await db.commit()

    return {"status": "Evolved", "traits": new_traits}

@app.get("/personalities/{p_id}/history", response_model=List[EvolutionLogResponse])
async def get_history(p_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EvolutionLog)
        .where(EvolutionLog.personality_id == p_id)
        .order_by(EvolutionLog.created_at.desc())
    )
    return result.scalars().all()

from src.schemas import RollbackRequest

@app.post("/evolution/{p_id}/rollback", response_model=EvolutionLogResponse)
async def rollback_evolution(p_id: uuid.UUID, req: RollbackRequest, db: AsyncSession = Depends(get_db)):
    # 1. Fetch Target Log
    result = await db.execute(select(EvolutionLog).where(EvolutionLog.id == req.target_log_id))
    target_log = result.scalars().first()
    if not target_log:
        raise HTTPException(status_code=404, detail="Target log not found")
    
    if target_log.personality_id != p_id:
        raise HTTPException(status_code=400, detail="Log belongs to another personality")

    # 2. Create NEW log with OLD traits
    # This preserves history while reverting state
    new_log = EvolutionLog(
        personality_id=p_id,
        traits=target_log.traits,
        reason=f"Rollback to {target_log.created_at.strftime('%Y-%m-%d %H:%M')}"
    )
    db.add(new_log)
    await db.commit()
    await db.refresh(new_log)
    
    return new_log

@app.post("/reset")
async def reset_personality(db: AsyncSession = Depends(get_db)):
    # Get active
    result = await db.execute(select(Personality).where(Personality.is_active == True))
    p = result.scalars().first()
    if not p:
        raise HTTPException(status_code=404, detail="No active personality")

    # Create empty log
    new_log = EvolutionLog(
        personality_id=p.id,
        traits=None,
        reason="Manual Reset"
    )
    db.add(new_log)
    await db.commit()
    return {"status": "Reset traits"}
