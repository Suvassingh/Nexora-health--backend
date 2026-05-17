from fastapi import APIRouter, Depends, HTTPException
from app.schemas.prescription import PrescriptionCreate, PrescriptionResponse
from app.core.dependencies import get_current_user, get_current_doctor
from app.database.supabase_client import supabase

router = APIRouter()

# Doctor creates prescription
@router.post("/")
async def create_prescription(data: PrescriptionCreate, current=Depends(get_current_doctor)):
    doctor = current["doctor"]

    # insert prescription
    prescription = {
        "consultation_id": str(data.consultation_id),
        "patient_id": str(data.patient_id),
        "doctor_id": doctor["id"],
        "diagnosis": data.diagnosis,
        "notes": data.notes,
        "follow_up_date": data.follow_up_date.isoformat() if data.follow_up_date else None,
    }
    result = supabase.table("prescriptions").insert(prescription).execute()
    prescription_id = result.data[0]["id"]

    # insert items
    items = [
        {
            "prescription_id": prescription_id,
            "medicine_name": item.medicine_name,
            "dosage": item.dosage,
            "frequency": item.frequency,
            "duration_days": item.duration_days,
            "instructions": item.instructions,
        }
        for item in data.items
    ]
    supabase.table("prescription_items").insert(items).execute()

    # return full prescription with items
    return await get_prescription(prescription_id, current["user"])


# Get prescription by id with items
@router.get("/{prescription_id}")
async def get_prescription(prescription_id: str, current_user=Depends(get_current_user)):
    prescription = supabase.table("prescriptions").select("*").eq("id", prescription_id).single().execute()
    if not prescription.data:
        raise HTTPException(status_code=404, detail="Prescription not found")

    items = supabase.table("prescription_items").select("*").eq("prescription_id", prescription_id).execute()
    return {**prescription.data, "items": items.data}


# Patient gets all their prescriptions
@router.get("/patient/my")
async def my_prescriptions(current_user=Depends(get_current_user)):
    result = supabase.table("prescriptions") \
        .select("*, doctors(specialty, user_profiles(full_name))") \
        .eq("patient_id", current_user["id"]) \
        .order("issued_at", desc=True) \
        .execute()

    prescriptions = []
    for p in result.data:
        items = supabase.table("prescription_items").select("*").eq("prescription_id", p["id"]).execute()
        prescriptions.append({**p, "items": items.data})
    return prescriptions


# Doctor gets all prescriptions they issued
@router.get("/doctor/issued")
async def issued_prescriptions(current=Depends(get_current_doctor)):
    doctor = current["doctor"]
    result = supabase.table("prescriptions") \
        .select("*, user_profiles!patient_id(full_name, avatar_url)") \
        .eq("doctor_id", doctor["id"]) \
        .order("issued_at", desc=True) \
        .execute()

    prescriptions = []
    for p in result.data:
        items = supabase.table("prescription_items").select("*").eq("prescription_id", p["id"]).execute()
        prescriptions.append({**p, "items": items.data})
    return prescriptions