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
            
            user_data = json.loads(user_json)
            return user_data.get('id')
        else:
            raise ValueError("Invalid signature")
    except Exception as e:
        raise ValueError(f"Auth verification failed: {e}")

def get_user_role(user_id: int) -> str:
    if user_id in settings.superadmin_ids_list:
        return "admin"
    if user_id in settings.viewer_ids_list:
        return "viewer"
    return None
