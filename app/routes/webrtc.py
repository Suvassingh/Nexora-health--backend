from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List
import json

router = APIRouter()

rooms: Dict[str, List[dict]] = {}

@router.websocket("/ws/{room_id}/{user_id}")
async def webrtc_signaling(websocket: WebSocket, room_id: str, user_id: str):
    await websocket.accept()

    if room_id not in rooms:
        rooms[room_id] = []

    rooms[room_id].append({"user_id": user_id, "ws": websocket})

    # notify others that someone joined
    await broadcast(room_id, {"type": "user-joined", "user_id": user_id}, exclude=websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            message["from"] = user_id

            # broadcast signal to all peers in room except sender
            await broadcast(room_id, message, exclude=websocket)

    except WebSocketDisconnect:
        rooms[room_id] = [p for p in rooms[room_id] if p["ws"] != websocket]
        await broadcast(room_id, {"type": "user-left", "user_id": user_id}, exclude=None)
        if not rooms[room_id]:
            del rooms[room_id]


async def broadcast(room_id: str, message: dict, exclude: WebSocket):
    if room_id not in rooms:
        return
    for peer in rooms[room_id]:
        if peer["ws"] != exclude:
            try:
                await peer["ws"].send_json(message)
            except Exception:
                pass