from fastapi import APIRouter, Depends, HTTPException
from app.core.dependencies import get_current_user, get_current_doctor
from app.database.supabase_client import supabase
from datetime import datetime, timezone
import uuid

router = APIRouter()

# Start consultation (doctor starts it)
@router.post("/start/{appointment_id}")
async def start_consultation(appointment_id: str, current=Depends(get_current_doctor)):
    # verify appointment
    appt = supabase.table("appointments").select("*").eq("id", appointment_id).single().execute()
    if not appt.data:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.data["status"] != "confirmed":
        raise HTTPException(status_code=400, detail="Appointment must be confirmed first")

    # check if consultation already exists
    existing = supabase.table("consultations").select("*").eq("appointment_id", appointment_id).execute()
    if existing.data:
        return existing.data[0]

    room_id = f"room_{uuid.uuid4().hex[:12]}"
    consultation = {
        "appointment_id": appointment_id,
        "room_id": room_id,
        "status": "waiting",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    result = supabase.table("consultations").insert(consultation).execute()

    # update appointment status to ongoing
    supabase.table("appointments").update({
        "status": "ongoing",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", appointment_id).execute()

    return result.data[0]


# Get consultation by appointment_id
@router.get("/by-appointment/{appointment_id}")
async def get_consultation_by_appointment(appointment_id: str, current_user=Depends(get_current_user)):
    result = supabase.table("consultations").select("*").eq("appointment_id", appointment_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return result.data


# Get consultation by id
@router.get("/{consultation_id}")
async def get_consultation(consultation_id: str, current_user=Depends(get_current_user)):
    result = supabase.table("consultations").select("*").eq("id", consultation_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Not found")
    return result.data


# End consultation
@router.patch("/{consultation_id}/end")
async def end_consultation(consultation_id: str, current=Depends(get_current_doctor)):
    result = supabase.table("consultations").update({
        "status": "ended",
        "ended_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", consultation_id).execute()

    if result.data:
        # update appointment to completed
        appt_id = result.data[0]["appointment_id"]
        supabase.table("appointments").update({
            "status": "completed",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", appt_id).execute()

    return result.data[0]