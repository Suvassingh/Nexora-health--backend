from datetime import date, datetime
from typing import Optional, List, Literal

from pydantic import BaseModel


class AllergyCreate(BaseModel):
    allergen:  str
    reaction:  Optional[str] = None
    severity:  str = "moderate"
    notes:     Optional[str] = None

class ConditionCreate(BaseModel):
    condition_name: str
    icd_code:       Optional[str] = None
    diagnosed_date: Optional[date] = None
    status:         str = "active"
    notes:          Optional[str] = None

class VitalsCreate(BaseModel):
    patient_id:     str
    appointment_id: Optional[str] = None
    bp_systolic:    Optional[int] = None
    bp_diastolic:   Optional[int] = None
    heart_rate:     Optional[int] = None
    spo2:           Optional[int] = None
    temperature_c:  Optional[float] = None
    weight_kg:      Optional[float] = None
    height_cm:      Optional[float] = None
    notes:          Optional[str] = None

class HistoryEntryCreate(BaseModel):
    patient_id:          str
    consultation_id:     Optional[str] = None
    appointment_id:      Optional[str] = None
    chief_complaint:     Optional[str] = None
    history_of_illness:  Optional[str] = None
    examination_notes:   Optional[str] = None
    diagnosis:           str
    icd_code:            Optional[str] = None
    treatment_plan:      Optional[str] = None
    follow_up_days:      Optional[int] = None
    consultation_type: Optional[Literal['in_person', 'video', 'chat', 'audio']] = None


class FamilyHistoryCreate(BaseModel):
    relation:  str
    condition: str
    notes:     Optional[str] = None

class ImmunisationCreate(BaseModel):
    patient_id:      str
    vaccine_name:    str
    dose_number:     int = 1
    administered_at: Optional[datetime] = None
    batch_number:    Optional[str] = None
    next_due_date:   Optional[date] = None
    notes:           Optional[str] = None