"""Pydantic schemas for authentication endpoints (replaces Marshmallow)."""

import re
from typing import Optional
from pydantic import BaseModel, field_validator, Field

E164_RE = re.compile(r'^\+[1-9]\d{6,14}$')

def _check_e164(v: str) -> str:
    if not E164_RE.match(v):
        raise ValueError("Phone number must be in E.164 format (e.g. +919876543210).")
    return v


class PhoneRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2)
    phone_number: str
    country: str
    password: str = Field(..., min_length=6)

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        return _check_e164(v)


class PhoneLoginRequest(BaseModel):
    phone_number: str
    password: str
    device_imei: Optional[str] = None
    confirm_handover: bool = False

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        return _check_e164(v)


class VerifyPhoneOTPRequest(BaseModel):
    phone_number: str
    otp_code: str = Field(..., min_length=6, max_length=6)

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        return _check_e164(v)


class ResendOTPRequest(BaseModel):
    phone_number: str

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        return _check_e164(v)


class ForgotPasswordRequest(BaseModel):
    phone_number: str

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        return _check_e164(v)


class ResetPasswordRequest(BaseModel):
    phone_number: str = Field(..., min_length=10)
    otp_code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=6)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class GoogleLoginRequest(BaseModel):
    id_token: str
