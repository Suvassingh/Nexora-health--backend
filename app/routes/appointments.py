
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatusUpdate,
    SlotCheckRequest,
)
from app.core.dependencies import (
    get_current_user,
    get_current_patient,
    get_current_doctor,
)
from app.database.supabase_client import supabase

router = APIRouter()


#  HELPERS 

def _apply_hp_filter(query, hp_id):
    """Add .eq('healthpost_id', hp_id) only when hp_id is non-null.
    Avoids PostgREST generating 'healthpost_id=eq.null' which matches
    NULL rows instead of acting as a no-op."""
    if hp_id:
        query = query.eq("healthpost_id", hp_id)
    return query


#  1. EXACT STATIC ROUTES 

@router.post("/", response_model=dict)
async def book_appointment(
    data: AppointmentCreate,
    current_user=Depends(get_current_patient),
):
    doctor = (
        supabase.table("doctors")
        .select("id, is_active, is_verified, healthpost_id")
        .eq("id", data.doctor_id)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if not doctor or not doctor.data:
        raise HTTPException(status_code=404, detail="Doctor not found or inactive")

    conflict = (
        supabase.table("appointments")
        .select("id")
        .eq("doctor_id", data.doctor_id)
        .eq("scheduled_at", data.scheduled_at.isoformat())
        .not_.in_("status", ["cancelled", "no_show"])
        .execute()
    )
    if conflict.data:
        raise HTTPException(
            status_code=409,
            detail="This time slot is already booked. Please choose another.",
        )

    appointment = {
        "patient_id":        current_user["id"],
        "doctor_id":         data.doctor_id,
        "healthpost_id":     doctor.data["healthpost_id"],
        "consultation_type": data.consultation_type,
        "scheduled_at":      data.scheduled_at.isoformat(),
        "duration_minutes":  data.duration_minutes,
        "patient_notes":     data.patient_notes,
        "status":            "pending",
    }
    result = supabase.table("appointments").insert(appointment).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create appointment")
    return result.data[0]


@router.post("/check-slots")
async def check_slots(
    data: SlotCheckRequest,
    current_user=Depends(get_current_user),
):
    try:
        date = datetime.strptime(data.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    start = date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    result = (
        supabase.table("appointments")
        .select("scheduled_at")
        .eq("doctor_id", data.doctor_id)
        .gte("scheduled_at", start.isoformat())
        .lt("scheduled_at", end.isoformat())
        .not_.in_("status", ["cancelled", "no_show"])
        .execute()
    )

    booked_slots = []
    for row in result.data:
        dt = datetime.fromisoformat(row["scheduled_at"]).astimezone(timezone.utc)
        h12 = dt.hour % 12 or 12
        mm = str(dt.minute).zfill(2)
        ap = "AM" if dt.hour < 12 else "PM"
        booked_slots.append(f"{h12}:{mm} {ap}")

    return {"doctor_id": data.doctor_id, "date": data.date, "booked_slots": booked_slots}


@router.get("/")
async def get_my_appointments(current_user=Depends(get_current_user)):
    if current_user["role"] == "patient":
        result = (
            supabase.table("appointments")
            .select(
                "*,"
                "doctors!appointments_doctor_id_fkey("
                "  id, specialty, healthpost_name, rating,"
                "  user_profiles!doctors_user_id_fkey(full_name, avatar_url, phone)"
                ")"
            )
            .eq("patient_id", current_user["id"])
            .order("scheduled_at", desc=True)
            .execute()
        )
    else:
        doctor = (
            supabase.table("doctors")
            .select("id, healthpost_id")
            .eq("user_id", current_user["id"])
            .maybe_single()
            .execute()
        )
        if not doctor or not doctor.data:
            raise HTTPException(status_code=404, detail="Doctor record not found")

        hp_id = doctor.data.get("healthpost_id")  
        query = (
            supabase.table("appointments")
            .select(
                "*,"
                "user_profiles!appointments_patient_id_fkey("
                "  full_name, avatar_url, phone, gender"
                ")"
            )
            .eq("doctor_id", doctor.data["id"])
        )
        query = _apply_hp_filter(query, hp_id)
        result = query.order("scheduled_at", desc=True).execute()

    return result.data


#  2. STATIC-PREFIX ROUTES (must stay before /{appointment_id}) 

@router.get("/upcoming/list")
async def get_upcoming_appointments(current_user=Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    week_later = now + timedelta(days=7)

    if current_user["role"] == "patient":
        result = (
            supabase.table("appointments")
            .select("*, doctors!appointments_doctor_id_fkey(specialty, user_profiles!doctors_user_id_fkey(full_name, avatar_url))")
            .eq("patient_id", current_user["id"])
            .in_("status", ["pending", "confirmed"])
            .gte("scheduled_at", now.isoformat())
            .lte("scheduled_at", week_later.isoformat())
            .order("scheduled_at")
            .execute()
        )
    else:
        doctor = (
            supabase.table("doctors")
            .select("id, healthpost_id")
            .eq("user_id", current_user["id"])
            .maybe_single()
            .execute()
        )
        if not doctor or not doctor.data:
            raise HTTPException(status_code=404, detail="Doctor record not found")

        hp_id = doctor.data.get("healthpost_id")  
        query = (
            supabase.table("appointments")
            .select("*, user_profiles!appointments_patient_id_fkey(full_name, phone)")
            .eq("doctor_id", doctor.data["id"])
        )
        query = _apply_hp_filter(query, hp_id)
        result = (
            query
            .in_("status", ["pending", "confirmed"])
            .gte("scheduled_at", now.isoformat())
            .lte("scheduled_at", week_later.isoformat())
            .order("scheduled_at")
            .execute()
        )

    return result.data


@router.get("/filter/{status}")
async def get_appointments_by_status(
    status: str,
    current_user=Depends(get_current_user),
):
    valid = ["pending", "confirmed", "ongoing", "completed", "cancelled"]
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid}")

    if current_user["role"] == "patient":
        result = (
            supabase.table("appointments")
            .select("*, doctors!appointments_doctor_id_fkey(specialty, healthpost_name, user_profiles!doctors_user_id_fkey(full_name))")
            .eq("patient_id", current_user["id"])
            .eq("status", status)
            .order("scheduled_at", desc=True)
            .execute()
        )
    else:
        doctor = (
            supabase.table("doctors")
            .select("id, healthpost_id")
            .eq("user_id", current_user["id"])
            .maybe_single()
            .execute()
        )
        if not doctor or not doctor.data:
            raise HTTPException(status_code=404, detail="Doctor record not found")

        hp_id = doctor.data.get("healthpost_id")  
        query = (
            supabase.table("appointments")
            .select("*, user_profiles!appointments_patient_id_fkey(full_name, phone)")
            .eq("doctor_id", doctor.data["id"])
        )
        query = _apply_hp_filter(query, hp_id)
        result = query.eq("status", status).order("scheduled_at", desc=True).execute()

    return result.data


#  3. DOCTOR-SPECIFIC (all /doctor/* must come before /{appointment_id}) 

@router.get("/doctor/today")
async def get_doctor_today_appointments(current_doctor=Depends(get_current_doctor)):
    doctor = current_doctor["doctor"]
    doctor_id = doctor["id"]
    hp_id = doctor.get("healthpost_id")  
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    query = (
        supabase.table("appointments")
        .select(
            "id, patient_notes, status, scheduled_at, duration_minutes, "
            "user_profiles!appointments_patient_id_fkey(full_name, avatar_url, phone)"
        )
        .eq("doctor_id", doctor_id)
    )
    query = _apply_hp_filter(query, hp_id)
    result = (
        query
        .gte("scheduled_at", start.isoformat())
        .lt("scheduled_at", end.isoformat())
        .order("scheduled_at")
        .execute()
    )

    appointments = []
    for appt in result.data or []:
        profile = appt.get("user_profiles", {}) or {}
        appointments.append({
            "id":                appt["id"],
            "patient_notes":     appt.get("patient_notes", ""),
            "status":            appt["status"],
            "scheduled_at":      appt["scheduled_at"],
            "duration_minutes":  appt.get("duration_minutes"),
            "patient_full_name": profile.get("full_name", "Unknown"),
            "patient_avatar":    profile.get("avatar_url"),
            "patient_phone":     profile.get("phone"),
        })
    return appointments


@router.get("/doctor/monthly")
async def get_doctor_monthly_appointments(
    year: int,
    month: int,
    current_doctor=Depends(get_current_doctor),
):
    doctor = current_doctor["doctor"]
    doctor_id = doctor["id"]
    hp_id = doctor.get("healthpost_id")  

    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12 \
        else datetime(year, month + 1, 1, tzinfo=timezone.utc)

    query = (
        supabase.table("appointments")
        .select(
            "id, patient_notes, status, scheduled_at, duration_minutes, "
            "user_profiles!appointments_patient_id_fkey(full_name, avatar_url)"
        )
        .eq("doctor_id", doctor_id)
    )
    query = _apply_hp_filter(query, hp_id)
    result = (
        query
        .gte("scheduled_at", start.isoformat())
        .lt("scheduled_at", end.isoformat())
        .order("scheduled_at")
        .execute()
    )

    appointments = []
    for appt in result.data or []:
        profile = appt.get("user_profiles", {}) or {}
        appointments.append({
            "id":                appt["id"],
            "patient_notes":     appt.get("patient_notes", ""),
            "status":            appt["status"],
            "scheduled_at":      appt["scheduled_at"],
            "duration_minutes":  appt.get("duration_minutes"),
            "patient_full_name": profile.get("full_name", "Unknown"),
            "patient_avatar":    profile.get("avatar_url"),
        })
    return appointments


@router.get("/doctor/patients")
async def get_doctor_patients(
    current_doctor=Depends(get_current_doctor),
):
    """Returns distinct patients who have a non-cancelled appointment
    with the logged-in doctor at their healthpost."""
    doctor = current_doctor["doctor"]
    doctor_id = doctor["id"]
    hp_id = doctor.get("healthpost_id")  

    query = (
        supabase.table("appointments")
        .select(
            "patient_id, "
            "user_profiles!appointments_patient_id_fkey("
            "  id, full_name, avatar_url, phone, gender"
            ")"
        )
        .eq("doctor_id", doctor_id)
    )
    query = _apply_hp_filter(query, hp_id)
    result = query.not_.in_("status", ["cancelled", "no_show"]).execute()

    seen = set()
    patients = []
    for row in result.data or []:
        pid = row["patient_id"]
        profile = row.get("user_profiles") or {}
        if pid not in seen:
            seen.add(pid)
            patients.append({
                "patient_id": pid,
                "full_name":  profile.get("full_name", "Unknown"),
                "avatar_url": profile.get("avatar_url"),
                "phone":      profile.get("phone"),
                "gender":     profile.get("gender"),
            })
    return patients


#  4. PARAMETERIZED ROUTES LAST 

@router.get("/{appointment_id}")
async def get_appointment(
    appointment_id: str,
    current_user=Depends(get_current_user),
):
    result = (
        supabase.table("appointments")
        .select(
            "*, "
            "doctors!appointments_doctor_id_fkey("
            "  id, specialty, healthpost_name, qualification, experience_years, rating,"
            "  user_profiles!doctors_user_id_fkey(full_name, avatar_url, phone)"
            "), "
            "user_profiles!appointments_patient_id_fkey("
            "  full_name, avatar_url, phone, gender"
            ")"
        )
        .eq("id", appointment_id)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appt = result.data

    if current_user["role"] == "patient":
        if appt["patient_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        doctor = (
            supabase.table("doctors")
            .select("healthpost_id")
            .eq("user_id", current_user["id"])
            .maybe_single()
            .execute()
        )
        if not doctor or not doctor.data:
            raise HTTPException(status_code=403, detail="Doctor record not found")
        hp_id = doctor.data.get("healthpost_id")
        if hp_id and appt.get("healthpost_id") != hp_id:
            raise HTTPException(status_code=403, detail="This appointment is at a different healthpost")

    return appt


@router.patch("/{appointment_id}/confirm")
async def confirm_appointment(
    appointment_id: str,
    current=Depends(get_current_doctor),
):
    doctor = current["doctor"]
    hp_id = doctor.get("healthpost_id")  

    query = (
        supabase.table("appointments")
        .select("*")
        .eq("id", appointment_id)
        .eq("doctor_id", doctor["id"])
    )
    query = _apply_hp_filter(query, hp_id)
    appt = query.maybe_single().execute()

    if not appt or not appt.data:
        raise HTTPException(status_code=404, detail="Appointment not found or not yours")
    if appt.data["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot confirm. Status is '{appt.data['status']}'")

    result = (
        supabase.table("appointments")
        .update({"status": "confirmed", "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", appointment_id)
        .execute()
    )
    return result.data[0]


@router.patch("/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: str,
    current_user=Depends(get_current_user),
):
    appt = (
        supabase.table("appointments")
        .select("*")
        .eq("id", appointment_id)
        .maybe_single()
        .execute()
    )
    if not appt or not appt.data:
        raise HTTPException(status_code=404, detail="Appointment not found")

    
    if current_user["role"] == "patient":
        if appt.data["patient_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        doctor = (
            supabase.table("doctors")
            .select("id, healthpost_id")
            .eq("user_id", current_user["id"])
            .maybe_single()
            .execute()
        )
        if not doctor or not doctor.data:
            raise HTTPException(status_code=403, detail="Doctor record not found")
        if appt.data["doctor_id"] != doctor.data["id"]:
            raise HTTPException(status_code=403, detail="Not your appointment")

    if appt.data["status"] in ["completed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel a {appt.data['status']} appointment")

    result = (
        supabase.table("appointments")
        .update({"status": "cancelled", "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", appointment_id)
        .execute()
    )
    return result.data[0]


@router.patch("/{appointment_id}/complete")
async def complete_appointment(
    appointment_id: str,
    current_doctor=Depends(get_current_doctor),
):
    doctor = current_doctor["doctor"]
    hp_id = doctor.get("healthpost_id")  

    query = (
        supabase.table("appointments")
        .select("*")
        .eq("id", appointment_id)
        .eq("doctor_id", doctor["id"])
    )
    query = _apply_hp_filter(query, hp_id)
    appt = query.maybe_single().execute()

    if not appt or not appt.data:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.data["status"] not in ["confirmed", "ongoing"]:
        raise HTTPException(status_code=400, detail="Only confirmed/ongoing appointments can be completed")

    result = (
        supabase.table("appointments")
        .update({"status": "completed", "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", appointment_id)
        .execute()
    )
    return result.data[0]


@router.patch("/{appointment_id}/no-show")
async def no_show_appointment(
    appointment_id: str,
    current_doctor=Depends(get_current_doctor),
):
    doctor = current_doctor["doctor"]
    hp_id = doctor.get("healthpost_id")  

    query = (
        supabase.table("appointments")
        .select("*")
        .eq("id", appointment_id)
        .eq("doctor_id", doctor["id"])
    )
    query = _apply_hp_filter(query, hp_id)
    appt = query.maybe_single().execute()

    if not appt or not appt.data:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.data["status"] not in ["confirmed", "ongoing"]:
        raise HTTPException(status_code=400, detail="Only confirmed/ongoing appointments can be marked as no-show")

    result = (
        supabase.table("appointments")
        .update({"status": "no_show", "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", appointment_id)
        .execute()
    )
    return result.data[0]