
# app/core/security.py
from jose import jwt
from jose.exceptions import JWTError
from app.core.config import settings

# Supabase JWT settings
SUPABASE_JWT_SECRET = settings.SUPABASE_JWT_SECRET  
SUPABASE_JWT_ALGORITHM = "HS256"  

def decode_token(token: str):
    """
    Decode a Supabase JWT token and return the payload.
    Returns None if token is invalid.
    """
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=[SUPABASE_JWT_ALGORITHM],
            options={"verify_aud": False}  
        )
        return payload
    except JWTError:
        return None