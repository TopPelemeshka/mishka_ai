from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import os
import sys

# Configure Loguru
# logger.remove() # We'll just use print for now in this simple tool or standard logging
# logger.add(sys.stderr, level="INFO")

app = FastAPI()

MEMORY_SERVICE_URL = os.getenv("MEMORY_SERVICE_URL", "http://mishka-memory:8000/facts/add")

class RememberRequest(BaseModel):
    text: str

@app.get("/manifest")
async def get_manifest():
    return {
        "name": "remember_fact",
        "description": "Сохранить факт в долгосрочную память. Используй, если пользователь просит запомнить или сообщает важную информацию о себе.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Текст факта, который нужно запомнить. Должен быть полным и понятным вне контекста (например, 'Влад любит суши')."
                }
            },
            "required": ["text"]
        }
    }

@app.post("/run")
async def run_tool(request: RememberRequest):
    print(f"Tool 'remember_fact' called with: {request.text}")
    
    async with httpx.AsyncClient() as client:
        try:
            # Call memory service to save the fact
            # The memory service expects {"text": "...", "metadata": {}}
            payload = {
                "text": request.text,
                "metadata": {"source": "user_tool_call"}
            }
            resp = await client.post(MEMORY_SERVICE_URL, json=payload, timeout=10.0)
            
            if resp.status_code == 200:
                data = resp.json()
                return {"status": "success", "message": f"Факт сохранен. ID: {data.get('id')}"}
            else:
                print(f"Memory Service Error: {resp.status_code} {resp.text}")
                raise HTTPException(status_code=502, detail=f"Memory Service Error: {resp.text}")
                
        except Exception as e:
            print(f"Exception calling memory service: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok"}
