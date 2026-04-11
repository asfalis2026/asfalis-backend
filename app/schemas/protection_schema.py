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
    """Request body for the /collect endpoint (raw window path).

    ``window`` is a list of raw sensor readings.  The backend extracts
    the 39 statistical features and stores one ``SensorTrainingData`` row.

    Optional metadata fields mirror ``labeled_windows.csv`` columns so
    manually labelled calibration data can be richly annotated.
    """
    window: List[SensorReading] = Field(..., min_length=10)
    label: Union[int, str]
    sensor_type: Optional[str] = 'accelerometer'
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


class FlatFeatureTrainingRequest(BaseModel):
    """Request body for the /collect endpoint (pre-extracted features path).

    The Android app extracts the 39 statistical features on-device from a
    300-reading window and sends them as a flat JSON object — matching the
    column schema of ``labeled_windows.csv`` exactly (no nesting required).

    Use this when the app has already computed the features and you want to
    skip server-side feature extraction.

    Example payload::

        {
          "sensor_type": "accelerometer",
          "label": 1,
          "x_mean": -0.46,  "x_std": 0.465,  "x_min": -1.2,  "x_max": 0.3,
          "x_range": 1.5,   "x_median": -0.45, "x_iqr": 0.6,  "x_rms": 0.67,
          ... (and the remaining 31 feature columns)
        }
    """
    # ── Metadata ──────────────────────────────────────────────────────────────
    sensor_type: Optional[str] = 'accelerometer'
    label: Union[int, str]
    dataset_name: Optional[str] = None
    motion_description: Optional[str] = None

    # ── X-axis (8 features) ───────────────────────────────────────────────────
    x_mean:   float
    x_std:    float
    x_min:    float
    x_max:    float
    x_range:  float
    x_median: float
    x_iqr:    float
    x_rms:    float

    # ── Y-axis (8 features) ───────────────────────────────────────────────────
    y_mean:   float
    y_std:    float
    y_min:    float
    y_max:    float
    y_range:  float
    y_median: float
    y_iqr:    float
    y_rms:    float

    # ── Z-axis (8 features) ───────────────────────────────────────────────────
    z_mean:   float
    z_std:    float
    z_min:    float
    z_max:    float
    z_range:  float
    z_median: float
    z_iqr:    float
    z_rms:    float

    # ── Magnitude (8 features) ────────────────────────────────────────────────
    mag_mean:   float
    mag_std:    float
    mag_min:    float
    mag_max:    float
    mag_range:  float
    mag_median: float
    mag_iqr:    float
    mag_rms:    float

    # ── Cross-axis correlations (3 features) ──────────────────────────────────
    xy_corr: float
    xz_corr: float
    yz_corr: float

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

    def to_named_features(self) -> dict:
        """Return the 39 features as a dict matching SensorTrainingData columns."""
        return {
            'x_mean': self.x_mean,     'x_std': self.x_std,       'x_min': self.x_min,
            'x_max': self.x_max,       'x_range': self.x_range,   'x_median': self.x_median,
            'x_iqr': self.x_iqr,       'x_rms': self.x_rms,
            'y_mean': self.y_mean,     'y_std': self.y_std,       'y_min': self.y_min,
            'y_max': self.y_max,       'y_range': self.y_range,   'y_median': self.y_median,
            'y_iqr': self.y_iqr,       'y_rms': self.y_rms,
            'z_mean': self.z_mean,     'z_std': self.z_std,       'z_min': self.z_min,
            'z_max': self.z_max,       'z_range': self.z_range,   'z_median': self.z_median,
            'z_iqr': self.z_iqr,       'z_rms': self.z_rms,
            'mag_mean': self.mag_mean, 'mag_std': self.mag_std,   'mag_min': self.mag_min,
            'mag_max': self.mag_max,   'mag_range': self.mag_range, 'mag_median': self.mag_median,
            'mag_iqr': self.mag_iqr,   'mag_rms': self.mag_rms,
            'xy_corr': self.xy_corr,   'xz_corr': self.xz_corr,  'yz_corr': self.yz_corr,
        }

