"""Settings routes — converted to FastAPI."""

from fastapi import APIRouter, Depends, HTTPException
from app.extensions import db
from app.models.settings import UserSettings
from app.schemas.settings_schema import SettingsUpdateRequest
from app.dependencies import get_current_user

router = APIRouter()


@router.get("")
def get_settings(user_id: str = Depends(get_current_user)):
    settings_obj = UserSettings.query.filter_by(user_id=user_id).first()
    if not settings_obj:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Settings not found."})
    return {"success": True, "data": settings_obj.to_dict()}


@router.put("")
def update_settings(data: SettingsUpdateRequest, user_id: str = Depends(get_current_user)):
    settings_obj = UserSettings.query.filter_by(user_id=user_id).first()
    if not settings_obj:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Settings not found."})

    update = data.model_dump(exclude_none=True)
    for field in ('emergency_number', 'sos_message', 'shake_sensitivity', 'battery_optimization', 'haptic_feedback'):
        if field in update:
            setattr(settings_obj, field, update[field])

    if 'auto_sos_enabled' in update:
        settings_obj.auto_sos_enabled = update['auto_sos_enabled']
        from app.services.protection_service import active_protection_users
        if update['auto_sos_enabled']:
            active_protection_users[user_id] = True
        else:
            active_protection_users.pop(user_id, None)

    db.session.commit()
    return {"success": True, "data": settings_obj.to_dict()}
