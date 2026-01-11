from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from typing import Annotated

from src.config import settings
from src.auth import (
    LoginRequest, Token, 
    verify_telegram_auth, get_user_role, create_access_token
)

app = FastAPI(title="Mishka Admin Backend")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# --- Dependencies ---
# --- Dependencies ---
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id_str = payload.get("sub")
        role: str = payload.get("role")
        
        if user_id_str is None or role is None:
            raise credentials_exception
            
        user_id = int(user_id_str)
        return {"user_id": user_id, "role": role}
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

async def require_superadmin(current_user: Annotated[dict, Depends(get_current_user)]):
    if current_user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return current_user

# --- Routes ---

@app.post("/auth/login", response_model=Token)
async def login(login_req: LoginRequest):
    # 1. Verify Telegram Signature
    try:
        user_id = verify_telegram_auth(login_req.initData)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # 2. Check Permissions (RBAC)
    role = get_user_role(user_id)
    if not role:
        raise HTTPException(status_code=403, detail="User not allowed")

    # 3. Check Password
    if login_req.password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")

    # 4. Generate Token
    access_token = create_access_token(
        data={"sub": user_id, "role": role}
    )
    return Token(access_token=access_token, token_type="bearer", role=role)

@app.get("/status")
async def get_status():
    return {"status": "ok", "service": "mishka-admin-backend"}

@app.get("/dashboard/stats")
async def get_stats(current_user: Annotated[dict, Depends(get_current_user)]):
    # Retrieve real stats (Mocking for now as per instructions)
    # In real world: query storage/memory service
    return {
        "user_requesting": current_user["user_id"],
        "role": current_user["role"],
        "cpu_usage": "15%",
        "ram_usage": "320MB",
        "total_users": 1337,
        "facts_in_memory": 42
    }

def sanitize_config(config: dict) -> dict:
    """Mask sensitive fields recursively."""
    sensitive_keys = ["key", "token", "secret", "pass", "password"]
    sanitized = config.copy()
    for k, v in sanitized.items():
        if isinstance(v, dict):
            sanitized[k] = sanitize_config(v)
        elif isinstance(k, str) and any(s in k.lower() for s in sensitive_keys):
            sanitized[k] = "********"
    return sanitized

@app.get("/tools")
async def get_tools(current_user: Annotated[dict, Depends(get_current_user)]):
    import httpx
    # Fetch tools from Memory Service
    MEMORY_URL = "http://mishka-memory:8000/tools/config"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(MEMORY_URL, timeout=5.0)
            if resp.status_code == 200:
                tools = resp.json()
                # Sanitize if viewer
                if current_user["role"] == "viewer":
                    return [sanitize_config(t) for t in tools]
                return tools
            else:
                return []
    except Exception:
        return []

@app.post("/tools/{name}")
async def update_tool_config(name: str, config: dict, admin: Annotated[dict, Depends(require_superadmin)]):
    # Mock update
    return {"status": "updated", "tool": name}

@app.get("/logs")
async def get_logs(admin: Annotated[dict, Depends(require_superadmin)]):
    from fastapi.responses import StreamingResponse
    LOG_FILE = "/app/logs/interactions.log"
    
    def log_generator():
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                # Basic tail implementation
                # f.seek(0, 2) # Start from end? No, maybe full logs for now. 
                # Prompts implies just "Stream logs"
                for line in f:
                    yield line
        except FileNotFoundError:
            yield "Log file not found."

    return StreamingResponse(log_generator(), media_type="text/plain")
