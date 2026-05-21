from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional, List
from uuid import UUID

class PrescriptionItemCreate(BaseModel):
    medicine_name: str
    dosage: Optional[str] = None        
    frequency: Optional[str] = None       
    duration_days: Optional[int] = None
    instructions: Optional[str] = None

class PrescriptionCreate(BaseModel):
    consultation_id: UUID
    patient_id: UUID
    diagnosis: Optional[str] = None
    notes: Optional[str] = None
    follow_up_date: Optional[date] = None
    items: List[PrescriptionItemCreate]

class PrescriptionItemResponse(BaseModel):
    id: UUID
    medicine_name: str
    dosage: Optional[str]
    frequency: Optional[str]
    duration_days: Optional[int]
    instructions: Optional[str]

class PrescriptionResponse(BaseModel):
    id: UUID
    consultation_id: UUID
    patient_id: UUID
    doctor_id: int
    diagnosis: Optional[str]
    notes: Optional[str]
    follow_up_date: Optional[date]
    issued_at: datetime
    items: List[PrescriptionItemResponse]
    
class PrescriptionItemInput(BaseModel):
    medicine_name: str
    dosage:        Optional[str] = None
    frequency:     Optional[str] = None
    duration_days: Optional[int] = None
    instructions:  Optional[str] = None

class DirectPrescriptionCreate(BaseModel):
    patient_id:     str
    diagnosis:      str
    notes:          Optional[str] = None
    follow_up_date: Optional[date] = None
    items:          List[PrescriptionItemInput] = []
