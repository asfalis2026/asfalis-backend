"""Pydantic schemas for the protection / Auto-SOS endpoints."""

from typing import List, Optional, Literal, Union
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


class SensorTrainingRequest(BaseModel):
    """Request body for the /collect endpoint.

    ``window`` is a list of 300 raw sensor readings.  The backend extracts
    the 39 statistical features and stores one ``SensorTrainingData`` row.

    Optional metadata fields mirror ``labeled_windows.csv`` columns so
    manually labelled calibration data can be richly annotated.
    """
    window: List[SensorReading] = Field(..., min_length=10)
    label: Union[int, str]
    dataset_name: Optional[str] = None
    motion_description: Optional[str] = None

    @field_validator('label')
    @classmethod
    def normalize_label(cls, v):
        """Map descriptive strings to 0/1 integers for the ML model."""
        if isinstance(v, int):
            if v in [0, 1]:
                return v
            raise ValueError("Integer label must be 0 (Safe) or 1 (Danger).")
        
        s = str(v).lower().strip()
        if s in ['fall', 'danger', 'true_positive', 'alert', '1']:
            return 1
        if s in ['safe', 'normal', 'false_positive', 'ok', 'no_fall', '0']:
            return 0
            
        raise ValueError(f"Invalid label '{v}'. Use 0/1 or 'safe'/'fall'.")
