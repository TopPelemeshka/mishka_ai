"""
Mishka LLM Provider - использует прямые REST вызовы к Gemini API с явной настройкой прокси.
"""
import os
import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from src.config import LLM_PROXY

app = FastAPI(title="Mishka LLM Provider")

# Gemini API Configuration
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

# Proxy Configuration
PROXY_CONFIG = None
if LLM_PROXY:
    print(f"Using Proxy: {LLM_PROXY}")
    PROXY_CONFIG = {
        "http://": LLM_PROXY,
        "https://": LLM_PROXY,
    }
    
    # Verify Proxy
    try:
        print("--- PROXY DIAGNOSTICS ---")
        with httpx.Client(proxy=LLM_PROXY, timeout=10) as client:
            resp = client.get("https://ipinfo.io/json")
            data = resp.json()
            print(f"   IP: {data.get('ip')}")
            print(f"   Country: {data.get('country')} ({data.get('city')})")
        print("-------------------------")
    except Exception as e:
        print(f"WARNING: Proxy verification failed: {e}")
else:
    print("WARNING: No proxy configured!")


class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "gemini-2.0-flash"
    messages: List[Message]
    temperature: Optional[float] = 0.7
    api_key: Optional[str] = None


def convert_messages_to_gemini_format(messages: List[Message]) -> dict:
    """
    Конвертирует сообщения в формат Gemini API.
    """
    contents = []
    system_instruction = None
    
    for msg in messages:
        if msg.role == "system":
            system_instruction = msg.content
        elif msg.role == "user":
            contents.append({
                "role": "user",
                "parts": [{"text": msg.content}]
            })
        elif msg.role in ("assistant", "model"):
            contents.append({
                "role": "model", 
                "parts": [{"text": msg.content}]
            })
    
    result = {"contents": contents}
    if system_instruction:
        result["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    
    return result


@app.post("/v1/chat/completions")
async def chat_completions(request_body: ChatCompletionRequest, request: Request):
    try:
        # Determine API Key (Header > Body > Env)
        api_key = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header.split(" ")[1]
        if not api_key:
            api_key = request_body.api_key
        if not api_key:
            api_key = GOOGLE_API_KEY
        if not api_key:
            raise HTTPException(status_code=401, detail="API Key not provided")

        # Build Gemini API URL
        model_name = request_body.model
        url = f"{GEMINI_API_URL}/{model_name}:generateContent?key={api_key}"
        
        # Convert messages
        payload = convert_messages_to_gemini_format(request_body.messages)
        payload["generationConfig"] = {
            "temperature": request_body.temperature
        }
        
        print(f"Calling Gemini API: model={model_name}")
        
        # Make request with explicit proxy
        async with httpx.AsyncClient(proxy=LLM_PROXY, timeout=60.0) as client:
            response = await client.post(url, json=payload)
            
            if response.status_code != 200:
                error_detail = response.text
                print(f"Gemini API Error: {response.status_code} - {error_detail}")
                raise HTTPException(status_code=response.status_code, detail=error_detail)
            
            data = response.json()
        
        # Extract response text
        candidates = data.get("candidates", [])
        if not candidates:
            raise HTTPException(status_code=500, detail="No response from Gemini")
        
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        text = parts[0].get("text", "") if parts else ""
        
        # Return in OpenAI-compatible format
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": text
                    }
                }
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "proxy": LLM_PROXY or "none"}
