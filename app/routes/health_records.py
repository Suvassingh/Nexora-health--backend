# from __future__ import annotations

# from datetime import datetime, timezone, date
# from typing import Optional, Literal
# from uuid import UUID

# from fastapi import APIRouter, Depends, HTTPException
# from pydantic import BaseModel

# from app.core.dependencies import get_current_user, get_current_doctor
# from app.database.supabase_client import supabase
# from app.schemas.health_record import AllergyCreate, ConditionCreate, FamilyHistoryCreate, HistoryEntryCreate, ImmunisationCreate, VitalsCreate

# router = APIRouter()







# def _assert_access(patient_id: str, current_user: dict) -> None:
#     """
#     Raises 403 if the caller cannot access this patient's record.

#     Rules:
#     - Patient: can only access their own record.
#     - Doctor:  can access ONLY IF the patient has a non-cancelled
#                appointment with THIS SPECIFIC DOCTOR.
#                (Previously it only checked the healthpost — now it
#                also checks doctor_id, so cross-doctor access is blocked.)
#     """
#     #  Patient: own record only 
#     if current_user["role"] == "patient":
#         if patient_id != current_user["id"]:
#             raise HTTPException(
#                 status_code=403,
#                 detail="You can only access your own health record",
#             )
#         return

#     if current_user["role"] != "doctor":
#         raise HTTPException(status_code=403, detail="Access denied")

#     #  Doctor: fetch their own doctor row 
#     doctor_res = (
#         supabase.table("doctors")
#         .select("id, healthpost_id, is_active")
#         .eq("user_id", current_user["id"])
#         .maybe_single()
#         .execute()
#     )
#     if not doctor_res or not doctor_res.data:
#         raise HTTPException(status_code=403, detail="Doctor record not found")

#     doctor = doctor_res.data

#     if not doctor["is_active"]:
#         raise HTTPException(status_code=403, detail="Your doctor account is inactive")

#     if not doctor["healthpost_id"]:
#         raise HTTPException(
#             status_code=403,
#             detail="Your account is not assigned to a healthpost",
#         )

#     access_check = (
#         supabase.table("appointments")
#         .select("id")
#         .eq("patient_id",    patient_id)
#         .eq("doctor_id",     doctor["id"])            
#         .eq("healthpost_id", doctor["healthpost_id"]) 
#         .not_.in_("status", ["cancelled", "no_show"])
#         .limit(1)
#         .execute()
#     )

#     if not access_check.data:
#         raise HTTPException(
#             status_code=403,
#             detail="This patient has no appointments with you",
#         )


# def _fetch_vitals_trend(patient_id: str, limit: int = 10) -> list:
#     result = (
#         supabase.table("patient_vitals")
#         .select(
#             "id, bp_systolic, bp_diastolic, heart_rate, spo2, "
#             "temperature_c, weight_kg, height_cm, bmi, recorded_at, notes"
#         )
#         .eq("patient_id", patient_id)
#         .order("recorded_at", desc=True)
#         .limit(limit)
#         .execute()
#     )
#     return result.data or []


# # 1. SUMMARY 

# @router.get("/summary/{patient_id}")
# async def get_patient_summary(
#     patient_id: str,
#     current_user=Depends(get_current_user),
# ):
#     _assert_access(patient_id, current_user)   

#     profile_res = (
#         supabase.table("user_profiles")
#         .select(
#             "id, full_name, avatar_url, phone, gender, "
#             "date_of_birth, province, district, municipality"
#         )
#         .eq("id", patient_id)
#         .maybe_single()
#         .execute()
#     )
    
#     if not profile_res or not profile_res.data:
#         raise HTTPException(status_code=404, detail="Patient not found")

#     profile = profile_res.data
#     patients_res = (
#         supabase.table("patients")
#         .select("blood_group")
#         .eq("user_id", patient_id)
#         .maybe_single()
#         .execute()
#     )
#     if patients_res and patients_res.data:
#         profile["blood_group"] = patients_res.data.get("blood_group")
#     else:
#         profile["blood_group"] = None
#     if profile.get("date_of_birth"):
#         try:
#             dob   = date.fromisoformat(profile["date_of_birth"])
#             today = date.today()
#             profile["age"] = today.year - dob.year - (
#                 (today.month, today.day) < (dob.month, dob.day)
#             )
#         except Exception:
#             profile["age"] = None
#     else:
#         profile["age"] = None

#     allergies_res = (
#         supabase.table("patient_allergies")
#         .select("id, allergen, reaction, severity, notes, recorded_at")
#         .eq("patient_id", patient_id)
#         .eq("is_active", True)
#         .execute()
#     )
#     severity_order = {"severe": 0, "moderate": 1, "mild": 2}
#     allergies = sorted(
#         allergies_res.data or [],
#         key=lambda a: severity_order.get(a.get("severity", "moderate"), 1),
#     )

#     conditions_res = (
#         supabase.table("patient_conditions")
#         .select("id, condition_name, icd_code, diagnosed_date, status, notes")
#         .eq("patient_id", patient_id)
#         .in_("status", ["active", "managed"])
#         .order("created_at", desc=True)
#         .execute()
#     )
#     conditions = conditions_res.data or []

#     vitals   = _fetch_vitals_trend(patient_id, limit=5)
#     latest_v = vitals[0] if vitals else None

#     history_res = (
#         supabase.table("medical_history_entries")
#         .select(
#             "id, chief_complaint, diagnosis, icd_code, treatment_plan, "
#             "follow_up_days, consultation_type, created_at, "
#             "doctors!medical_history_entries_doctor_id_fkey("
#             "  specialty,"
#             "  user_profiles!doctors_user_id_fkey(full_name)"
#             ")"
#         )
#         .eq("patient_id", patient_id)
#         .order("created_at", desc=True)
#         .limit(10)
#         .execute()
#     )
#     history = history_res.data or []

#     family_res = (
#         supabase.table("patient_family_history")
#         .select("id, relation, condition, notes")
#         .eq("patient_id", patient_id)
#         .execute()
#     )
#     family_history = family_res.data or []

#     immunisations_res = (
#         supabase.table("patient_immunisations")
#         .select("id, vaccine_name, dose_number, administered_at, next_due_date, notes")
#         .eq("patient_id", patient_id)
#         .order("administered_at", desc=True)
#         .execute()
#     )
#     immunisations = immunisations_res.data or []
#     today_str = date.today().isoformat()
#     for imm in immunisations:
#         imm["overdue"] = bool(
#             imm.get("next_due_date") and imm["next_due_date"] < today_str
#         )

#     presc_res = (
#         supabase.table("prescriptions")
#         .select(
#             "id, diagnosis, notes, follow_up_date, issued_at, "
#             "doctors!prescriptions_doctor_id_fkey("
#             "  specialty,"
#             "  user_profiles!doctors_user_id_fkey(full_name)"
#             ")"
#         )
#         .eq("patient_id", patient_id)
#         .order("issued_at", desc=True)
#         .limit(1)
#         .execute()
#     )
#     latest_prescription = None
#     total_prescriptions = 0
#     if presc_res.data:
#         latest_prescription = presc_res.data[0]
#         items_res = (
#             supabase.table("prescription_items")
#             .select("medicine_name, dosage, frequency, duration_days, instructions")
#             .eq("prescription_id", latest_prescription["id"])
#             .execute()
#         )
#         latest_prescription["items"] = items_res.data or []
#         count_res = (
#             supabase.table("prescriptions")
#             .select("id", count="exact")
#             .eq("patient_id", patient_id)
#             .execute()
#         )
#         total_prescriptions = count_res.count or 0

#     return {
#         "profile":        profile,
#         "allergies":      allergies,
#         "conditions":     conditions,
#         "vitals": {
#             "latest": latest_v,
#             "trend":  vitals,
#         },
#         "medical_history": history,
#         "family_history":  family_history,
#         "immunisations":   immunisations,
#         "prescriptions": {
#             "total":  total_prescriptions,
#             "latest": latest_prescription,
#         },
#         "flags": {
#             "has_severe_allergy":   any(a["severity"] == "severe" for a in allergies),
#             "has_active_condition": any(c["status"] == "active" for c in conditions),
#             "has_overdue_vaccine":  any(i["overdue"] for i in immunisations),
#             "low_spo2": (
#                 latest_v["spo2"] is not None and latest_v["spo2"] < 94
#                 if latest_v else False
#             ),
#         },
#     }

# # 2–7. INDIVIDUAL ENDPOINTS  

# @router.get("/{patient_id}/allergies")
# async def get_allergies(patient_id: str, current_user=Depends(get_current_user)):
#     _assert_access(patient_id, current_user)
#     res = (
#         supabase.table("patient_allergies")
#         .select("*")
#         .eq("patient_id", patient_id)
#         .order("recorded_at", desc=True)
#         .execute()
#     )
#     return res.data or []

# @router.post("/{patient_id}/allergies")
# async def add_allergy(
#     patient_id: str,
#     data: AllergyCreate,
#     current_user=Depends(get_current_user),
# ):
#     _assert_access(patient_id, current_user)
#     payload = {
#         "patient_id": patient_id,
#         "allergen":   data.allergen,
#         "reaction":   data.reaction,
#         "severity":   data.severity,
#         "notes":      data.notes,
#         "recorded_by": current_user["id"],
#         "is_active":  True,
#     }
#     res = supabase.table("patient_allergies").insert(payload).execute()
#     return res.data[0]

# @router.patch("/{patient_id}/allergies/{allergy_id}")
# async def update_allergy(
#     patient_id: str,
#     allergy_id: str,
#     is_active: bool,
#     current_user=Depends(get_current_user),
# ):
#     _assert_access(patient_id, current_user)
#     res = (
#         supabase.table("patient_allergies")
#         .update({"is_active": is_active})
#         .eq("id", allergy_id)
#         .eq("patient_id", patient_id)
#         .execute()
#     )
#     if not res.data:
#         raise HTTPException(status_code=404, detail="Allergy not found")
#     return res.data[0]

# @router.get("/{patient_id}/conditions")
# async def get_conditions(patient_id: str, current_user=Depends(get_current_user)):
#     _assert_access(patient_id, current_user)
#     res = (
#         supabase.table("patient_conditions")
#         .select("*")
#         .eq("patient_id", patient_id)
#         .order("created_at", desc=True)
#         .execute()
#     )
#     return res.data or []

# @router.post("/{patient_id}/conditions")
# async def add_condition(
#     patient_id: str,
#     data: ConditionCreate,
#     current=Depends(get_current_doctor),
# ):
#     _assert_access(patient_id, current["user"])
#     payload = {
#         "patient_id":     patient_id,
#         "condition_name": data.condition_name,
#         "icd_code":       data.icd_code,
#         "diagnosed_date": data.diagnosed_date.isoformat() if data.diagnosed_date else None,
#         "diagnosed_by":   current["user"]["id"],
#         "status":         data.status,
#         "notes":          data.notes,
#     }
#     res = supabase.table("patient_conditions").insert(
#         {k: v for k, v in payload.items() if v is not None}
#     ).execute()
#     return res.data[0]

# @router.patch("/{patient_id}/conditions/{condition_id}")
# async def update_condition_status(
#     patient_id:   str,
#     condition_id: str,
#     status:       str,
#     current=Depends(get_current_doctor),
# ):
#     _assert_access(patient_id, current["user"])
#     if status not in ["active", "managed", "resolved"]:
#         raise HTTPException(status_code=400, detail="Invalid status")
#     res = (
#         supabase.table("patient_conditions")
#         .update({"status": status})
#         .eq("id", condition_id)
#         .eq("patient_id", patient_id)
#         .execute()
#     )
#     if not res.data:
#         raise HTTPException(status_code=404, detail="Condition not found")
#     return res.data[0]

# @router.post("/vitals")
# async def record_vitals(data: VitalsCreate, current_user=Depends(get_current_user)):
#     if current_user["role"] == "patient":
#         raise HTTPException(status_code=403, detail="Only staff can record vitals")
#     _assert_access(data.patient_id, current_user)
#     payload = {k: v for k, v in {
#         "patient_id":     data.patient_id,
#         "appointment_id": data.appointment_id,
#         "recorded_by":    current_user["id"],
#         "bp_systolic":    data.bp_systolic,
#         "bp_diastolic":   data.bp_diastolic,
#         "heart_rate":     data.heart_rate,
#         "spo2":           data.spo2,
#         "temperature_c":  data.temperature_c,
#         "weight_kg":      data.weight_kg,
#         "height_cm":      data.height_cm,
#         "notes":          data.notes,
#     }.items() if v is not None}
#     res = supabase.table("patient_vitals").insert(payload).execute()
#     return res.data[0]

# @router.get("/{patient_id}/vitals")
# async def get_vitals_history(
#     patient_id: str,
#     limit: int = 20,
#     current_user=Depends(get_current_user),
# ):
#     _assert_access(patient_id, current_user)
#     return _fetch_vitals_trend(patient_id, limit=min(limit, 50))

# @router.post("/history")
# async def create_history_entry(
#     data: HistoryEntryCreate,
#     current=Depends(get_current_doctor),
# ):
#     _assert_access(data.patient_id, current["user"])
#     payload = {k: v for k, v in {
#         "patient_id":         data.patient_id,
#         "consultation_id":    data.consultation_id,
#         "appointment_id":     data.appointment_id,
#         "doctor_id":          current["doctor"]["id"],
#         "chief_complaint":    data.chief_complaint,
#         "history_of_illness": data.history_of_illness,
#         "examination_notes":  data.examination_notes,
#         "diagnosis":          data.diagnosis,
#         "icd_code":           data.icd_code,
#         "treatment_plan":     data.treatment_plan,
#         "follow_up_days":     data.follow_up_days,
#         "consultation_type":  data.consultation_type,
#     }.items() if v is not None}
#     res = supabase.table("medical_history_entries").insert(payload).execute()
#     return res.data[0]

# @router.get("/{patient_id}/history")
# async def get_history(
#     patient_id: str,
#     limit: int = 20,
#     current_user=Depends(get_current_user),
# ):
#     _assert_access(patient_id, current_user)
#     res = (
#         supabase.table("medical_history_entries")
#         .select(
#             "*, "
#             "doctors!medical_history_entries_doctor_id_fkey("
#             "  specialty,"
#             "  user_profiles!doctors_user_id_fkey(full_name, avatar_url)"
#             ")"
#         )
#         .eq("patient_id", patient_id)
#         .order("created_at", desc=True)
#         .limit(min(limit, 50))
#         .execute()
#     )
#     return res.data or []

# @router.get("/{patient_id}/family-history")
# async def get_family_history(patient_id: str, current_user=Depends(get_current_user)):
#     _assert_access(patient_id, current_user)
#     res = supabase.table("patient_family_history").select("*").eq("patient_id", patient_id).execute()
#     return res.data or []

# @router.post("/{patient_id}/family-history")
# async def add_family_history(
#     patient_id: str,
#     data: FamilyHistoryCreate,
#     current_user=Depends(get_current_user),
# ):
#     _assert_access(patient_id, current_user)
#     res = supabase.table("patient_family_history").insert({
#         "patient_id": patient_id,
#         "relation":   data.relation,
#         "condition":  data.condition,
#         "notes":      data.notes,
#     }).execute()
#     return res.data[0]

# @router.delete("/{patient_id}/family-history/{entry_id}", status_code=204)
# async def delete_family_history(
#     patient_id: str,
#     entry_id: str,
#     current_user=Depends(get_current_user),
# ):
    
#     _assert_access(patient_id, current_user)
#     supabase.table("patient_family_history").delete().eq("id", entry_id).eq("patient_id", patient_id).execute()

# @router.get("/{patient_id}/immunisations")
# async def get_immunisations(patient_id: str, current_user=Depends(get_current_user)):
#     _assert_access(patient_id, current_user)
#     res = (
#         supabase.table("patient_immunisations")
#         .select("*")
#         .eq("patient_id", patient_id)
#         .order("administered_at", desc=True)
#         .execute()
#     )
#     today_str = date.today().isoformat()
#     data = res.data or []
#     for imm in data:
#         imm["overdue"] = bool(imm.get("next_due_date") and imm["next_due_date"] < today_str)
#     return data

# @router.post("/immunisations")
# async def record_immunisation(
#     data: ImmunisationCreate,
#     current_user=Depends(get_current_user),
# ):
#     if current_user["role"] == "patient":
#         raise HTTPException(status_code=403, detail="Only staff can record immunisations")
#     _assert_access(data.patient_id, current_user)
#     payload = {k: v for k, v in {
#         "patient_id":      data.patient_id,
#         "vaccine_name":    data.vaccine_name,
#         "dose_number":     data.dose_number,
#         "administered_by": current_user["id"],
#         "administered_at": (
#             data.administered_at.isoformat()
#             if data.administered_at
#             else datetime.now(timezone.utc).isoformat()
#         ),
#         "batch_number":    data.batch_number,
#         "next_due_date":   data.next_due_date.isoformat() if data.next_due_date else None,
#         "notes":           data.notes,
#     }.items() if v is not None}
#     res = supabase.table("patient_immunisations").insert(payload).execute()
#     return res.data[0]

  


# class AllergyUpdate(BaseModel):
#     allergen:  Optional[str]  = None
#     reaction:  Optional[str]  = None
#     severity:  Optional[str]  = None   
#     notes:     Optional[str]  = None
#     is_active: Optional[bool] = None


# class ConditionUpdate(BaseModel):
#     condition_name: Optional[str]  = None
#     icd_code:       Optional[str]  = None
#     diagnosed_date: Optional[date] = None
#     status:         Optional[str]  = None   
#     notes:          Optional[str]  = None


# class VitalsUpdate(BaseModel):
#     bp_systolic:   Optional[int]   = None
#     bp_diastolic:  Optional[int]   = None
#     heart_rate:    Optional[int]   = None
#     spo2:          Optional[int]   = None
#     temperature_c: Optional[float] = None
#     weight_kg:     Optional[float] = None
#     height_cm:     Optional[float] = None
#     notes:         Optional[str]   = None


# class HistoryUpdate(BaseModel):
#     chief_complaint:     Optional[str] = None
#     history_of_illness:  Optional[str] = None
#     examination_notes:   Optional[str] = None
#     diagnosis:           Optional[str] = None
#     icd_code:            Optional[str] = None
#     treatment_plan:      Optional[str] = None
#     follow_up_days:      Optional[int] = None
#     consultation_type:   Optional[str] = None


# class FamilyHistoryUpdate(BaseModel):
#     relation:  Optional[str] = None
#     condition: Optional[str] = None
#     notes:     Optional[str] = None


# class ImmunisationUpdate(BaseModel):
#     vaccine_name:    Optional[str]      = None
#     dose_number:     Optional[int]      = None
#     administered_at: Optional[datetime] = None
#     batch_number:    Optional[str]      = None
#     next_due_date:   Optional[date]     = None
#     notes:           Optional[str]      = None



# def _assert_access(patient_id: str, current_user: dict) -> None:
#     """
#     Raises 403 if the caller cannot access this patient's record.
#     (Identical to the guard in health_records.py – skip if merging.)
#     """
#     if current_user["role"] == "patient":
#         if patient_id != current_user["id"]:
#             raise HTTPException(
#                 status_code=403,
#                 detail="You can only access your own health record",
#             )
#         return

#     if current_user["role"] != "doctor":
#         raise HTTPException(status_code=403, detail="Access denied")

#     doctor_res = (
#         supabase.table("doctors")
#         .select("id, healthpost_id, is_active")
#         .eq("user_id", current_user["id"])
#         .maybe_single()
#         .execute()
#     )
#     if not doctor_res or not doctor_res.data:
#         raise HTTPException(status_code=403, detail="Doctor record not found")

#     doctor = doctor_res.data
#     if not doctor["is_active"]:
#         raise HTTPException(status_code=403, detail="Your doctor account is inactive")
#     if not doctor["healthpost_id"]:
#         raise HTTPException(
#             status_code=403,
#             detail="Your account is not assigned to a healthpost",
#         )

#     access_check = (
#         supabase.table("appointments")
#         .select("id")
#         .eq("patient_id",    patient_id)
#         .eq("doctor_id",     doctor["id"])
#         .eq("healthpost_id", doctor["healthpost_id"])
#         .not_.in_("status", ["cancelled", "no_show"])
#         .limit(1)
#         .execute()
#     )
#     if not access_check.data:
#         raise HTTPException(
#             status_code=403,
#             detail="This patient has no appointments with you",
#         )



# @router.patch("/vitals/{vitals_id}")
# async def update_vitals(
#     vitals_id: str,
#     data: VitalsUpdate,
#     current=Depends(get_current_doctor),
# ):
#     """Doctor updates an existing vitals record."""
#     # Fetch the row first to grab patient_id for the access check
#     row_res = (
#         supabase.table("patient_vitals")
#         .select("patient_id")
#         .eq("id", vitals_id)
#         .maybe_single()
#         .execute()
#     )
#     if not row_res or not row_res.data:
#         raise HTTPException(status_code=404, detail="Vitals record not found")

#     patient_id = row_res.data["patient_id"]
#     _assert_access(patient_id, current["user"])

#     payload = {k: v for k, v in data.model_dump().items() if v is not None}
#     if not payload:
#         raise HTTPException(status_code=400, detail="No fields to update")

#     payload["updated_at"] = datetime.now(timezone.utc).isoformat()

#     res = (
#         supabase.table("patient_vitals")
#         .update(payload)
#         .eq("id", vitals_id)
#         .execute()
#     )
#     if not res.data:
#         raise HTTPException(status_code=404, detail="Vitals record not found")
#     return res.data[0]



# @router.patch("/{patient_id}/allergies/{allergy_id}/edit")
# async def edit_allergy(
#     patient_id: str,
#     allergy_id: str,
#     data: AllergyUpdate,
#     current_user=Depends(get_current_user),
# ):
#     """Full-field allergy update (doctors only in practice; guard enforced)."""
#     _assert_access(patient_id, current_user)

#     payload = {k: v for k, v in data.model_dump().items() if v is not None}
#     if not payload:
#         raise HTTPException(status_code=400, detail="No fields to update")

#     res = (
#         supabase.table("patient_allergies")
#         .update(payload)
#         .eq("id",         allergy_id)
#         .eq("patient_id", patient_id)
#         .execute()
#     )
#     if not res.data:
#         raise HTTPException(status_code=404, detail="Allergy not found")
#     return res.data[0]



# @router.patch("/{patient_id}/conditions/{condition_id}/edit")
# async def edit_condition(
#     patient_id:   str,
#     condition_id: str,
#     data: ConditionUpdate,
#     current=Depends(get_current_doctor),
# ):
#     """Full-field condition update."""
#     _assert_access(patient_id, current["user"])

#     if data.status and data.status not in ["active", "managed", "resolved"]:
#         raise HTTPException(status_code=400, detail="Invalid status")

#     payload = {k: v for k, v in data.model_dump().items() if v is not None}
#     if data.diagnosed_date:
#         payload["diagnosed_date"] = data.diagnosed_date.isoformat()
#     if not payload:
#         raise HTTPException(status_code=400, detail="No fields to update")

#     res = (
#         supabase.table("patient_conditions")
#         .update(payload)
#         .eq("id",         condition_id)
#         .eq("patient_id", patient_id)
#         .execute()
#     )
#     if not res.data:
#         raise HTTPException(status_code=404, detail="Condition not found")
#     return res.data[0]



# @router.patch("/history/{entry_id}")
# async def update_history_entry(
#     entry_id: str,
#     data: HistoryUpdate,
#     current=Depends(get_current_doctor),
# ):
#     """Doctor edits an existing medical-history entry they authored."""
#     # Fetch to verify ownership + get patient_id
#     row_res = (
#         supabase.table("medical_history_entries")
#         .select("patient_id, doctor_id")
#         .eq("id", entry_id)
#         .maybe_single()
#         .execute()
#     )
#     if not row_res or not row_res.data:
#         raise HTTPException(status_code=404, detail="History entry not found")

#     row = row_res.data
#     _assert_access(row["patient_id"], current["user"])

#     # Only the authoring doctor may edit
#     if row["doctor_id"] != current["doctor"]["id"]:
#         raise HTTPException(
#             status_code=403,
#             detail="You can only edit history entries you created",
#         )

#     payload = {k: v for k, v in data.model_dump().items() if v is not None}
#     if not payload:
#         raise HTTPException(status_code=400, detail="No fields to update")

#     payload["updated_at"] = datetime.now(timezone.utc).isoformat()

#     res = (
#         supabase.table("medical_history_entries")
#         .update(payload)
#         .eq("id", entry_id)
#         .execute()
#     )
#     if not res.data:
#         raise HTTPException(status_code=404, detail="History entry not found")
#     return res.data[0]



# @router.patch("/{patient_id}/family-history/{entry_id}")
# async def update_family_history(
#     patient_id: str,
#     entry_id:   str,
#     data: FamilyHistoryUpdate,
#     current_user=Depends(get_current_user),
# ):
#     """Edit an existing family-history entry."""
#     _assert_access(patient_id, current_user)

#     payload = {k: v for k, v in data.model_dump().items() if v is not None}
#     if not payload:
#         raise HTTPException(status_code=400, detail="No fields to update")

#     res = (
#         supabase.table("patient_family_history")
#         .update(payload)
#         .eq("id",         entry_id)
#         .eq("patient_id", patient_id)
#         .execute()
#     )
#     if not res.data:
#         raise HTTPException(status_code=404, detail="Family history entry not found")
#     return res.data[0]



# @router.patch("/immunisations/{imm_id}")
# async def update_immunisation(
#     imm_id: str,
#     data: ImmunisationUpdate,
#     current_user=Depends(get_current_user),
# ):
#     """Doctor edits an existing immunisation record."""
#     if current_user["role"] == "patient":
#         raise HTTPException(status_code=403, detail="Only staff can edit immunisations")

#     row_res = (
#         supabase.table("patient_immunisations")
#         .select("patient_id")
#         .eq("id", imm_id)
#         .maybe_single()
#         .execute()
#     )
#     if not row_res or not row_res.data:
#         raise HTTPException(status_code=404, detail="Immunisation record not found")

#     patient_id = row_res.data["patient_id"]
#     _assert_access(patient_id, current_user)

#     payload = {k: v for k, v in data.model_dump().items() if v is not None}
#     if data.administered_at:
#         payload["administered_at"] = data.administered_at.isoformat()
#     if data.next_due_date:
#         payload["next_due_date"] = data.next_due_date.isoformat()
#     if not payload:
#         raise HTTPException(status_code=400, detail="No fields to update")

#     res = (
#         supabase.table("patient_immunisations")
#         .update(payload)
#         .eq("id", imm_id)
#         .execute()
#     )
#     if not res.data:
#         raise HTTPException(status_code=404, detail="Immunisation record not found")
#     return res.data[0]


from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Optional, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.dependencies import get_current_user, get_current_doctor
from app.database.supabase_client import supabase
from app.schemas.health_record import AllergyCreate, ConditionCreate, FamilyHistoryCreate, HistoryEntryCreate, ImmunisationCreate, VitalsCreate
from app.utils.encryption import encrypt_text, decrypt_text   # <-- ADDED

router = APIRouter()


def _assert_access(patient_id: str, current_user: dict) -> None:
    # (unchanged – same as original)
    if current_user["role"] == "patient":
        if patient_id != current_user["id"]:
            raise HTTPException(
                status_code=403,
                detail="You can only access your own health record",
            )
        return

    if current_user["role"] != "doctor":
        raise HTTPException(status_code=403, detail="Access denied")

    doctor_res = (
        supabase.table("doctors")
        .select("id, healthpost_id, is_active")
        .eq("user_id", current_user["id"])
        .maybe_single()
        .execute()
    )
    if not doctor_res or not doctor_res.data:
        raise HTTPException(status_code=403, detail="Doctor record not found")

    doctor = doctor_res.data
    if not doctor["is_active"]:
        raise HTTPException(status_code=403, detail="Your doctor account is inactive")
    if not doctor["healthpost_id"]:
        raise HTTPException(
            status_code=403,
            detail="Your account is not assigned to a healthpost",
        )

    access_check = (
        supabase.table("appointments")
        .select("id")
        .eq("patient_id",    patient_id)
        .eq("doctor_id",     doctor["id"])
        .eq("healthpost_id", doctor["healthpost_id"])
        .not_.in_("status", ["cancelled", "no_show"])
        .limit(1)
        .execute()
    )
    if not access_check.data:
        raise HTTPException(
            status_code=403,
            detail="This patient has no appointments with you",
        )


def _fetch_vitals_trend(patient_id: str, limit: int = 10) -> list:
    result = (
        supabase.table("patient_vitals")
        .select(
            "id, bp_systolic, bp_diastolic, heart_rate, spo2, "
            "temperature_c, weight_kg, height_cm, bmi, recorded_at, notes"
        )
        .eq("patient_id", patient_id)
        .order("recorded_at", desc=True)
        .limit(limit)
        .execute()
    )
    # Decrypt notes for each vital record
    for item in result.data or []:
        item["notes"] = decrypt_text(item.get("notes"))
    return result.data or []


# 1. SUMMARY

@router.get("/summary/{patient_id}")
async def get_patient_summary(
    patient_id: str,
    current_user=Depends(get_current_user),
):
    _assert_access(patient_id, current_user)

    profile_res = (
        supabase.table("user_profiles")
        .select(
            "id, full_name, avatar_url, phone, gender, "
            "date_of_birth, province, district, municipality"
        )
        .eq("id", patient_id)
        .maybe_single()
        .execute()
    )
    if not profile_res or not profile_res.data:
        raise HTTPException(status_code=404, detail="Patient not found")

    profile = profile_res.data
    patients_res = (
        supabase.table("patients")
        .select("blood_group")
        .eq("user_id", patient_id)
        .maybe_single()
        .execute()
    )
    if patients_res and patients_res.data:
        profile["blood_group"] = patients_res.data.get("blood_group")
    else:
        profile["blood_group"] = None
    if profile.get("date_of_birth"):
        try:
            dob   = date.fromisoformat(profile["date_of_birth"])
            today = date.today()
            profile["age"] = today.year - dob.year - (
                (today.month, today.day) < (dob.month, dob.day)
            )
        except Exception:
            profile["age"] = None
    else:
        profile["age"] = None

    allergies_res = (
        supabase.table("patient_allergies")
        .select("id, allergen, reaction, severity, notes, recorded_at")
        .eq("patient_id", patient_id)
        .eq("is_active", True)
        .execute()
    )
    allergies = []
    for a in allergies_res.data or []:
        allergies.append({
            "id": a["id"],
            "allergen": decrypt_text(a.get("allergen")),
            "reaction": decrypt_text(a.get("reaction")),
            "severity": a["severity"],
            "notes": decrypt_text(a.get("notes")),
            "recorded_at": a["recorded_at"],
        })
    severity_order = {"severe": 0, "moderate": 1, "mild": 2}
    allergies = sorted(allergies, key=lambda a: severity_order.get(a.get("severity", "moderate"), 1))

    conditions_res = (
        supabase.table("patient_conditions")
        .select("id, condition_name, icd_code, diagnosed_date, status, notes")
        .eq("patient_id", patient_id)
        .in_("status", ["active", "managed"])
        .order("created_at", desc=True)
        .execute()
    )
    conditions = []
    for c in conditions_res.data or []:
        conditions.append({
            "id": c["id"],
            "condition_name": decrypt_text(c.get("condition_name")),
            "icd_code": decrypt_text(c.get("icd_code")),
            "diagnosed_date": c["diagnosed_date"],
            "status": c["status"],
            "notes": decrypt_text(c.get("notes")),
        })

    vitals = _fetch_vitals_trend(patient_id, limit=5)
    latest_v = vitals[0] if vitals else None

    history_res = (
        supabase.table("medical_history_entries")
        .select(
            "id, chief_complaint, diagnosis, icd_code, treatment_plan, "
            "follow_up_days, consultation_type, created_at, "
            "doctors!medical_history_entries_doctor_id_fkey("
            "  specialty,"
            "  user_profiles!doctors_user_id_fkey(full_name)"
            ")"
        )
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    history = []
    for h in history_res.data or []:
        history.append({
            "id": h["id"],
            "chief_complaint": decrypt_text(h.get("chief_complaint")),
            "diagnosis": decrypt_text(h.get("diagnosis")),
            "icd_code": decrypt_text(h.get("icd_code")),
            "treatment_plan": decrypt_text(h.get("treatment_plan")),
            "follow_up_days": h["follow_up_days"],
            "consultation_type": h["consultation_type"],
            "created_at": h["created_at"],
            "doctors": h["doctors"],
        })

    family_res = (
        supabase.table("patient_family_history")
        .select("id, relation, condition, notes")
        .eq("patient_id", patient_id)
        .execute()
    )
    family_history = []
    for f in family_res.data or []:
        family_history.append({
            "id": f["id"],
            "relation": decrypt_text(f.get("relation")),
            "condition": decrypt_text(f.get("condition")),
            "notes": decrypt_text(f.get("notes")),
        })

    immunisations_res = (
        supabase.table("patient_immunisations")
        .select("id, vaccine_name, dose_number, administered_at, next_due_date, notes")
        .eq("patient_id", patient_id)
        .order("administered_at", desc=True)
        .execute()
    )
    immunisations = []
    today_str = date.today().isoformat()
    for imm in immunisations_res.data or []:
        imm_dec = {
            "id": imm["id"],
            "vaccine_name": decrypt_text(imm.get("vaccine_name")),
            "dose_number": imm["dose_number"],
            "administered_at": imm["administered_at"],
            "next_due_date": imm["next_due_date"],
            "notes": decrypt_text(imm.get("notes")),
            "overdue": bool(imm.get("next_due_date") and imm["next_due_date"] < today_str),
        }
        immunisations.append(imm_dec)

    presc_res = (
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
        .limit(1)
        .execute()
    )
    latest_prescription = None
    total_prescriptions = 0
    if presc_res.data:
        latest_prescription = presc_res.data[0]
        latest_prescription["diagnosis"] = decrypt_text(latest_prescription.get("diagnosis"))
        latest_prescription["notes"] = decrypt_text(latest_prescription.get("notes"))
        items_res = (
            supabase.table("prescription_items")
            .select("medicine_name, dosage, frequency, duration_days, instructions")
            .eq("prescription_id", latest_prescription["id"])
            .execute()
        )
        items = []
        for it in items_res.data or []:
            items.append({
                "medicine_name": decrypt_text(it.get("medicine_name")),
                "dosage": decrypt_text(it.get("dosage")),
                "frequency": decrypt_text(it.get("frequency")),
                "duration_days": it["duration_days"],
                "instructions": decrypt_text(it.get("instructions")),
            })
        latest_prescription["items"] = items
        count_res = (
            supabase.table("prescriptions")
            .select("id", count="exact")
            .eq("patient_id", patient_id)
            .execute()
        )
        total_prescriptions = count_res.count or 0

    return {
        "profile":        profile,
        "allergies":      allergies,
        "conditions":     conditions,
        "vitals": {
            "latest": latest_v,
            "trend":  vitals,
        },
        "medical_history": history,
        "family_history":  family_history,
        "immunisations":   immunisations,
        "prescriptions": {
            "total":  total_prescriptions,
            "latest": latest_prescription,
        },
        "flags": {
            "has_severe_allergy":   any(a["severity"] == "severe" for a in allergies),
            "has_active_condition": any(c["status"] == "active" for c in conditions),
            "has_overdue_vaccine":  any(i["overdue"] for i in immunisations),
            "low_spo2": (
                latest_v["spo2"] is not None and latest_v["spo2"] < 94
                if latest_v else False
            ),
        },
    }


# 2–7. INDIVIDUAL ENDPOINTS

@router.get("/{patient_id}/allergies")
async def get_allergies(patient_id: str, current_user=Depends(get_current_user)):
    _assert_access(patient_id, current_user)
    res = (
        supabase.table("patient_allergies")
        .select("*")
        .eq("patient_id", patient_id)
        .order("recorded_at", desc=True)
        .execute()
    )
    allergies = []
    for a in res.data or []:
        allergies.append({
            **a,
            "allergen": decrypt_text(a.get("allergen")),
            "reaction": decrypt_text(a.get("reaction")),
            "notes": decrypt_text(a.get("notes")),
        })
    return allergies


@router.post("/{patient_id}/allergies")
async def add_allergy(
    patient_id: str,
    data: AllergyCreate,
    current_user=Depends(get_current_user),
):
    _assert_access(patient_id, current_user)
    payload = {
        "patient_id": patient_id,
        "allergen":   encrypt_text(data.allergen),
        "reaction":   encrypt_text(data.reaction),
        "severity":   data.severity,
        "notes":      encrypt_text(data.notes),
        "recorded_by": current_user["id"],
        "is_active":  True,
    }
    res = supabase.table("patient_allergies").insert(payload).execute()
    result = res.data[0]
    result["allergen"] = decrypt_text(result.get("allergen"))
    result["reaction"] = decrypt_text(result.get("reaction"))
    result["notes"] = decrypt_text(result.get("notes"))
    return result


@router.patch("/{patient_id}/allergies/{allergy_id}")
async def update_allergy(
    patient_id: str,
    allergy_id: str,
    is_active: bool,
    current_user=Depends(get_current_user),
):
    _assert_access(patient_id, current_user)
    res = (
        supabase.table("patient_allergies")
        .update({"is_active": is_active})
        .eq("id", allergy_id)
        .eq("patient_id", patient_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Allergy not found")
    result = res.data[0]
    result["allergen"] = decrypt_text(result.get("allergen"))
    result["reaction"] = decrypt_text(result.get("reaction"))
    result["notes"] = decrypt_text(result.get("notes"))
    return result


@router.get("/{patient_id}/conditions")
async def get_conditions(patient_id: str, current_user=Depends(get_current_user)):
    _assert_access(patient_id, current_user)
    res = (
        supabase.table("patient_conditions")
        .select("*")
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .execute()
    )
    conditions = []
    for c in res.data or []:
        conditions.append({
            **c,
            "condition_name": decrypt_text(c.get("condition_name")),
            "icd_code": decrypt_text(c.get("icd_code")),
            "notes": decrypt_text(c.get("notes")),
        })
    return conditions


@router.post("/{patient_id}/conditions")
async def add_condition(
    patient_id: str,
    data: ConditionCreate,
    current=Depends(get_current_doctor),
):
    _assert_access(patient_id, current["user"])
    payload = {
        "patient_id":     patient_id,
        "condition_name": encrypt_text(data.condition_name),
        "icd_code":       encrypt_text(data.icd_code),
        "diagnosed_date": data.diagnosed_date.isoformat() if data.diagnosed_date else None,
        "diagnosed_by":   current["user"]["id"],
        "status":         data.status,
        "notes":          encrypt_text(data.notes),
    }
    res = supabase.table("patient_conditions").insert(
        {k: v for k, v in payload.items() if v is not None}
    ).execute()
    result = res.data[0]
    result["condition_name"] = decrypt_text(result.get("condition_name"))
    result["icd_code"] = decrypt_text(result.get("icd_code"))
    result["notes"] = decrypt_text(result.get("notes"))
    return result


@router.patch("/{patient_id}/conditions/{condition_id}")
async def update_condition_status(
    patient_id:   str,
    condition_id: str,
    status:       str,
    current=Depends(get_current_doctor),
):
    _assert_access(patient_id, current["user"])
    if status not in ["active", "managed", "resolved"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    res = (
        supabase.table("patient_conditions")
        .update({"status": status})
        .eq("id", condition_id)
        .eq("patient_id", patient_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Condition not found")
    result = res.data[0]
    result["condition_name"] = decrypt_text(result.get("condition_name"))
    result["icd_code"] = decrypt_text(result.get("icd_code"))
    result["notes"] = decrypt_text(result.get("notes"))
    return result


@router.post("/vitals")
async def record_vitals(data: VitalsCreate, current_user=Depends(get_current_user)):
    if current_user["role"] == "patient":
        raise HTTPException(status_code=403, detail="Only staff can record vitals")
    _assert_access(data.patient_id, current_user)
    payload = {k: v for k, v in {
        "patient_id":     data.patient_id,
        "appointment_id": data.appointment_id,
        "recorded_by":    current_user["id"],
        "bp_systolic":    data.bp_systolic,
        "bp_diastolic":   data.bp_diastolic,
        "heart_rate":     data.heart_rate,
        "spo2":           data.spo2,
        "temperature_c":  data.temperature_c,
        "weight_kg":      data.weight_kg,
        "height_cm":      data.height_cm,
        "notes":          encrypt_text(data.notes),   # <-- encrypt notes
    }.items() if v is not None}
    res = supabase.table("patient_vitals").insert(payload).execute()
    result = res.data[0]
    result["notes"] = decrypt_text(result.get("notes"))
    return result


@router.get("/{patient_id}/vitals")
async def get_vitals_history(
    patient_id: str,
    limit: int = 20,
    current_user=Depends(get_current_user),
):
    _assert_access(patient_id, current_user)
    return _fetch_vitals_trend(patient_id, limit=min(limit, 50))


@router.post("/history")
async def create_history_entry(
    data: HistoryEntryCreate,
    current=Depends(get_current_doctor),
):
    _assert_access(data.patient_id, current["user"])
    payload = {k: v for k, v in {
        "patient_id":         data.patient_id,
        "consultation_id":    data.consultation_id,
        "appointment_id":     data.appointment_id,
        "doctor_id":          current["doctor"]["id"],
        "chief_complaint":    encrypt_text(data.chief_complaint),
        "history_of_illness": encrypt_text(data.history_of_illness),
        "examination_notes":  encrypt_text(data.examination_notes),
        "diagnosis":          encrypt_text(data.diagnosis),
        "icd_code":           encrypt_text(data.icd_code),
        "treatment_plan":     encrypt_text(data.treatment_plan),
        "follow_up_days":     data.follow_up_days,
        "consultation_type":  data.consultation_type,
    }.items() if v is not None}
    res = supabase.table("medical_history_entries").insert(payload).execute()
    result = res.data[0]
    for field in ["chief_complaint", "history_of_illness", "examination_notes", "diagnosis", "icd_code", "treatment_plan"]:
        result[field] = decrypt_text(result.get(field))
    return result


@router.get("/{patient_id}/history")
async def get_history(
    patient_id: str,
    limit: int = 20,
    current_user=Depends(get_current_user),
):
    _assert_access(patient_id, current_user)
    res = (
        supabase.table("medical_history_entries")
        .select(
            "*, "
            "doctors!medical_history_entries_doctor_id_fkey("
            "  specialty,"
            "  user_profiles!doctors_user_id_fkey(full_name, avatar_url)"
            ")"
        )
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .limit(min(limit, 50))
        .execute()
    )
    history = []
    for h in res.data or []:
        decrypted = dict(h)
        for field in ["chief_complaint", "history_of_illness", "examination_notes", "diagnosis", "icd_code", "treatment_plan"]:
            decrypted[field] = decrypt_text(h.get(field))
        history.append(decrypted)
    return history


@router.get("/{patient_id}/family-history")
async def get_family_history(patient_id: str, current_user=Depends(get_current_user)):
    _assert_access(patient_id, current_user)
    res = supabase.table("patient_family_history").select("*").eq("patient_id", patient_id).execute()
    family = []
    for f in res.data or []:
        family.append({
            **f,
            "relation": decrypt_text(f.get("relation")),
            "condition": decrypt_text(f.get("condition")),
            "notes": decrypt_text(f.get("notes")),
        })
    return family


@router.post("/{patient_id}/family-history")
async def add_family_history(
    patient_id: str,
    data: FamilyHistoryCreate,
    current_user=Depends(get_current_user),
):
    _assert_access(patient_id, current_user)
    payload = {
        "patient_id": patient_id,
        "relation":   encrypt_text(data.relation),
        "condition":  encrypt_text(data.condition),
        "notes":      encrypt_text(data.notes),
    }
    res = supabase.table("patient_family_history").insert(payload).execute()
    result = res.data[0]
    result["relation"] = decrypt_text(result.get("relation"))
    result["condition"] = decrypt_text(result.get("condition"))
    result["notes"] = decrypt_text(result.get("notes"))
    return result


@router.delete("/{patient_id}/family-history/{entry_id}", status_code=204)
async def delete_family_history(
    patient_id: str,
    entry_id: str,
    current_user=Depends(get_current_user),
):
    _assert_access(patient_id, current_user)
    supabase.table("patient_family_history").delete().eq("id", entry_id).eq("patient_id", patient_id).execute()


@router.get("/{patient_id}/immunisations")
async def get_immunisations(patient_id: str, current_user=Depends(get_current_user)):
    _assert_access(patient_id, current_user)
    res = (
        supabase.table("patient_immunisations")
        .select("*")
        .eq("patient_id", patient_id)
        .order("administered_at", desc=True)
        .execute()
    )
    today_str = date.today().isoformat()
    data = []
    for imm in res.data or []:
        data.append({
            **imm,
            "vaccine_name": decrypt_text(imm.get("vaccine_name")),
            "batch_number": decrypt_text(imm.get("batch_number")),
            "notes": decrypt_text(imm.get("notes")),
            "overdue": bool(imm.get("next_due_date") and imm["next_due_date"] < today_str),
        })
    return data


@router.post("/immunisations")
async def record_immunisation(
    data: ImmunisationCreate,
    current_user=Depends(get_current_user),
):
    if current_user["role"] == "patient":
        raise HTTPException(status_code=403, detail="Only staff can record immunisations")
    _assert_access(data.patient_id, current_user)
    payload = {k: v for k, v in {
        "patient_id":      data.patient_id,
        "vaccine_name":    encrypt_text(data.vaccine_name),
        "dose_number":     data.dose_number,
        "administered_by": current_user["id"],
        "administered_at": (
            data.administered_at.isoformat()
            if data.administered_at
            else datetime.now(timezone.utc).isoformat()
        ),
        "batch_number":    encrypt_text(data.batch_number),
        "next_due_date":   data.next_due_date.isoformat() if data.next_due_date else None,
        "notes":           encrypt_text(data.notes),
    }.items() if v is not None}
    res = supabase.table("patient_immunisations").insert(payload).execute()
    result = res.data[0]
    result["vaccine_name"] = decrypt_text(result.get("vaccine_name"))
    result["batch_number"] = decrypt_text(result.get("batch_number"))
    result["notes"] = decrypt_text(result.get("notes"))
    return result


# ------------------------------
# UPDATE ENDPOINTS (PATCH)
# ------------------------------

class AllergyUpdate(BaseModel):
    allergen:  Optional[str]  = None
    reaction:  Optional[str]  = None
    severity:  Optional[str]  = None
    notes:     Optional[str]  = None
    is_active: Optional[bool] = None


class ConditionUpdate(BaseModel):
    condition_name: Optional[str]  = None
    icd_code:       Optional[str]  = None
    diagnosed_date: Optional[date] = None
    status:         Optional[str]  = None
    notes:          Optional[str]  = None


class VitalsUpdate(BaseModel):
    bp_systolic:   Optional[int]   = None
    bp_diastolic:  Optional[int]   = None
    heart_rate:    Optional[int]   = None
    spo2:          Optional[int]   = None
    temperature_c: Optional[float] = None
    weight_kg:     Optional[float] = None
    height_cm:     Optional[float] = None
    notes:         Optional[str]   = None


class HistoryUpdate(BaseModel):
    chief_complaint:     Optional[str] = None
    history_of_illness:  Optional[str] = None
    examination_notes:   Optional[str] = None
    diagnosis:           Optional[str] = None
    icd_code:            Optional[str] = None
    treatment_plan:      Optional[str] = None
    follow_up_days:      Optional[int] = None
    consultation_type:   Optional[str] = None


class FamilyHistoryUpdate(BaseModel):
    relation:  Optional[str] = None
    condition: Optional[str] = None
    notes:     Optional[str] = None


class ImmunisationUpdate(BaseModel):
    vaccine_name:    Optional[str]      = None
    dose_number:     Optional[int]      = None
    administered_at: Optional[datetime] = None
    batch_number:    Optional[str]      = None
    next_due_date:   Optional[date]     = None
    notes:           Optional[str]      = None


@router.patch("/vitals/{vitals_id}")
async def update_vitals(
    vitals_id: str,
    data: VitalsUpdate,
    current=Depends(get_current_doctor),
):
    row_res = (
        supabase.table("patient_vitals")
        .select("patient_id")
        .eq("id", vitals_id)
        .maybe_single()
        .execute()
    )
    if not row_res or not row_res.data:
        raise HTTPException(status_code=404, detail="Vitals record not found")

    patient_id = row_res.data["patient_id"]
    _assert_access(patient_id, current["user"])

    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    if "notes" in payload:
        payload["notes"] = encrypt_text(payload["notes"])
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")

    payload["updated_at"] = datetime.now(timezone.utc).isoformat()

    res = (
        supabase.table("patient_vitals")
        .update(payload)
        .eq("id", vitals_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Vitals record not found")
    result = res.data[0]
    result["notes"] = decrypt_text(result.get("notes"))
    return result


@router.patch("/{patient_id}/allergies/{allergy_id}/edit")
async def edit_allergy(
    patient_id: str,
    allergy_id: str,
    data: AllergyUpdate,
    current_user=Depends(get_current_user),
):
    _assert_access(patient_id, current_user)

    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    if "allergen" in payload:
        payload["allergen"] = encrypt_text(payload["allergen"])
    if "reaction" in payload:
        payload["reaction"] = encrypt_text(payload["reaction"])
    if "notes" in payload:
        payload["notes"] = encrypt_text(payload["notes"])
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")

    res = (
        supabase.table("patient_allergies")
        .update(payload)
        .eq("id", allergy_id)
        .eq("patient_id", patient_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Allergy not found")
    result = res.data[0]
    result["allergen"] = decrypt_text(result.get("allergen"))
    result["reaction"] = decrypt_text(result.get("reaction"))
    result["notes"] = decrypt_text(result.get("notes"))
    return result


@router.patch("/{patient_id}/conditions/{condition_id}/edit")
async def edit_condition(
    patient_id:   str,
    condition_id: str,
    data: ConditionUpdate,
    current=Depends(get_current_doctor),
):
    _assert_access(patient_id, current["user"])

    if data.status and data.status not in ["active", "managed", "resolved"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    if data.diagnosed_date:
        payload["diagnosed_date"] = data.diagnosed_date.isoformat()
    if "condition_name" in payload:
        payload["condition_name"] = encrypt_text(payload["condition_name"])
    if "icd_code" in payload:
        payload["icd_code"] = encrypt_text(payload["icd_code"])
    if "notes" in payload:
        payload["notes"] = encrypt_text(payload["notes"])
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")

    res = (
        supabase.table("patient_conditions")
        .update(payload)
        .eq("id", condition_id)
        .eq("patient_id", patient_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Condition not found")
    result = res.data[0]
    result["condition_name"] = decrypt_text(result.get("condition_name"))
    result["icd_code"] = decrypt_text(result.get("icd_code"))
    result["notes"] = decrypt_text(result.get("notes"))
    return result


@router.patch("/history/{entry_id}")
async def update_history_entry(
    entry_id: str,
    data: HistoryUpdate,
    current=Depends(get_current_doctor),
):
    row_res = (
        supabase.table("medical_history_entries")
        .select("patient_id, doctor_id")
        .eq("id", entry_id)
        .maybe_single()
        .execute()
    )
    if not row_res or not row_res.data:
        raise HTTPException(status_code=404, detail="History entry not found")

    row = row_res.data
    _assert_access(row["patient_id"], current["user"])

    if row["doctor_id"] != current["doctor"]["id"]:
        raise HTTPException(
            status_code=403,
            detail="You can only edit history entries you created",
        )

    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    # Encrypt sensitive text fields
    for field in ["chief_complaint", "history_of_illness", "examination_notes", "diagnosis", "icd_code", "treatment_plan"]:
        if field in payload:
            payload[field] = encrypt_text(payload[field])
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")

    payload["updated_at"] = datetime.now(timezone.utc).isoformat()

    res = (
        supabase.table("medical_history_entries")
        .update(payload)
        .eq("id", entry_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="History entry not found")
    result = res.data[0]
    for field in ["chief_complaint", "history_of_illness", "examination_notes", "diagnosis", "icd_code", "treatment_plan"]:
        result[field] = decrypt_text(result.get(field))
    return result


@router.patch("/{patient_id}/family-history/{entry_id}")
async def update_family_history(
    patient_id: str,
    entry_id:   str,
    data: FamilyHistoryUpdate,
    current_user=Depends(get_current_user),
):
    _assert_access(patient_id, current_user)

    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    if "relation" in payload:
        payload["relation"] = encrypt_text(payload["relation"])
    if "condition" in payload:
        payload["condition"] = encrypt_text(payload["condition"])
    if "notes" in payload:
        payload["notes"] = encrypt_text(payload["notes"])
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")

    res = (
        supabase.table("patient_family_history")
        .update(payload)
        .eq("id", entry_id)
        .eq("patient_id", patient_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Family history entry not found")
    result = res.data[0]
    result["relation"] = decrypt_text(result.get("relation"))
    result["condition"] = decrypt_text(result.get("condition"))
    result["notes"] = decrypt_text(result.get("notes"))
    return result


@router.patch("/immunisations/{imm_id}")
async def update_immunisation(
    imm_id: str,
    data: ImmunisationUpdate,
    current_user=Depends(get_current_user),
):
    if current_user["role"] == "patient":
        raise HTTPException(status_code=403, detail="Only staff can edit immunisations")

    row_res = (
        supabase.table("patient_immunisations")
        .select("patient_id")
        .eq("id", imm_id)
        .maybe_single()
        .execute()
    )
    if not row_res or not row_res.data:
        raise HTTPException(status_code=404, detail="Immunisation record not found")

    patient_id = row_res.data["patient_id"]
    _assert_access(patient_id, current_user)

    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    if "vaccine_name" in payload:
        payload["vaccine_name"] = encrypt_text(payload["vaccine_name"])
    if "batch_number" in payload:
        payload["batch_number"] = encrypt_text(payload["batch_number"])
    if "notes" in payload:
        payload["notes"] = encrypt_text(payload["notes"])
    if data.administered_at:
        payload["administered_at"] = data.administered_at.isoformat()
    if data.next_due_date:
        payload["next_due_date"] = data.next_due_date.isoformat()
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")

    res = (
        supabase.table("patient_immunisations")
        .update(payload)
        .eq("id", imm_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Immunisation record not found")
    result = res.data[0]
    result["vaccine_name"] = decrypt_text(result.get("vaccine_name"))
    result["batch_number"] = decrypt_text(result.get("batch_number"))
    result["notes"] = decrypt_text(result.get("notes"))
    return result