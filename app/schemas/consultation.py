from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID
from app.models.enums import ConsultationStatus

class ConsultationResponse(BaseModel):
    id: UUID
    appointment_id: UUID
    room_id: str
    status: ConsultationStatus
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime