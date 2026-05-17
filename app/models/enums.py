from enum import Enum

class ConsultationType(str, Enum):
    chat = "chat"
    audio = "audio"
    video = "video"

class AppointmentStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    ongoing = "ongoing"
    completed = "completed"
    cancelled = "cancelled"