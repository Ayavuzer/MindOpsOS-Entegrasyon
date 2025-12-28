"""JWT token utilities."""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def create_access_token(
    user_id: int,
    tenant_id: int,
    email: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, str, datetime]:
    """
    Create JWT access token.
    
    Returns:
        tuple: (token, jti, expires_at)
    """
    jti = str(uuid.uuid4())
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    
    payload = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "email": email,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": jti,
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, jti, expire


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and verify JWT token.
    
    Returns:
        dict with user info or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def extract_jti(token: str) -> Optional[str]:
    """Extract JTI from token without full verification."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        return payload.get("jti")
    except JWTError:
        return None
