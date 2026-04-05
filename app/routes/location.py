"""Location routes — converted to FastAPI."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.services.location_service import update_location, get_last_location, start_sharing, stop_sharing
from app.dependencies import get_current_user

router = APIRouter()


class LocationUpdateRequest(BaseModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    is_sharing: bool = False


@router.post("/update")
def update(data: LocationUpdateRequest, user_id: str = Depends(get_current_user)):
    update_location(user_id, data.latitude, data.longitude, data.is_sharing, data.accuracy)
    return {"success": True, "message": "Location updated."}


@router.get("/current")
def get_current(user_id: str = Depends(get_current_user)):
    location = get_last_location(user_id)
    if not location:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "No location history."})
    return {"success": True, "data": location.to_dict()}


@router.post("/share/start")
def start_sharing_route(user_id: str = Depends(get_current_user)):
    contacts = start_sharing(user_id)
    tracking_session_id = str(uuid.uuid4())
    return {"success": True, "data": {
        "sharing_session_id": tracking_session_id,
        "shared_with": [c.to_dict() for c in contacts],
        "tracking_url": f"https://asfalis.app/track/{tracking_session_id}",
    }}


@router.post("/share/stop")
def stop_sharing_route(user_id: str = Depends(get_current_user)):
    stop_sharing(user_id)
    return {"success": True, "message": "Sharing stopped."}
