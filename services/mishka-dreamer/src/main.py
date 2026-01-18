import asyncio
import os
import httpx
import json
import numpy as np
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

MEMORY_API_URL = os.getenv("MEMORY_API_URL", "http://mishka-memory:8000")
LLM_PROVIDER_URL = os.getenv("LLM_PROVIDER_URL", "http://mishka-llm-provider:8000/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")

from fastapi import FastAPI
import uvicorn
from src.log_handler import setup_logger, start_log_handler, stop_log_handler

app = FastAPI(title="Mishka Dreamer")
scheduler = AsyncIOScheduler()

setup_logger()

def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

async def merge_cluster(cluster_facts):
    """Asks LLM to merge facts."""
    texts = [f["text"] for f in cluster_facts]
    prompt = f"""
    Consolidate these related facts into a single, concise fact.
    Retain all key details (names, dates, preferences) but remove redundancy.
    
    Facts:
    {json.dumps(texts, indent=2, ensure_ascii=False)}
    
    Return pure text of the merged fact.
    """
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                LLM_PROVIDER_URL,
                json={
                    "model": LLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                }
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Merge failed: {e}")
        return None

async def run_dreamer_job():
    logger.info("Starting Nightly Dream (Consolidation)...")
    
    try:
        # 1. Fetch All Facts
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{MEMORY_API_URL}/facts/all", params={"limit": 2000}, timeout=10.0)
                if resp.status_code != 200:
                    logger.error("Failed to fetch facts")
                    return
                facts = resp.json()
            except Exception as e:
                logger.error(f"Fetch facts failed: {e}")
                return
            
        logger.info(f"Loaded {len(facts)} facts.")
        if not facts: return
        
        # 2. Greedy Clustering (Sim > 0.85)
        # Using numpy for speed
        try:
            vectors = np.array([f["vector"] for f in facts])
            # ... (Existing logic kept implicitly, I should paste it) ...
            # Wait, I need to copy the logic.
            
            # Reusing existing logic
            ids = [f["id"] for f in facts]
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            normalized = vectors / norms
            
            active_indices = set(range(len(facts)))
            clusters = []
            
            while active_indices:
                idx = active_indices.pop()
                current_cluster = [idx]
                sims = np.dot(normalized, normalized[idx])
                candidates = np.where(sims > 0.85)[0]
                for c_idx in candidates:
                    if c_idx in active_indices and c_idx != idx:
                        current_cluster.append(c_idx)
                        active_indices.remove(c_idx)
                
                if len(current_cluster) > 1:
                    clusters.append([facts[i] for i in current_cluster])

            logger.info(f"Found {len(clusters)} clusters to merge.")
            
            # 3. Merge Clusters
            for cluster in clusters:
                merged_text = await merge_cluster(cluster)
                if merged_text:
                    logger.info(f"Merged {len(cluster)} facts into: {merged_text}")
                    for f in cluster:
                        async with httpx.AsyncClient() as client:
                            await client.delete(f"{MEMORY_API_URL}/facts/{f['id']}")
                    async with httpx.AsyncClient() as client:
                        await client.post(
                            f"{MEMORY_API_URL}/facts/add",
                            json={
                                "text": merged_text,
                                "metadata": {"source": "dreamer", "merged_count": len(cluster)}
                            }
                        )
        except Exception as e:
            logger.error(f"Clustering error: {e}")

    except Exception as e:
        logger.exception(f"Dreamer Job Failed: {e}")
    
    logger.info("Dream Complete.")

@app.on_event("startup")
async def startup():
    await start_log_handler()
    scheduler.add_job(run_dreamer_job, 'cron', hour=4, minute=0)
    scheduler.start()
    logger.info("Mishka Dreamer started (Schedule: 04:00)")

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()
    await stop_log_handler()

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
