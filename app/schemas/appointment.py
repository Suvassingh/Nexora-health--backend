from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional
from uuid import UUID
from app.models.enums import ConsultationType, AppointmentStatus


class AppointmentCreate(BaseModel):
    doctor_id: int                         
    consultation_type: ConsultationType
    scheduled_at: datetime                 
    duration_minutes: int = 30
    patient_notes: Optional[str] = None    

    @field_validator("scheduled_at", mode="before")
    @classmethod
    def parse_scheduled_at(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


class AppointmentResponse(BaseModel):
    id: str
    patient_id: str
    doctor_id: int
    consultation_type: ConsultationType
    status: AppointmentStatus
    scheduled_at: datetime
    duration_minutes: int
    patient_notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus


class SlotCheckRequest(BaseModel):
    doctor_id: int
    date: str   