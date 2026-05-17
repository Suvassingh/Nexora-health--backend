
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.database.supabase_client import supabase

router = APIRouter(prefix="/calls", tags=["calls"])


class InitiateCallRequest(BaseModel):
    callee_id: str
    appointment_id: Optional[str] = None
    call_type: str


class UpdateStatusRequest(BaseModel):
    status: str


@router.post("/initiate")
async def initiate_call(
    req: InitiateCallRequest,
    current_user=Depends(get_current_user),
):
    caller_id = current_user["id"]

    if req.call_type not in ("audio", "video"):
        raise HTTPException(status_code=400, detail="call_type must be 'audio' or 'video'")

    # Verify callee exists
    callee = (
        supabase.from_("user_profiles")
        .select("id, full_name")
        .eq("id", req.callee_id)
        .execute()
    )
    if not callee.data:
        raise HTTPException(status_code=404, detail="Callee not found")

    # Get caller name
    caller = (
        supabase.from_("user_profiles")
        .select("full_name")
        .eq("id", caller_id)
        .execute()
    )
    caller_name = caller.data[0].get("full_name", "Unknown") if caller.data else "Unknown"

    # Build insert payload
    payload: dict = {
        "caller_id": caller_id,
        "callee_id": req.callee_id,
        "call_type": req.call_type,
        "status":    "ringing",
    }
    if req.appointment_id:
        payload["appointment_id"] = req.appointment_id

    # Insert call row
    supabase.from_("calls").insert(payload).execute()

    # Fetch the newly created call id
    result = (
        supabase.from_("calls")
        .select("id")
        .eq("caller_id", caller_id)
        .eq("callee_id", req.callee_id)
        .eq("status", "ringing")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create call")

    call_id = result.data[0]["id"]

    return {
        "call_id":     call_id,
        "caller_name": caller_name,
        "status":      "ringing",
    }


@router.patch("/{call_id}/status")
async def update_call_status(
    call_id: str,
    req: UpdateStatusRequest,
    current_user=Depends(get_current_user),
):
    valid = {"accepted", "declined", "ended", "missed"}
    if req.status not in valid:
        raise HTTPException(status_code=400, detail=f"status must be one of {valid}")

    update: dict = {"status": req.status}
    if req.status in ("ended", "declined", "missed"):
        update["ended_at"] = datetime.now(timezone.utc).isoformat()

    supabase.from_("calls").update(update).eq("id", call_id).execute()

    return {"call_id": call_id, "status": req.status}


@router.get("/history")
async def list_my_calls(
    current_user=Depends(get_current_user),
):
    uid = current_user["id"]

    # Fetch as caller
    as_caller = (
        supabase.from_("calls")
        .select("*")
        .eq("caller_id", uid)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )

    # Fetch as callee
    as_callee = (
        supabase.from_("calls")
        .select("*")
        .eq("callee_id", uid)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )

    # Merge and sort
    all_calls = (as_caller.data or []) + (as_callee.data or [])
    all_calls.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return all_calls[:50]


@router.get("/{call_id}")
async def get_call(
    call_id: str,
    current_user=Depends(get_current_user),
):
    result = (
        supabase.from_("calls")
        .select("*")
        .eq("id", call_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Call not found")
    return result.data[0]