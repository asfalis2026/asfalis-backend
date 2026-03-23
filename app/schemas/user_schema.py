"""Pydantic schemas for the user profile endpoints."""

from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    sos_message: Optional[str] = Field(None, min_length=1, max_length=500)
    profile_image_url: Optional[str] = None


class FCMTokenRequest(BaseModel):
    fcm_token: str
