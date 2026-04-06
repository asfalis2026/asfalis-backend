"""
sensor_data.py — Window-level sensor training data model.

Each row represents a single 300-reading window reduced to 39 statistical
features, matching the schema of labeled_windows.csv produced by the ML
data pipeline.  This replaces the previous per-reading schema.

Schema columns (39 features + metadata):
  Per-axis (x, y, z): mean, std, min, max, range, median, iqr, rms  → 24
  Magnitude (mag):    mean, std, min, max, range, median, iqr, rms  →  8
  Cross-correlations: xy_corr, xz_corr, yz_corr                    →  3
  ─────────────────────────────────────────────────────────────────
  Total feature columns:                                              39
"""

from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from datetime import datetime
import uuid

from app.database import Base


class SensorTrainingData(Base):
    __tablename__ = 'sensor_training_data'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)

    # Optional metadata (mirrors labeled_windows.csv columns)
    dataset_name = Column(String(100), nullable=True)        # e.g. 'fast_walking', 'highheight_free_fall'
    motion_description = Column(Text, nullable=True)         # e.g. 'DANGER — Highheight Free Fall'

    # Ground-truth label: 0 = SAFE, 1 = DANGER
    danger_label = Column(Integer, nullable=False)

    # ── X-axis statistical features ─────────────────────────────────────────
    x_mean   = Column(Float, nullable=False)
    x_std    = Column(Float, nullable=False)
    x_min    = Column(Float, nullable=False)
    x_max    = Column(Float, nullable=False)
    x_range  = Column(Float, nullable=False)
    x_median = Column(Float, nullable=False)
    x_iqr    = Column(Float, nullable=False)
    x_rms    = Column(Float, nullable=False)

    # ── Y-axis statistical features ─────────────────────────────────────────
    y_mean   = Column(Float, nullable=False)
    y_std    = Column(Float, nullable=False)
    y_min    = Column(Float, nullable=False)
    y_max    = Column(Float, nullable=False)
    y_range  = Column(Float, nullable=False)
    y_median = Column(Float, nullable=False)
    y_iqr    = Column(Float, nullable=False)
    y_rms    = Column(Float, nullable=False)

    # ── Z-axis statistical features ─────────────────────────────────────────
    z_mean   = Column(Float, nullable=False)
    z_std    = Column(Float, nullable=False)
    z_min    = Column(Float, nullable=False)
    z_max    = Column(Float, nullable=False)
    z_range  = Column(Float, nullable=False)
    z_median = Column(Float, nullable=False)
    z_iqr    = Column(Float, nullable=False)
    z_rms    = Column(Float, nullable=False)

    # ── Magnitude statistical features ───────────────────────────────────────
    mag_mean   = Column(Float, nullable=False)
    mag_std    = Column(Float, nullable=False)
    mag_min    = Column(Float, nullable=False)
    mag_max    = Column(Float, nullable=False)
    mag_range  = Column(Float, nullable=False)
    mag_median = Column(Float, nullable=False)
    mag_iqr    = Column(Float, nullable=False)
    mag_rms    = Column(Float, nullable=False)

    # ── Cross-axis correlations ──────────────────────────────────────────────
    xy_corr = Column(Float, nullable=False)
    xz_corr = Column(Float, nullable=False)
    yz_corr = Column(Float, nullable=False)

    # ── Bookkeeping ──────────────────────────────────────────────────────────
    # Links this window back to the SOSAlert that generated it (auto-SOS only).
    # NULL for manually collected calibration data.
    sos_alert_id = Column(String(36), ForeignKey('sos_alerts.id'), nullable=True)

    # True once the user has confirmed the label (via /sos/feedback or /collect).
    is_verified = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id':                self.id,
            'user_id':           self.user_id,
            'dataset_name':      self.dataset_name,
            'motion_description': self.motion_description,
            'danger_label':      self.danger_label,
            # X
            'x_mean':   self.x_mean,  'x_std':    self.x_std,
            'x_min':    self.x_min,   'x_max':    self.x_max,
            'x_range':  self.x_range, 'x_median': self.x_median,
            'x_iqr':    self.x_iqr,   'x_rms':    self.x_rms,
            # Y
            'y_mean':   self.y_mean,  'y_std':    self.y_std,
            'y_min':    self.y_min,   'y_max':    self.y_max,
            'y_range':  self.y_range, 'y_median': self.y_median,
            'y_iqr':    self.y_iqr,   'y_rms':    self.y_rms,
            # Z
            'z_mean':   self.z_mean,  'z_std':    self.z_std,
            'z_min':    self.z_min,   'z_max':    self.z_max,
            'z_range':  self.z_range, 'z_median': self.z_median,
            'z_iqr':    self.z_iqr,   'z_rms':    self.z_rms,
            # Magnitude
            'mag_mean':   self.mag_mean,  'mag_std':    self.mag_std,
            'mag_min':    self.mag_min,   'mag_max':    self.mag_max,
            'mag_range':  self.mag_range, 'mag_median': self.mag_median,
            'mag_iqr':    self.mag_iqr,   'mag_rms':    self.mag_rms,
            # Correlations
            'xy_corr': self.xy_corr,
            'xz_corr': self.xz_corr,
            'yz_corr': self.yz_corr,
            # Metadata
            'sos_alert_id': self.sos_alert_id,
            'is_verified':  self.is_verified,
            'created_at':   self.created_at.isoformat() if self.created_at else None,
        }

    def to_feature_vector(self):
        """Return the 39 features as a flat list (same column order as labeled_windows.csv)."""
        return [
            self.x_mean,   self.x_std,   self.x_min,   self.x_max,
            self.x_range,  self.x_median, self.x_iqr,  self.x_rms,
            self.y_mean,   self.y_std,   self.y_min,   self.y_max,
            self.y_range,  self.y_median, self.y_iqr,  self.y_rms,
            self.z_mean,   self.z_std,   self.z_min,   self.z_max,
            self.z_range,  self.z_median, self.z_iqr,  self.z_rms,
            self.mag_mean, self.mag_std, self.mag_min, self.mag_max,
            self.mag_range, self.mag_median, self.mag_iqr, self.mag_rms,
            self.xy_corr,  self.xz_corr, self.yz_corr,
        ]
