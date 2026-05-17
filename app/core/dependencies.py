from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database.supabase_client import supabase

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    token = credentials.credentials

    try:
        # Verify token with Supabase directly
        user_response = supabase.auth.get_user(token)

        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )

        user_id = user_response.user.id

        # Fetch user profile
        profile = (
            supabase.table("user_profiles")
            .select("*")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )

        if not profile.data:
            raise HTTPException(
                status_code=404,
                detail="User profile not found",
            )

        return profile.data

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )


async def get_current_patient(current_user=Depends(get_current_user)):
    if current_user.get("role") != "patient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients can perform this action",
        )
    return current_user


async def get_current_doctor(current_user=Depends(get_current_user)):
    if current_user.get("role") != "doctor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can perform this action",
        )

    doctor = (
        supabase.table("doctors")
        .select("*")
        .eq("user_id", current_user["id"])
        .maybe_single()
        .execute()
    )

    if not doctor.data:
        raise HTTPException(
            status_code=404,
            detail="Doctor profile not found",
        )

    return {"user": current_user, "doctor": doctor.data}