from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from app.schemas.chat import ChatMessageCreate, ChatMessageResponse
from app.core.dependencies import get_current_user
from app.database.supabase_client import supabase
from typing import Dict, List
import json

router = APIRouter()

chat_rooms: Dict[str, List[dict]] = {}

# Get all messages for a consultation
@router.get("/{consultation_id}/messages")
async def get_messages(consultation_id: str, current_user=Depends(get_current_user)):
    result = supabase.table("chat_messages") \
        .select("*, user_profiles!sender_id(full_name, avatar_url)") \
        .eq("consultation_id", consultation_id) \
        .order("created_at") \
        .execute()
    return result.data


# Send message (REST fallback)
@router.post("/{consultation_id}/send")
async def send_message(
    consultation_id: str,
    data: ChatMessageCreate,
    current_user=Depends(get_current_user)
):
    message = {
        "consultation_id": consultation_id,
        "sender_id": current_user["id"],
        "message": data.message,
        "message_type": data.message_type,
        "file_url": data.file_url,
        "seen": False,
    }
    result = supabase.table("chat_messages").insert(message).execute()
    return result.data[0]


# Mark messages as seen
@router.patch("/{consultation_id}/seen")
async def mark_seen(consultation_id: str, current_user=Depends(get_current_user)):
    supabase.table("chat_messages").update({"seen": True}) \
        .eq("consultation_id", consultation_id) \
        .neq("sender_id", current_user["id"]) \
        .execute()
    return {"message": "Marked as seen"}


# WebSocket real-time chat
@router.websocket("/ws/{consultation_id}/{user_id}")
async def chat_ws(websocket: WebSocket, consultation_id: str, user_id: str):
    await websocket.accept()

    if consultation_id not in chat_rooms:
        chat_rooms[consultation_id] = []
    chat_rooms[consultation_id].append({"user_id": user_id, "ws": websocket})

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # save to supabase
            saved = supabase.table("chat_messages").insert({
                "consultation_id": consultation_id,
                "sender_id": user_id,
                "message": message.get("message"),
                "message_type": message.get("message_type", "text"),
                "file_url": message.get("file_url"),
                "seen": False,
            }).execute()

            # broadcast to others
            payload = {**saved.data[0], "from": user_id}
            for peer in chat_rooms[consultation_id]:
                if peer["ws"] != websocket:
                    await peer["ws"].send_json(payload)

    except WebSocketDisconnect:
        chat_rooms[consultation_id] = [
            p for p in chat_rooms[consultation_id] if p["ws"] != websocket
        ]