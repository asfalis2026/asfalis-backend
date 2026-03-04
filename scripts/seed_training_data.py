"""Seed synthetic training data and retrain the ML model.

Run this once when the sensor_training_data table is empty:

    # Inside the container
    docker-compose exec web python scripts/seed_training_data.py

    # Or locally (with venv activated)
    python scripts/seed_training_data.py

The script generates realistic synthetic accelerometer and gyroscope readings
for two classes:

    0 — Safe  (normal walking, standing, sitting, gentle rotation)
    1 — Danger (falls, violent shaking, rapid uncontrolled rotation)

After seeding it immediately runs train_model.py so the new 17-feature model
is saved to the DB and picked up by the live inference path.
"""

import os
import sys
import uuid
import time
import numpy as np

# ── project root on path ────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.sensor_data import SensorTrainingData
from app.models.user import User

# ── tuneable constants ───────────────────────────────────────────────────────
WINDOW_SIZE   = 40          # readings per window (must match train_model.py)
SAFE_WINDOWS  = 120         # windows of class-0 data per sensor type
DANGER_WINDOWS = 120        # windows of class-1 data per sensor type
RNG_SEED      = 42

rng = np.random.default_rng(RNG_SEED)


# ── synthetic signal generators ──────────────────────────────────────────────

def _accel_safe(n: int) -> np.ndarray:
    """Normal activity: gravity on z, small movement noise on all axes.

    Simulates standing / slow walking.  Magnitude ≈ 9.5–10.5 m/s².
    """
    x = rng.normal(0.0,  0.25, n)
    y = rng.normal(0.0,  0.25, n)
    z = rng.normal(-9.81, 0.30, n)
    return np.column_stack([x, y, z])


def _accel_walking(n: int) -> np.ndarray:
    """Brisk walking: periodic heel-strike impulses.  Magnitude ≈ 10–14 m/s²."""
    t = np.linspace(0, 2 * np.pi, n)
    x = 0.8 * np.sin(2 * t) + rng.normal(0, 0.15, n)
    y = 0.5 * np.cos(2 * t) + rng.normal(0, 0.15, n)
    z = -9.81 + 0.6 * np.sin(4 * t) + rng.normal(0, 0.20, n)
    return np.column_stack([x, y, z])


def _accel_danger_fall(n: int) -> np.ndarray:
    """Simulated fall: free-fall → impact spike → rest.

    Phase 1 (first 30 %):  near-zero g (free-fall / weightlessness)
    Phase 2 (next 20 %):   massive impact spike (25–45 m/s²)
    Phase 3 (last 50 %):   lying still, noisy
    """
    data = np.zeros((n, 3))
    p1 = int(n * 0.30)
    p2 = int(n * 0.20)

    # Free-fall
    data[:p1, 0] = rng.normal(0, 0.3, p1)
    data[:p1, 1] = rng.normal(0, 0.3, p1)
    data[:p1, 2] = rng.normal(0, 0.3, p1)

    # Impact spike
    data[p1:p1+p2, 0] = rng.uniform(-20, 20, p2)
    data[p1:p1+p2, 1] = rng.uniform(-15, 15, p2)
    data[p1:p1+p2, 2] = rng.uniform(-40, -25, p2)

    # Post-fall rest
    rest = n - p1 - p2
    data[p1+p2:, 0] = rng.normal(0.2,  0.4, rest)
    data[p1+p2:, 1] = rng.normal(0.1,  0.4, rest)
    data[p1+p2:, 2] = rng.normal(-9.5, 0.5, rest)
    return data


def _accel_danger_shake(n: int) -> np.ndarray:
    """Violent shaking: high-frequency, high-amplitude oscillations.

    Magnitude regularly exceeds 20 m/s².
    """
    t = np.linspace(0, 4 * np.pi, n)
    x = rng.uniform(8, 15) * np.sin(rng.uniform(3, 7) * t) + rng.normal(0, 1, n)
    y = rng.uniform(8, 15) * np.cos(rng.uniform(3, 7) * t) + rng.normal(0, 1, n)
    z = rng.uniform(5, 12) * np.sin(rng.uniform(3, 7) * t) + rng.normal(0, 1, n)
    return np.column_stack([x, y, z])


def _gyro_safe(n: int) -> np.ndarray:
    """Slow, controlled rotation — e.g. turning phone over.  ≈ ±0.3 rad/s."""
    x = rng.normal(0, 0.05, n)
    y = rng.normal(0, 0.05, n)
    z = rng.normal(0, 0.05, n)
    return np.column_stack([x, y, z])


def _gyro_walking(n: int) -> np.ndarray:
    """Natural body rotation while walking.  ≈ ±0.8 rad/s."""
    t = np.linspace(0, 2 * np.pi, n)
    x = 0.4 * np.sin(2 * t) + rng.normal(0, 0.08, n)
    y = 0.3 * np.cos(3 * t) + rng.normal(0, 0.08, n)
    z = 0.2 * np.sin(t)     + rng.normal(0, 0.06, n)
    return np.column_stack([x, y, z])


def _gyro_danger(n: int) -> np.ndarray:
    """Rapid uncontrolled spin / tumble during a fall.  ≈ ±4–6 rad/s."""
    t = np.linspace(0, 4 * np.pi, n)
    amp_x = rng.uniform(2.5, 5.0)
    amp_y = rng.uniform(2.5, 5.0)
    amp_z = rng.uniform(1.5, 4.0)
    x = amp_x * np.sin(rng.uniform(2, 6) * t) + rng.normal(0, 0.3, n)
    y = amp_y * np.cos(rng.uniform(2, 6) * t) + rng.normal(0, 0.3, n)
    z = amp_z * np.sin(rng.uniform(2, 6) * t) + rng.normal(0, 0.2, n)
    return np.column_stack([x, y, z])


# ── generators map ───────────────────────────────────────────────────────────
SAFE_GENERATORS = {
    'accelerometer': [_accel_safe, _accel_walking],
    'gyroscope':     [_gyro_safe,  _gyro_walking],
}

DANGER_GENERATORS = {
    'accelerometer': [_accel_danger_fall, _accel_danger_shake],
    'gyroscope':     [_gyro_danger],
}


def _generate_windows(sensor_type: str, label: int, n_windows: int) -> list[np.ndarray]:
    gens = SAFE_GENERATORS[sensor_type] if label == 0 else DANGER_GENERATORS[sensor_type]
    windows = []
    for i in range(n_windows):
        gen = gens[i % len(gens)]
        windows.append(gen(WINDOW_SIZE))
    return windows


def _windows_to_records(windows, sensor_type, label, user_id, base_ts):
    records = []
    ts = base_ts
    for window in windows:
        for reading in window:
            records.append(SensorTrainingData(
                id=str(uuid.uuid4()),
                user_id=user_id,
                sensor_type=sensor_type,
                timestamp=ts,
                x=float(reading[0]),
                y=float(reading[1]),
                z=float(reading[2]),
                label=label,
                is_verified=True,
            ))
            ts += 50  # 50 ms between readings ≈ 20 Hz
    return records, ts


# ── main ─────────────────────────────────────────────────────────────────────

def seed():
    app = create_app()
    with app.app_context():
        # We need a real user_id to satisfy the FK constraint.
        user = User.query.first()
        if not user:
            print("❌ No users found in the database.")
            print("   Please register at least one account via the app, then re-run this script.")
            return

        user_id = user.id
        print(f"✅ Using user_id: {user_id} ({user.full_name})")

        # Clear existing synthetic (unverified=False) seed data to avoid duplication
        existing = SensorTrainingData.query.filter_by(user_id=user_id).count()
        if existing > 0:
            confirm = input(
                f"⚠️  Found {existing} existing records for this user. "
                "Delete them and reseed? [y/N] "
            ).strip().lower()
            if confirm != 'y':
                print("Aborted.")
                return
            SensorTrainingData.query.filter_by(user_id=user_id).delete()
            db.session.commit()
            print(f"🗑  Cleared {existing} existing records.")

        base_ts = int(time.time() * 1000)
        all_records = []

        for sensor_type in ('accelerometer', 'gyroscope'):
            for label, n_windows in ((0, SAFE_WINDOWS), (1, DANGER_WINDOWS)):
                tag = 'safe' if label == 0 else 'danger'
                windows = _generate_windows(sensor_type, label, n_windows)
                records, base_ts = _windows_to_records(
                    windows, sensor_type, label, user_id, base_ts
                )
                all_records.extend(records)
                print(f"   Generated {len(records):>5} readings  [{sensor_type:>14} / {tag}]  ({n_windows} windows)")

        db.session.bulk_save_objects(all_records)
        db.session.commit()
        print(f"\n✅ Seeded {len(all_records)} synthetic training records into sensor_training_data.")
        print("\n🔄 Starting model training...")


def main():
    seed()

    # Delegate to train_model.train() directly
    from scripts.train_model import train
    train()


if __name__ == "__main__":
    main()
