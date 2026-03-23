"""Pydantic schemas for contacts endpoints."""

import re
from typing import Optional
from pydantic import BaseModel, field_validator, EmailStr, Field

_E164_RE = re.compile(r'^\+[1-9]\d{6,14}$')


class ContactRequest(BaseModel):
    name: str = Field(..., min_length=2)
    phone: str
    email: Optional[str] = None
    relationship: Optional[str] = None
    is_primary: bool = False

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v and not _E164_RE.match(v):
            raise ValueError("Phone number must be in E.164 format (e.g. +919876543210).")
        return v
