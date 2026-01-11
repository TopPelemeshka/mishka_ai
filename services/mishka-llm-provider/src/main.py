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
from src.key_manager import key_manager

app = FastAPI(title="Mishka LLM Provider")

from src.config_manager import config_manager

@app.on_event("startup")
async def startup_event():
    await config_manager.initialize()

# Gemini API Configuration
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

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
    model: str = "gemini-2.0-flash" # Default value for Pydantic (static)
    # We will override this in the handler if not provided or if we want to enforce dynamic default?
    # Pydantic defaults are set at import time. We can't easily make them dynamic.
    # But we can check in the handler: if request.model == "gemini-2.0-flash" (default), check if dynamic config is different?
    # Or better: let Pydantic be 'gemini-2.0-flash' and in handler logic:
    # model_name = request_body.model
    # if model_name == "gemini-2.0-flash": # If user didn't change it... (weak heuristic)
    # Better approach: Default to None or Optional, and if None, use config.
    messages: List[Message]
    temperature: Optional[float] = 0.7
    api_key: Optional[str] = None

class EmbeddingRequest(BaseModel):
    content: str
    task_type: str = "retrieval_document" # retrieval_query, retrieval_document, semantic_similarity, classification, clustering
    model: str = "models/text-embedding-004"
    output_dimensionality: Optional[int] = 768
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
    # Determine API Key (Header > Body > Env)
    user_provided_key = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        user_provided_key = auth_header.split(" ")[1]
    if not user_provided_key:
        user_provided_key = request_body.api_key

    # If user provided key, use it (single attempt)
    keys_to_try = [user_provided_key] if user_provided_key else None

    # If no user key, get all system keys for rotation
    # We don't just get all keys locally, we want to try them in order starting from 'next'.
    # But simple approach: Loop up to N times, getting 'next' key each time.
    max_retries = 1
    if not user_provided_key:
        # Try at least as many times as we have keys, or a fixed limit (e.g. 5)
        # To avoid infinite loops if all fail.
        total_keys = len(key_manager.get_all_keys())
        max_retries = total_keys if total_keys > 0 else 1

    last_error = None

    for attempt in range(max_retries):
        try:
            # Get Key
            if user_provided_key:
                api_key = user_provided_key
            else:
                api_key = key_manager.get_next_key()
            
            if not api_key:
                raise HTTPException(status_code=401, detail="No API Keys available in configuration")

            # Build Gemini API URL
            model_name = request_body.model
            # DYNAMIC: Check if we should use dynamic default
            # If the user passed the HARDCODED default from Pydantic, we might want to swap it?
            # Or just rely on the fact that if this variable is used, we use it.
            # Let's assume if the user explicitly sends a model, we respect it.
            # But if we want to change the SYSTEM default, we should probably change the Pydantic default? No, can't.
            # Let's just use the timeout for now as it's cleaner.
            
            # Dynamic Timeout
            timeout_val = float(config_manager.get("request_timeout", 120.0))
            
            url = f"{GEMINI_API_URL}/{model_name}:generateContent?key={api_key}"
            
            # Convert messages (Uploads files using CURRENT key)
            # This ensures file permissions match the generation request key
            payload = convert_messages_to_gemini_format(request_body.messages, api_key)
            
            payload["generationConfig"] = {
                "temperature": request_body.temperature
            }
            
            print(f"Calling Gemini API: model={model_name} (Attempt {attempt+1}/{max_retries})")
            
            # Make request with explicit proxy
            async with httpx.AsyncClient(proxy=LLM_PROXY, timeout=timeout_val) as client:
                response = await client.post(url, json=payload)
                
                if response.status_code != 200:
                    error_detail = response.text
                    print(f"Gemini API Error: {response.status_code} - {error_detail}")
                    
                    # If 429 Resource Exhausted, try next key
                    if response.status_code == 429:
                        last_error = f"429: {error_detail}"
                        if user_provided_key: # Cannot rotate user provided key
                            break 
                        print("Rate limit hit, rotating key...")
                        continue # Try next key
                        
                    raise HTTPException(status_code=response.status_code, detail=error_detail)
                
                data = response.json()
            
            # Extract response text
            candidates = data.get("candidates", [])
            if not candidates:
                # Handle empty response
                print(f"Empty candidates: {data}")
                raise HTTPException(status_code=500, detail="No response from Gemini (Safety?)")
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            text = parts[0].get("text", "") if parts else ""
            
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
            if attempt == max_retries - 1:
                raise
        except Exception as e:
            print(f"Error attempt {attempt}: {e}")
            last_error = str(e)
            if attempt == max_retries - 1:
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"All retries failed. Last error: {last_error}")

    # If we fell out of loop
    raise HTTPException(status_code=429, detail=f"Rate limit exceeded on all keys. Last error: {last_error}")


@app.get("/health")
async def health():
    return {"status": "ok", "proxy": LLM_PROXY or "none"}


@app.post("/v1/embeddings")
async def create_embedding(request_body: EmbeddingRequest, request: Request):
    # Auth (Reuse logic mostly)
    user_provided_key = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        user_provided_key = auth_header.split(" ")[1]
    if not user_provided_key:
        user_provided_key = request_body.api_key

    max_retries = 1
    if not user_provided_key:
        total_keys = len(key_manager.get_all_keys())
        max_retries = total_keys if total_keys > 0 else 1

    last_error = None

    for attempt in range(max_retries):
        try:
            if user_provided_key:
                api_key = user_provided_key
            else:
                api_key = key_manager.get_next_key()
            
            if not api_key:
                raise HTTPException(status_code=401, detail="API Key not provided")

            genai.configure(api_key=api_key)
            
            # Call Gemini Embedding API
            print(f"Generating embedding for task={request_body.task_type} (Attempt {attempt+1}/{max_retries})")
            
            result = genai.embed_content(
                model=request_body.model,
                content=request_body.content,
                task_type=request_body.task_type,
                output_dimensionality=request_body.output_dimensionality
            )
            
            return {
                "embedding": result['embedding'],
                "model": request_body.model
            }

        except Exception as e:
            print(f"Embedding Error attempt {attempt}: {e}")
            last_error = str(e)
            
            # Check for Rate Limit in exception message
            if "429" in str(e) or "ResourceExhausted" in str(e) or "quota" in str(e).lower():
                if user_provided_key:
                    break
                print("Rate limit hit (embedding), rotating key...")
                continue
            
            # If other error, maybe break or continue?
            # Safe to retry for 503s etc, but SDK might hide status codes.
            # We continue if multiple keys available.
            
            if attempt == max_retries - 1:
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(status_code=429, detail=f"Rate limit exceeded (embeddings). Last error: {last_error}")

