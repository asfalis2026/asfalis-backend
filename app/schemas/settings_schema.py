"""Pydantic schemas for the settings endpoint."""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class SettingsUpdateRequest(BaseModel):
    emergency_number: Optional[str] = Field(None, min_length=3)
    sos_message: Optional[str] = Field(None, max_length=500)
    shake_sensitivity: Optional[Literal['low', 'medium', 'high']] = None
    battery_optimization: Optional[bool] = None
    haptic_feedback: Optional[bool] = None
    auto_sos_enabled: Optional[bool] = None
