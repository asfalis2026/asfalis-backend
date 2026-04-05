"""
Auth routes — migrated from Flask to FastAPI.

Token strategy (unchanged):
  access_token  — 15 min, used on all protected endpoints
  refresh_token — 30 days, rotated on every /refresh; blocklisted on logout
  sos_token     — long-lived access token, stored by app for emergency use
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Request, HTTPException
from jose import jwt as jose_jwt

from app.config import settings
from app.extensions import db
from app.models.user import User
from app.models.settings import UserSettings
from app.models.revoked_token import RevokedToken
from app.models.device_security import UserDeviceBinding, HandsetChangeRequest
from app.schemas.auth_schema import (
    PhoneRegisterRequest, PhoneLoginRequest, VerifyPhoneOTPRequest,
    ResendOTPRequest, ForgotPasswordRequest, ResetPasswordRequest,
    RefreshTokenRequest, GoogleLoginRequest,
)
from app.dependencies import get_current_user, decode_token_lenient
from app.utils.validators import validate_password
from app.utils.otp import store_otp, verify_otp, generate_otp
from app.services.sms_service import send_otp_sms
from slowapi import Limiter
from slowapi.util import get_remote_address
import bcrypt

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# ─── Token helpers ──────────────────────────────────────────────────────────

def _make_tokens(user_id: str):
    now = datetime.now(timezone.utc)

    access_payload = {
        "sub": user_id, "type": "access", "jti": str(uuid.uuid4()),
        "iat": now, "exp": now + settings.JWT_ACCESS_TOKEN_EXPIRES,
    }
    access_token = jose_jwt.encode(access_payload, settings.JWT_SECRET_KEY, algorithm="HS256")

    refresh_payload = {
        "sub": user_id, "type": "refresh", "jti": str(uuid.uuid4()),
        "iat": now, "exp": now + settings.JWT_REFRESH_TOKEN_EXPIRES,
    }
    refresh_token = jose_jwt.encode(refresh_payload, settings.JWT_SECRET_KEY, algorithm="HS256")

    sos_payload = {
        "sub": user_id, "type": "access", "token_purpose": "sos",
        "jti": str(uuid.uuid4()), "iat": now,
        "exp": now + timedelta(days=settings.JWT_SOS_TOKEN_EXPIRES_DAYS),
    }
    sos_token = jose_jwt.encode(sos_payload, settings.JWT_SECRET_KEY, algorithm="HS256")

    expires_in = int(settings.JWT_ACCESS_TOKEN_EXPIRES.total_seconds())
    return access_token, refresh_token, sos_token, expires_in


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ─── Health / validate ──────────────────────────────────────────────────────

@router.get("/validate")
def validate_token(user_id: str = Depends(get_current_user)):
    return {"success": True, "user_id": user_id}


# ─── Registration ───────────────────────────────────────────────────────────

@router.post("/register/phone", status_code=201)
def register_phone(data: PhoneRegisterRequest):
    phone = data.phone_number

    if User.query.filter_by(phone=phone).first():
        raise HTTPException(400, detail={"code": "PHONE_TAKEN",
                                         "message": "Phone number already registered."})

    if not validate_password(data.password):
        raise HTTPException(400, detail={"code": "WEAK_PASSWORD",
                                         "message": "Password must be at least 6 chars and contain a digit."})

    new_user = User(
        full_name=data.full_name,
        phone=phone,
        country=data.country,
        password_hash=_hash_password(data.password),
        auth_provider='phone',
    )
    db.session.add(new_user)
    db.session.flush()  # get ID before commit

    # Default settings row
    db.session.add(UserSettings(user_id=new_user.id))

    # Generate and send OTP
    otp_code = generate_otp()
    try:
        store_otp(phone=phone, otp_code=otp_code, purpose='phone_verification')
    except Exception as e:
        db.session.rollback()
        raise HTTPException(500, detail={"code": "OTP_ERROR", "message": str(e)})

    db.session.commit()

    send_result = send_otp_sms(phone, otp_code)
    resp = {
        "status": "success",
        "message": "Registration started. Please verify your phone number.",
        "data": {"user_id": new_user.id}
    }
    if settings.DEBUG or send_result == "mock-sid":
        resp["data"]["otp_code"] = otp_code
    return resp


@router.post("/register", status_code=201, include_in_schema=False)
def register_alias_simple(data: PhoneRegisterRequest):
    """Alias for /register/phone."""
    return register_phone(data)


# ─── Phone OTP verification ─────────────────────────────────────────────────

@router.post("/verify-phone-otp")
def verify_phone_otp(data: VerifyPhoneOTPRequest):
    ok, msg = verify_otp(phone=data.phone_number, otp_code=data.otp_code, purpose='phone_verification')
    if not ok:
        raise HTTPException(400, detail={"code": "OTP_INVALID", "message": msg})

    user = User.query.filter_by(phone=data.phone_number).first()
    if not user:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "User not found."})

    user.is_verified = True
    db.session.commit()

    access_token, refresh_token, sos_token, expires_in = _make_tokens(user.id)
    return {
        "success": True,
        "message": "Phone verified successfully.",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "sos_token": sos_token,
            "expires_in": expires_in,
            "user_id": user.id,
            "full_name": user.full_name,
        }
    }


# ─── Resend OTP ─────────────────────────────────────────────────────────────

@router.post("/resend-otp")
def resend_otp(request: Request, data: ResendOTPRequest):
    user = User.query.filter_by(phone=data.phone_number).first()
    if not user:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "User not found."})

    otp_code = generate_otp()
    store_otp(phone=data.phone_number, otp_code=otp_code, purpose='phone_verification')
    send_otp_sms(data.phone_number, otp_code)

    resp = {"success": True, "message": "OTP resent."}
    if settings.DEBUG:
        resp["data"] = {"otp_code": otp_code}
    return resp


# ─── Login ───────────────────────────────────────────────────────────────────

@router.post("/login/phone")
def login_phone(request: Request, data: PhoneLoginRequest):
    user = User.query.filter_by(phone=data.phone_number).first()
    if not user:
        raise HTTPException(401, detail={"code": "INVALID_CREDENTIALS",
                                         "message": "Invalid phone number or password."})

    if not user.password_hash or not _check_password(data.password, user.password_hash):
        raise HTTPException(401, detail={"code": "INVALID_CREDENTIALS",
                                         "message": "Invalid phone number or password."})

    if not user.is_verified:
        raise HTTPException(403, detail={"code": "UNVERIFIED_PHONE",
                                         "message": "Please verify your phone number first."})

    # IMEI binding check
    if settings.IMEI_BINDING_ENABLED and data.device_imei:
        binding = UserDeviceBinding.query.filter_by(user_id=user.id).first()
        if not binding:
            binding = UserDeviceBinding(user_id=user.id, device_imei=data.device_imei)
            db.session.add(binding)
        elif binding.device_imei != data.device_imei:
            # Check for pending approved handset change
            pending = HandsetChangeRequest.query.filter_by(
                user_id=user.id, new_device_imei=data.device_imei, status='pending'
            ).order_by(HandsetChangeRequest.requested_at.desc()).first()

            if pending and pending.is_eligible:
                pending.status = 'completed'
                pending.completed_at = datetime.utcnow()
                binding.device_imei = data.device_imei
                binding.last_login_at = datetime.utcnow()
            elif pending and not pending.is_eligible:
                hours_left = (pending.eligible_at - datetime.utcnow()).total_seconds() / 3600
                raise HTTPException(403, detail={
                    "code": "HANDSET_TRANSFER_PENDING",
                    "message": f"Handset transfer approved. Available in {hours_left:.1f} hours.",
                    "hours_remaining": round(hours_left, 1)
                })
            elif data.confirm_handover:
                new_req = HandsetChangeRequest(
                    user_id=user.id,
                    old_device_imei=binding.device_imei,
                    new_device_imei=data.device_imei
                )
                db.session.add(new_req)
                db.session.commit()
                raise HTTPException(403, detail={
                    "code": "HANDSET_TRANSFER_INITIATED",
                    "message": "Handset transfer request submitted. Please try again in 12 hours.",
                    "eligible_at": new_req.eligible_at.isoformat()
                })
            else:
                raise HTTPException(403, detail={
                    "code": "DEVICE_MISMATCH",
                    "message": "This account is linked to a different device.",
                    "requires_handover_confirmation": True
                })
        binding.last_login_at = datetime.utcnow()
    db.session.commit()

    access_token, refresh_token, sos_token, expires_in = _make_tokens(user.id)
    return {
        "success": True,
        "message": "Login successful.",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "sos_token": sos_token,
            "expires_in": expires_in,
            "user_id": user.id,
            "full_name": user.full_name,
            "auth_provider": user.auth_provider,
        }
    }


@router.post("/login", include_in_schema=False)
def login_alias_simple(request: Request, data: PhoneLoginRequest):
    """Alias for /login/phone."""
    return login_phone(request, data)


# ─── Token refresh ───────────────────────────────────────────────────────────

@router.post("/refresh")
def refresh_token(data: RefreshTokenRequest):
    token_str = data.refresh_token
    try:
        payload = decode_token_lenient(token_str)
    except HTTPException:
        raise HTTPException(401, detail={"code": "REFRESH_TOKEN_INVALID",
                                         "message": "Invalid refresh token."})

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(401, detail={"code": "REFRESH_TOKEN_INVALID",
                                         "message": "Token missing JTI."})

    if RevokedToken.query.filter_by(jti=jti).first():
        raise HTTPException(401, detail={"code": "REFRESH_TOKEN_REUSED",
                                         "message": "Refresh token already used. Please log in again."})

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, detail={"code": "REFRESH_TOKEN_INVALID",
                                         "message": "Invalid refresh token."})

    # Revoke old token
    db.session.add(RevokedToken(jti=jti, token_type='refresh'))
    db.session.commit()

    access_token, refresh_token_new, sos_token, expires_in = _make_tokens(user_id)
    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token_new,
            "expires_in": expires_in
        }
    }


# ─── Logout ──────────────────────────────────────────────────────────────────

@router.post("/logout")
def logout(data: RefreshTokenRequest):
    try:
        payload = decode_token_lenient(data.refresh_token)
        jti = payload.get("jti")
        if jti and not RevokedToken.query.filter_by(jti=jti).first():
            db.session.add(RevokedToken(jti=jti, token_type='refresh'))
            db.session.commit()
    except Exception:
        pass
    return {"success": True, "message": "Logged out successfully."}


# ─── Forgot / Reset password ─────────────────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(request: Request, data: ForgotPasswordRequest):
    user = User.query.filter_by(phone=data.phone_number).first()
    if not user:
        raise HTTPException(404, detail={"code": "NOT_FOUND",
                                         "message": "No account with that phone number."})

    otp_code = generate_otp()
    store_otp(phone=data.phone_number, otp_code=otp_code, purpose='reset_password')
    send_otp_sms(data.phone_number, otp_code)

    resp = {"success": True, "message": "Password reset OTP sent."}
    if settings.DEBUG:
        resp["data"] = {"otp_code": otp_code}
    return resp


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest):
    ok, msg = verify_otp(phone=data.phone_number, otp_code=data.otp_code, purpose='reset_password')
    if not ok:
        raise HTTPException(400, detail={"code": "OTP_INVALID", "message": msg})

    if not validate_password(data.new_password):
        raise HTTPException(400, detail={"code": "WEAK_PASSWORD",
                                         "message": "Password must be at least 6 chars and contain a digit."})

    user = User.query.filter_by(phone=data.phone_number).first()
    if not user:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "User not found."})

    user.password_hash = _hash_password(data.new_password)
    db.session.commit()
    return {"success": True, "message": "Password reset successfully."}


# ─── Google OAuth (mocked) ────────────────────────────────────────────────────

@router.post("/google")
def google_login(data: GoogleLoginRequest):
    # TODO: verify id_token with Google SDK
    raise HTTPException(501, detail={"code": "NOT_IMPLEMENTED",
                                     "message": "Google OAuth not yet implemented."})
