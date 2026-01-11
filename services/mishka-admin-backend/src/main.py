from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from typing import Annotated, Optional
from pydantic import BaseModel

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

@app.on_event("startup")
async def startup():
    from src.database import init_db
    from src.events import producer
    await init_db()
    await producer.connect()

@app.on_event("shutdown")
async def shutdown():
    from src.events import producer
    await producer.close()

# --- Configuration Routes ---
from src.database import get_db
from src.models import DynamicConfig
from src.events import producer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

class ConfigUpdate(BaseModel):
    service: str
    key: str
    value: str
    description: Optional[str] = None
    type: str = "string"

@app.get("/admin/configs")
async def get_all_configs(current_user: Annotated[dict, Depends(get_current_user)], db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DynamicConfig))
    configs = result.scalars().all()
    
    # Group by service
    grouped = {}
    for c in configs:
        if c.service not in grouped:
            grouped[c.service] = []
        grouped[c.service].append({
            "key": c.key,
            "value": c.value, 
            "description": c.description,
            "type": c.type
        })
        
    if current_user["role"] == "viewer":
        # Sanitize values if needed? Assume viewers can see configs for now, unless sensitive.
        pass
        
    return grouped

@app.post("/admin/configs")
async def update_config(
    idx: ConfigUpdate, 
    admin: Annotated[dict, Depends(require_superadmin)], 
    db: AsyncSession = Depends(get_db)
):
    # Check if exists
    result = await db.execute(
        select(DynamicConfig).where(
            DynamicConfig.service == idx.service, 
            DynamicConfig.key == idx.key
        )
    )
    existing = result.scalars().first()
    
    if existing:
        existing.value = idx.value
        if idx.description: existing.description = idx.description
        if idx.type: existing.type = idx.type
    else:
        new_config = DynamicConfig(
            service=idx.service, 
            key=idx.key, 
            value=idx.value,
            description=idx.description,
            type=idx.type
        )
        db.add(new_config)
        
    await db.commit()
    
    # Publish Event
    await producer.publish_update(idx.service, idx.key, idx.value)
    
    return {"status": "updated", "key": f"{idx.service}.{idx.key}"}

@app.get("/internal/configs/{service_name}")
async def get_service_config(service_name: str, db: AsyncSession = Depends(get_db)):
    """Internal endpoint for services to fetch their config on startup"""
    # No auth for internal network (or use shared secret if paranoid, generally internal network is trusted in Docker Compose)
    result = await db.execute(select(DynamicConfig).where(DynamicConfig.service == service_name))
    configs = result.scalars().all()
    
    return {c.key: c.value for c in configs}

