
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.database.supabase_client import supabase

router = APIRouter()

class UserRegister(BaseModel):
    email:        EmailStr
    password:     str
    full_name:    str
    phone:        str
    role:         str            
    healthpost_id: Optional[str] = None  

class UserLogin(BaseModel):
    email:    EmailStr
    password: str

class HealthpostCreate(BaseModel):
    name:         str
    hp_code:      Optional[str] = None   
    province:     Optional[str] = None
    district:     Optional[str] = None
    municipality: Optional[str] = None
    ward:         Optional[str] = None
    address:      Optional[str] = None
    phone:        Optional[str] = None



# HEALTHPOST ENDPOINTS

@router.get("/healthposts")
async def list_healthposts(
    district:     Optional[str] = None,
    municipality: Optional[str] = None,
):
    """
    Public endpoint — used on registration/booking screens so
    patients and doctors can pick their healthpost.
    """
    query = supabase.table("healthposts").select("id, name, hp_code, district, municipality, ward, address, phone").eq("is_active", True)

    if district:
        query = query.eq("district", district)
    if municipality:
        query = query.eq("municipality", municipality)

    result = query.order("name").execute()
    return result.data or []


@router.post("/healthposts")
async def create_healthpost(data: HealthpostCreate):
    """
    Admin / OIC creates a healthpost record.
    In production, guard this with an admin token check.
    For now, the Supabase dashboard / seed script can create these.
    """
    payload = {
        "name":         data.name,
        "hp_code":      data.hp_code,
        "province":     data.province,
        "district":     data.district,
        "municipality": data.municipality,
        "ward":         data.ward,
        "address":      data.address,
        "phone":        data.phone,
        "is_active":    True,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    result = supabase.table("healthposts").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create healthpost")
    return result.data[0]



# REGISTER

@router.post("/register")
async def register(user: UserRegister):
    # Validate role
    if user.role not in ("patient", "doctor"):
        raise HTTPException(status_code=400, detail="role must be 'patient' or 'doctor'")

    # Doctors must supply a healthpost
    if user.role == "doctor":
        if not user.healthpost_id:
            raise HTTPException(
                status_code=400,
                detail="healthpost_id is required when registering as a doctor",
            )
        # Verify the healthpost exists and is active
        hp = (
            supabase.table("healthposts")
            .select("id, name")
            .eq("id", user.healthpost_id)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        if not hp or not hp.data:
            raise HTTPException(status_code=404, detail="Healthpost not found or inactive")

    try:
        # 1. Supabase Auth sign-up
        auth_response = supabase.auth.sign_up({
            "email":    user.email,
            "password": user.password,
        })
        user_id = auth_response.user.id

        # 2. user_profiles row
        supabase.table("user_profiles").insert({
            "id":        user_id,
            "email":     user.email,
            "full_name": user.full_name,
            "phone":     user.phone,
            "role":      user.role,
        }).execute()

        # 3a. Doctor record — include healthpost_id
        if user.role == "doctor":
            supabase.table("doctors").insert({
                "user_id":        user_id,
                "healthpost_id":  user.healthpost_id,
                "license_number": "PENDING",
                "specialty":      "General",
                "healthpost_name": hp.data["name"],   
                "is_active":      True,
            }).execute()

        # 3b. Patient record
        if user.role == "patient":
            supabase.table("patients").insert({
                "user_id":     user_id,
                "age":         None,
                "gender":      None,
                "blood_group": None,
                "conditions":  None,
            }).execute()

        return {"message": "User created successfully", "user_id": user_id}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# LOGIN

@router.post("/login")
async def login(user: UserLogin):
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email":    user.email,
            "password": user.password,
        })
        return {
            "access_token": auth_response.session.access_token,
            "token_type":   "bearer",
            "user":         auth_response.user,
        }
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid credentials")