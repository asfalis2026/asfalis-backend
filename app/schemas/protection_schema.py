"""Pydantic schemas for the protection / Auto-SOS endpoints."""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


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
    """Request body for the /predict endpoint.

    ``window`` must be a list of [x, y, z] triplets, e.g.:
        [[0.1, -0.2, 9.8], [0.3, -0.1, 9.7], ...]
    """
    window: List[List[float]] = Field(..., min_length=3)
    sensor_type: Literal['accelerometer', 'gyroscope'] = 'accelerometer'
    location: str = 'Unknown'
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator('window')
    @classmethod
    def validate_window_shape(cls, v):
        for i, reading in enumerate(v):
            if len(reading) != 3:
                raise ValueError(
                    f"window[{i}] must have exactly 3 values [x, y, z], "
                    f"got {len(reading)}: {reading}"
                )
        return v




