"""Pydantic schemas for the protection / Auto-SOS endpoints."""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class ToggleProtectionRequest(BaseModel):
    is_active: bool


class SensorReading(BaseModel):
    x: float
    y: float
    z: float
    timestamp: int


class SensorDataRequest(BaseModel):
    sensor_type: Literal['accelerometer', 'gyroscope']
    data: List[SensorReading]
    sensitivity: str = 'medium'


class SensorWindowRequest(BaseModel):
    """Request body for the /predict endpoint."""
    window: List[List[float]] = Field(..., min_length=3)
    sensor_type: Literal['accelerometer', 'gyroscope'] = 'accelerometer'
    location: str = 'Unknown'
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SensorTrainingRequest(BaseModel):
    sensor_type: Literal['accelerometer', 'gyroscope']
    data: List[SensorReading]
    label: Literal[0, 1]
