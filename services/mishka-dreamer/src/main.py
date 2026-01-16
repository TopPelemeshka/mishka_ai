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
            resp = await client.get(f"{MEMORY_API_URL}/facts/all", params={"limit": 2000})
            if resp.status_code != 200:
                logger.error("Failed to fetch facts")
                return
            facts = resp.json()
            
        logger.info(f"Loaded {len(facts)} facts.")
        if not facts: return
        
        # 2. Greedy Clustering (Sim > 0.85)
        # Using numpy for speed
        vectors = np.array([f["vector"] for f in facts])
        ids = [f["id"] for f in facts]
        
        # Normalize vectors for dot product = cosine sim
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        normalized = vectors / norms
        
        active_indices = set(range(len(facts)))
        clusters = []
        
        while active_indices:
            idx = active_indices.pop()
            current_cluster = [idx]
            
            # Compare with remaining
            # This is O(N^2) worst case but for N=2000 it's 4M ops, handled by python/numpy in <1s.
            
            # Vectorized comparison against ALL, then filter by active
            sims = np.dot(normalized, normalized[idx])
            
            # Find indices with sim > 0.85
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
                
                # Delete old
                for f in cluster:
                    async with httpx.AsyncClient() as client:
                        await client.delete(f"{MEMORY_API_URL}/facts/{f['id']}")
                        
                # Add new
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{MEMORY_API_URL}/facts/add",
                        json={
                            "text": merged_text,
                            "metadata": {"source": "dreamer", "merged_count": len(cluster)}
                        }
                    )
        
        # 4. Garbage Collection (Placeholder as per task)
        # "If updated_at < now - 60d ... delete"
        # We need updated_at in metadata. Assuming it exists or we add it. 
        # Skipping for now to focus on Consolidation as prioritized.
                    
    except Exception as e:
        logger.exception(f"Dreamer Job Failed: {e}")
    
    logger.info("Dream Complete.")

if __name__ == "__main__":
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_dreamer_job, 'cron', hour=4, minute=0)
    
    logger.info("Mishka Dreamer started (Schedule: 04:00)")
    scheduler.start()
    
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
