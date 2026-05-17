# server/turn_token_server.py
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
import os
import time
import hmac
import hashlib
import base64
import httpx
from pydantic import BaseModel
from typing import List

router = APIRouter()

class TurnResponse(BaseModel):
    ttl: int
    username: str
    credential: str
    urls: List[str]
    expiry: int

def _load_config():
    """Load config from env at runtime. Do NOT raise at import time."""
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    TURN_SHARED_SECRET = os.getenv("TURN_SHARED_SECRET")
    try:
        TTL = int(os.getenv("TURN_TTL", "3600"))
    except Exception:
        TTL = 3600
    TURN_URLS = os.getenv(
        "TURN_URLS",
        "turn:turn.example.com:3478?transport=udp,turn:turn.example.com:3478?transport=tcp",
    ).split(",")

    missing = [name for name, val in (
        ("SUPABASE_URL", SUPABASE_URL),
        ("SUPABASE_KEY", SUPABASE_KEY),
        ("TURN_SHARED_SECRET", TURN_SHARED_SECRET),
    ) if not val]

    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))

    return SUPABASE_URL, SUPABASE_KEY, TURN_SHARED_SECRET, TTL, [u.strip() for u in TURN_URLS if u.strip()]

async def verify_supabase_token(bearer_token: str) -> dict:
    """
    Call Supabase auth user endpoint to verify the user's access token.
    Returns parsed user JSON if valid, otherwise raises HTTPException(401).
    """
    if not bearer_token:
        raise HTTPException(status_code=401, detail="Missing Authorization token")

    SUPABASE_URL, SUPABASE_KEY, *_ = _load_config()

    url = f"{SUPABASE_URL}/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "apikey": SUPABASE_KEY,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")
    return resp.json()

@router.get("/turn-credentials", response_model=TurnResponse)
async def turn_credentials(authorization: str | None = Header(None)):
    # Validate Authorization header
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    access_token = authorization.split(" ", 1)[1].strip()

    # Verify token 
    user = await verify_supabase_token(access_token)
    user_id = user.get("id") or user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user info")

    # Load remaining config for TURN generation
    try:
        _, _, TURN_SHARED_SECRET, TTL, TURN_URLS = _load_config()
    except RuntimeError as e:
        # Config missing: return 500 so the app can still start
        raise HTTPException(status_code=500, detail=str(e))

    now = int(time.time())
    expiry = now + TTL
    username = f"{expiry}:{user_id}"

    # HMAC-SHA1 of username using shared secret, base64 encoded
    mac = hmac.new(TURN_SHARED_SECRET.encode(), username.encode(), hashlib.sha1)
    credential = base64.b64encode(mac.digest()).decode("utf-8")

    return JSONResponse({
        "ttl": TTL,
        "username": username,
        "credential": credential,
        "urls": TURN_URLS,
        "expiry": expiry,
    })

@router.get("/health")
async def health_check():
    # lightweight health endpoint
    return {"status": "ok", "component": "turn_token_server"}