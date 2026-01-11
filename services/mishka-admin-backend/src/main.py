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

async def get_admin_user(current_user: Annotated[dict, Depends(get_current_user)]):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user

# --- Routes ---

@app.post("/auth/login", response_model=Token)
async def login(login_req: LoginRequest):
    # 1. Verify Telegram Signature
    try:
        user_id = verify_telegram_auth(login_req.initData)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # 2. Check Permissions (Whitelist)
    role = get_user_role(user_id)
    if not role:
        raise HTTPException(status_code=403, detail="User not allowed")

    # 3. Check Password (2FA kind of)
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

@app.get("/stats")
async def get_stats(current_user: Annotated[dict, Depends(get_current_user)]):
    return {
        "user_requesting": current_user["user_id"],
        "cpu_load": "12%", # Mock
        "memory_usage": "256MB", # Mock
        "active_chats": 42
    }
