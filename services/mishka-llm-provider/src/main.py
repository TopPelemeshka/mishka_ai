import os
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from src.config import LLM_PROXY

app = FastAPI(title="Mishka LLM Provider")

# Configure Gemini with Proxy
if LLM_PROXY:
    print(f"Using Proxy: {LLM_PROXY}")
    os.environ["HTTP_PROXY"] = LLM_PROXY
    os.environ["HTTPS_PROXY"] = LLM_PROXY

# Initialize Gemini (API Key should be passed or configured, but for now we assume it might be passed in request or environment)
# IMPORTANT: For this task I will assume user provides API Key in request or env.
# Adding a fallback check for env var.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)


class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "gemini-pro"
    messages: List[Message]
    temperature: Optional[float] = 0.7
    api_key: Optional[str] = None # Allow passing API key in request

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    try:
        # Determine API Key
        api_key = request.api_key or GOOGLE_API_KEY
        if not api_key:
            raise HTTPException(status_code=401, detail="API Key not provided (in request or env)")
        
        # Re-configure if specific key provided
        genai.configure(api_key=api_key)
        
        # Prepare messages for Gemini
        # Gemini expects history in specific format or prompt.
        # Simple conversion for text-only model
        model = genai.GenerativeModel(request.model)
        
        chat = model.start_chat(history=[])
        
        # Convert messages to Gemini format. 
        # Note: simplistic implementation. 'system' role might need special handling.
        # For now, just taking the last user message to simpler send_message.
        # A full chat history reconstruction would be:
        # history = []
        # for msg in request.messages[:-1]: ...
        
        last_message = request.messages[-1]
        if last_message.role != "user":
             raise HTTPException(status_code=400, detail="Last message must be from user")

        response = chat.send_message(last_message.content)
        
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": response.text
                    }
                }
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok"}
