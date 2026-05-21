from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import date

from app.core.dependencies import get_current_user, get_current_doctor
from app.database.supabase_client import supabase
from app.schemas.prescription import DirectPrescriptionCreate

router = APIRouter()


@router.post("/direct")
async def create_direct_prescription(
    data: DirectPrescriptionCreate,
    current = Depends(get_current_doctor),   # doctor only
):
    """
    Create a prescription directly from the health record screen.
    This endpoint is only for doctors.
    """
    doctor = current["doctor"]

    # Verify doctor has access to this patient (must have an appointment)
    access = (
        supabase.table("appointments")
        .select("id")
        .eq("patient_id", data.patient_id)
        .eq("doctor_id", doctor["id"])
        .not_.in_("status", ["cancelled", "no_show"])
        .limit(1)
        .execute()
    )
    if not access.data:
        raise HTTPException(
            status_code=403,
            detail="You do not have a valid appointment with this patient",
        )

    # Insert prescription
    prescription_payload = {
        "patient_id":     data.patient_id,
        "doctor_id":      doctor["id"],
        "diagnosis":      data.diagnosis,
        "notes":          data.notes,
        "follow_up_date": data.follow_up_date.isoformat() if data.follow_up_date else None,
    }
    res = supabase.table("prescriptions").insert(prescription_payload).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create prescription")

    prescription_id = res.data[0]["id"]

    # Insert prescription items
    if data.items:
        items_payload = [
            {
                "prescription_id": prescription_id,
                "medicine_name":   item.medicine_name,
                "dosage":          item.dosage,
                "frequency":       item.frequency,
                "duration_days":   item.duration_days,
                "instructions":    item.instructions,
            }
            for item in data.items
        ]
        supabase.table("prescription_items").insert(items_payload).execute()

    # Fetch the complete prescription with items
    full = supabase.table("prescriptions").select("*").eq("id", prescription_id).single().execute()
    items_res = supabase.table("prescription_items").select("*").eq("prescription_id", prescription_id).execute()
    return {**full.data, "items": items_res.data or []}


@router.get("/patient/{patient_id}")
async def get_patient_prescriptions(
    patient_id: str,
    limit: int = 10,
    current_user = Depends(get_current_user),   # accepts doctor OR patient
):
    """
    Fetch all prescriptions for a patient.
    - Doctors: must have an appointment with the patient.
    - Patients: can only see their own records.
    """
    user = current_user
    # Determine role – handle both "role" and "user_role" keys
    role = user.get("role") or user.get("user_role")
    user_id = user.get("id")

    #  Patient access 
    if role == "patient" or (role is None and user_id == patient_id):
        if user_id != patient_id:
            raise HTTPException(status_code=403, detail="You can only view your own prescriptions")

    #  Doctor access 
    elif role == "doctor":
        doctor_id = user.get("doctor", {}).get("id")
        if not doctor_id:
            raise HTTPException(status_code=403, detail="Doctor information missing")

        # Verify doctor has an appointment with this patient
        access = (
            supabase.table("appointments")
            .select("id")
            .eq("patient_id", patient_id)
            .eq("doctor_id", doctor_id)
            .not_.in_("status", ["cancelled", "no_show"])
            .limit(1)
            .execute()
        )
        if not access.data:
            raise HTTPException(status_code=403, detail="You are not the doctor of this patient")

    #  Fallback (e.g. user role not set) 
    else:
        # If no role but the user_id equals the requested patient_id, allow access
        if user_id == patient_id:
            pass   # grant access
        else:
            raise HTTPException(
                status_code=403,
                detail="Access denied – you are not authorised to view these prescriptions"
            )

    #  Fetch prescriptions 
    res = (
        supabase.table("prescriptions")
        .select(
            "id, diagnosis, notes, follow_up_date, issued_at, "
            "doctors!prescriptions_doctor_id_fkey("
            "  specialty,"
            "  user_profiles!doctors_user_id_fkey(full_name)"
            ")"
        )
        .eq("patient_id", patient_id)
        .order("issued_at", desc=True)
        .limit(min(limit, 50))
        .execute()
    )

    prescriptions = []
    for p in res.data or []:
        items_res = (
            supabase.table("prescription_items")
            .select("medicine_name, dosage, frequency, duration_days, instructions")
            .eq("prescription_id", p["id"])
            .execute()
        )
        prescriptions.append({**p, "items": items_res.data or []})

    return prescriptions