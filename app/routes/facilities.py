from fastapi import APIRouter, Depends
from supabase import create_client
import os

from app.core.dependencies import get_current_user

router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@router.get("/")
async def list_facilities(user=Depends(get_current_user)):
    """Return all health facilities (name, type, district, province)."""
    result = (
        supabase.table("facilities")
        .select("id, name, type, district, province")
        .order("name")
        .execute()
    )
    return result.data or []