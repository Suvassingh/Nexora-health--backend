# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_JWT_SECRET: str   # add this
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    TURN_SHARED_SECRET: str
    TURN_URLS: str
    TURN_TTL: int

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()