"""User profile routes — converted to FastAPI."""

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.extensions import db
from app.models.user import User
from app.models.trusted_contact import TrustedContact
from app.schemas.user_schema import UpdateProfileRequest, FCMTokenRequest
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/security-policy")
def get_security_policy(user_id: str = Depends(get_current_user)):
    return {"success": True, "data": {
        "screenshot_protection": {
            "enabled": True,
            "protected_screens": ["trusted_contacts", "sos_history"]
        }
    }}


@router.get("/profile")
def get_profile(user_id: str = Depends(get_current_user)):
    user = db.session.get(User, user_id)
    if not user:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "User not found."})

    try:
        contacts = TrustedContact.query.filter_by(user_id=user_id).all()
        return {"success": True, "data": {
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "country": user.country,
            "phone": user.phone,
            "sos_message": user.sos_message,
            "profile_image_url": user.profile_image_url,
            "emergency_contact": user.settings.emergency_number if user.settings else None,
            "trusted_contacts": [c.to_dict() for c in contacts],
            "trusted_contacts_count": len(contacts),
            "member_since": user.created_at.strftime('%B %Y'),
            "is_protection_active": True,
            "auth_provider": user.auth_provider,
        }}
    except Exception as e:
        logger.error(f"Profile fetch failed for user {user_id}: {e}")
        db.session.rollback()
        raise HTTPException(500, detail={"code": "INTERNAL_ERROR", "message": "Failed to fetch profile."})


@router.put("/profile")
def update_profile(data: UpdateProfileRequest, user_id: str = Depends(get_current_user)):
    user = db.session.get(User, user_id)
    if not user:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "User not found."})

    update = data.model_dump(exclude_none=True)
    for field in ('full_name', 'phone', 'sos_message', 'profile_image_url'):
        if field in update:
            setattr(user, field, update[field])

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        err = str(e).lower()
        if "unique" in err or "duplicate" in err:
            raise HTTPException(409, detail={"code": "CONFLICT",
                                             "message": "Phone number already in use."})
        raise HTTPException(500, detail={"code": "INTERNAL_ERROR", "message": str(e)})

    return {"success": True, "message": "Profile updated successfully."}


@router.put("/fcm-token")
def update_fcm_token(data: FCMTokenRequest, user_id: str = Depends(get_current_user)):
    user = db.session.get(User, user_id)
    if not user:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "User not found."})
    user.fcm_token = data.fcm_token
    db.session.commit()
    return {"success": True, "message": "FCM token updated."}


@router.put("/sos-message")
def update_sos_message(body: dict, user_id: str = Depends(get_current_user)):
    sos_message = body.get('sos_message')
    if not sos_message or not sos_message.strip():
        raise HTTPException(400, detail={"code": "VALIDATION_ERROR",
                                         "message": "sos_message cannot be empty."})
    if len(sos_message) > 500:
        raise HTTPException(400, detail={"code": "VALIDATION_ERROR",
                                         "message": "SOS message too long (max 500 chars)."})

    user = db.session.get(User, user_id)
    if not user:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "User not found."})
    user.sos_message = sos_message.strip()
    db.session.commit()
    return {"success": True, "message": "SOS message updated.", "data": {"sos_message": user.sos_message}}


@router.delete("/account")
def delete_account(user_id: str = Depends(get_current_user)):
    user = db.session.get(User, user_id)
    if not user:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "User not found."})
    db.session.delete(user)
    db.session.commit()
    return {"success": True, "message": "Account deleted successfully."}


@router.delete("/{target_user_id}")
def delete_user_by_id(target_user_id: str, user_id: str = Depends(get_current_user)):
    user = db.session.get(User, target_user_id)
    if not user:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "User not found."})
    db.session.delete(user)
    db.session.commit()
    return {"success": True, "message": f"User {target_user_id} deleted."}
