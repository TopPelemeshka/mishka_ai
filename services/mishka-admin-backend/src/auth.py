from datetime import datetime, timedelta
from typing import Optional
import jwt
from aiogram.utils.web_app import check_webapp_signature
from fastapi import HTTPException, status
from pydantic import BaseModel

from src.config import settings

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

class LoginRequest(BaseModel):
    initData: str
    password: str

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    
    # Ensure sub is string (JWT standard)
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
        
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def verify_telegram_auth(init_data: str) -> int:
    """
    Verifies initData string from Telegram Mini App.
    Returns user_id if valid, raises ValueError if invalid.
    """
    # DEV_MODE Bypass
    if settings.DEV_MODE and init_data == "dev":
        # Return configured superadmin ID or fallback
        return settings.SUPERADMIN_ID or 123456789

    try:
        # aiogram 3.x utility
        # check_webapp_signature(bot_token, init_data) matches the hash
        if check_webapp_signature(settings.TELEGRAM_BOT_TOKEN, init_data):
            # Parse user_id manually or use parsing lib. 
            # init_data is a query string.
            from urllib.parse import parse_qs
            import json
            
            parsed = parse_qs(init_data)
            user_json = parsed.get('user', [''])[0]
            if not user_json:
                raise ValueError("No user data in initData")
            
            # Debug
            print(f"Auth check: init_data={init_data}")
            # check_webapp_signature does the rest
            
            user_data = json.loads(user_json)
            return user_data.get('id')
        else:
            print(f"Signature mismatch. Token={settings.TELEGRAM_BOT_TOKEN[:5]}...")
            raise ValueError("Invalid signature")
    except Exception as e:
        print(f"Auth Exception: {e}")
        raise ValueError(f"Auth verification failed: {e}")

from enum import Enum

class UserRole(str, Enum):
    SUPERADMIN = "superadmin"
    VIEWER = "viewer"

def get_user_role(user_id: int) -> Optional[str]:
    if user_id == settings.SUPERADMIN_ID:
        return UserRole.SUPERADMIN
    if user_id in settings.viewer_ids_list:
        return UserRole.VIEWER
    return None
