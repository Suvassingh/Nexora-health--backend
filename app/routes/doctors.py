from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from app.database.supabase_client import supabase
from app.core.dependencies import get_current_doctor  

router = APIRouter()


@router.get("/")
async def get_doctors(
    specialty: str = "General",
    province: str | None = None,
    district: str | None = None,
    municipality: str | None = None,
):
    # 1. First, verify we can fetch ANY doctor (no filters)
    try:
        test_query = supabase.table("doctors").select("*").limit(1).execute()
        print(f"DEBUG: Test query returned {len(test_query.data or [])} doctors")
        if test_query.data:
            print(f"DEBUG: Sample doctor: {test_query.data[0]}")
    except Exception as e:
        print(f"DEBUG: Supabase connection error: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

    # 2. Build the doctors query with filters
    query = supabase.table("doctors").select("*, healthposts!doctors_healthpost_id_fkey(province, district, municipality)").eq("is_active", True)

    if specialty:
        query = query.eq("specialty", specialty)   

    query = query.limit(30)

    doctors_result = query.execute()
    doctors = doctors_result.data or []
    print(f"DEBUG: Found {len(doctors)} doctors matching specialty '{specialty}'")

    if not doctors:
        # Fallback to ilike (case-insensitive)
        fallback_query = supabase.table("doctors").select("*").ilike("specialty", f"%{specialty}%").eq("is_active", True).limit(30)
        fallback_result = fallback_query.execute()
        doctors = fallback_result.data or []
        print(f"DEBUG: Fallback ilike returned {len(doctors)} doctors")

    if not doctors:
        print("DEBUG: No doctors found at all – check RLS or connection")
        return []

    # 3. Fetch user profiles for those doctors
    user_ids = [d["user_id"] for d in doctors if d.get("user_id")]
    profiles_by_id = {}
    if user_ids:
        profiles_result = supabase.table("user_profiles").select("*").in_("id", user_ids).execute()
        profiles = profiles_result.data or []
        profiles_by_id = {p["id"]: p for p in profiles}
        print(f"DEBUG: Found {len(profiles)} user profiles for {len(user_ids)} doctors")

    # 4. Attach profile to each doctor
    for d in doctors:
        d["user_profile"] = profiles_by_id.get(d["user_id"])

    # 5. Apply location filters
    def _loc(doctor, field):

        hp = doctor.get("healthposts") or {}  

        if hp.get(field):                     
            return hp[field]

        profile = doctor.get("user_profile") or {}

        return profile.get(field)            
    if province:
        doctors = [d for d in doctors if _loc(d, "province") == province]
    if district:
        doctors = [d for d in doctors if _loc(d, "district") == district]
    if municipality:
        doctors = [d for d in doctors if _loc(d, "municipality") == municipality]

    # 6. Format output for frontend
    for d in doctors:
        profile = d.pop("user_profile", None)
        d["user_profiles"] = [profile] if profile else None
        hp = d.get("healthposts") or {}
        d["province"]     = hp.get("province")     or (profile or {}).get("province")

    print(f"DEBUG: Final doctors count after filters: {len(doctors)}")
    return doctors


#  NEW ENDPOINTS 

@router.get("/me")
async def get_my_doctor_profile(current_doctor=Depends(get_current_doctor)):
    """
    Returns the doctor record for the currently authenticated doctor,
    including the linked user_profile (full_name, avatar_url, etc.)
    """
    doctor = current_doctor["doctor"]  
    user_id = doctor["user_id"]

    # Fetch user profile
    profile_result = supabase.table("user_profiles").select("*").eq("id", user_id).single().execute()
    profile = profile_result.data if profile_result.data else {}

    # Merge doctor + profile
    doctor["full_name"] = profile.get("full_name", "Doctor")
    doctor["avatar_url"] = profile.get("avatar_url")
    doctor["phone"] = profile.get("phone")
    doctor["province"] = profile.get("province")
    doctor["district"] = profile.get("district")
    doctor["municipality"] = profile.get("municipality")

    return doctor


@router.get("/stats")
async def get_doctor_stats(current_doctor=Depends(get_current_doctor)):
    """
    Returns aggregated statistics for the doctor.
    """
    doctor_id = current_doctor["doctor"]["id"]
    now = datetime.now(timezone.utc)

    # Today range
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # Month range
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        month_end = now.replace(year=now.year+1, month=1, day=1)
    else:
        month_end = now.replace(month=now.month+1, day=1)

    # Query today's appointments
    today_appts = supabase.table("appointments") \
        .select("status") \
        .eq("doctor_id", doctor_id) \
        .gte("scheduled_at", today_start.isoformat()) \
        .lt("scheduled_at", today_end.isoformat()) \
        .execute()

    today_list = today_appts.data or []
    print("DEBUG statuses:", [a["status"] for a in today_list])   

    today_count = len(today_list)
    pending_count = sum(1 for a in today_list if a["status"] == "pending")
    completed_count = sum(1 for a in today_list if a["status"] == "completed")

    # Query this month's appointments
    month_appts = supabase.table("appointments") \
        .select("id") \
        .eq("doctor_id", doctor_id) \
        .gte("scheduled_at", month_start.isoformat()) \
        .lt("scheduled_at", month_end.isoformat()) \
        .execute()

    total_this_month = len(month_appts.data or [])

    return {
        "today_count": today_count,
        "pending_count": pending_count,
        "completed_count": completed_count,
        "total_this_month": total_this_month,
    }