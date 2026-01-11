"""
Mishka LLM Provider - использует прямые REST вызовы к Gemini API с явной настройкой прокси.
"""
import os
import httpx
import google.generativeai as genai
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
    # Configure genai to use proxy implicitly via env vars (it respects them)
    os.environ["HTTP_PROXY"] = LLM_PROXY
    os.environ["HTTPS_PROXY"] = LLM_PROXY
else:
    print("WARNING: No proxy configured!")


class Message(BaseModel):
    role: str
    content: str
    files: Optional[List[str]] = None # Local paths to files

class ChatCompletionRequest(BaseModel):
    model: str = "gemini-2.0-flash"
    messages: List[Message]
    temperature: Optional[float] = 0.7
    api_key: Optional[str] = None


def upload_file_to_gemini(file_path: str, api_key: str):
    """
    Uploads a file to Gemini using the SDK.
    Returns the file URI and mime_type.
    """
    try:
        genai.configure(api_key=api_key)
        
        # Check if file exists
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return None

        # Determine mime type (basic)
        mime_type = "application/octet-stream"
        ext = file_path.split('.')[-1].lower()
        if ext in ['jpg', 'jpeg']: mime_type = "image/jpeg"
        elif ext == 'png': mime_type = "image/png"
        elif ext in ['ogg', 'oga']: mime_type = "audio/ogg"
        elif ext == 'mp3': mime_type = "audio/mp3"
        elif ext == 'wav': mime_type = "audio/wav"

        print(f"Uploading file: {file_path} ({mime_type})")
        
        # Upload
        # Note: genai.upload_file handles large files automatically
        myfile = genai.upload_file(file_path, mime_type=mime_type)
        
        print(f"Uploaded: {myfile.name} -> {myfile.uri}")
        return {"file_uri": myfile.uri, "mime_type": myfile.mime_type}

    except Exception as e:
        print(f"Upload failed: {e}")
        return None


def convert_messages_to_gemini_format(messages: List[Message], api_key: str) -> dict:
    """
    Конвертирует сообщения в формат Gemini API, загружая файлы.
    """
    contents = []
    system_instruction = None
    
    for msg in messages:
        if msg.role == "system":
            system_instruction = msg.content
            
        elif msg.role == "user":
            parts = []
            
            # 1. Add Text
            if msg.content:
                parts.append({"text": msg.content})
            
            # 2. Upload and Add Files
            if msg.files:
                for file_path in msg.files:
                    file_data = upload_file_to_gemini(file_path, api_key)
                    if file_data:
                        parts.append({
                            "file_data": {
                                "file_uri": file_data["file_uri"],
                                "mime_type": file_data["mime_type"]
                            }
                        })
            
            contents.append({
                "role": "user",
                "parts": parts
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
        
        # Convert messages (Sync upload for now to keep logic simple)
        # In production this should be async, but SDK is sync.
        payload = convert_messages_to_gemini_format(request_body.messages, api_key)
        
        payload["generationConfig"] = {
            "temperature": request_body.temperature
        }
        
        print(f"Calling Gemini API: model={model_name}")
        
        # Make request with explicit proxy
        async with httpx.AsyncClient(proxy=LLM_PROXY, timeout=120.0) as client:
            response = await client.post(url, json=payload)
            
            if response.status_code != 200:
                error_detail = response.text
                print(f"Gemini API Error: {response.status_code} - {error_detail}")
                raise HTTPException(status_code=response.status_code, detail=error_detail)
            
            data = response.json()
        
        # Extract response text
        candidates = data.get("candidates", [])
        if not candidates:
            # Handle empty response (e.g., blocked content)
            print(f"Empty candidates: {data}")
            raise HTTPException(status_code=500, detail="No response from Gemini (Safety?)")
        
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "proxy": LLM_PROXY or "none"}
