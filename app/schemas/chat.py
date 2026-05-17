from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID
from app.models.enums import MessageType

class ChatMessageCreate(BaseModel):
    message: Optional[str] = None
    message_type: MessageType = MessageType.text
    file_url: Optional[str] = None

class ChatMessageResponse(BaseModel):
    id: UUID
    consultation_id: UUID
    sender_id: UUID
    message: Optional[str]
    message_type: MessageType
    file_url: Optional[str]
    seen: bool
    created_at: datetime