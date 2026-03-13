"""
seed_training_data_from_csv.py
──────────────────────────────
Reads the three labelled CSV datasets and streams them into the
Supabase (PostgreSQL) `sensor_training_data` table.

This allows the models to be retrained directly from the database
using the `train_model.py` script.

Owner: "Abhraneel K5" (a9834edc-57cf-4836-bc6b-a21710078d7a)
"""

import os
import sys
import time
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ── Path setup ──────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.models.sensor_data import SensorTrainingData
from app.extensions import db

# The user "Abhraneel K5"
TARGET_USER_ID = "a9834edc-57cf-4836-bc6b-a21710078d7a"

DATA_DIR = os.path.join(PROJECT_ROOT, "data_visualisation")

CSV_FILES = [
    {"path": os.path.join(DATA_DIR, "MEDIUM_DANGER.csv"),       "label": 1},
    {"path": os.path.join(DATA_DIR, "MEDIUM_FALL_CLEANED.csv"), "label": 1},
    {"path": os.path.join(DATA_DIR, "MEDIUM_SAFE.csv"),         "label": 0},
]


def process_csv(file_cfg: dict, session) -> int:
    """Read a CSV file and insert its rows into the DB in chunks."""
    path  = file_cfg["path"]
    label = file_cfg["label"]
    filename = os.path.basename(path)

    if not os.path.exists(path):
        print(f"  ⚠️  File not found: {path}")
        return 0

    print(f"📂 Processing {filename} ({'Danger' if label == 1 else 'Safe'}) ...")
    
    # Read the full CSV
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    # Required columns guarantee
    if not {"x", "y", "z"}.issubset(set(df.columns)):
        print(f"  ⚠️  Skipping {filename}: Missing x, y, or z columns.")
        return 0
        
    records = []
    
    # Optional columns for mapping timestamps
    has_date = 'date' in df.columns
    has_time = 'time' in df.columns
    has_value2 = 'value 2' in df.columns # logcat outputs usually have epoch ms here
    
    # Iterate and map directly to DB models
    for idx, row in df.iterrows():
        try:
            x_val = float(row['x'])
            y_val = float(row['y'])
            z_val = float(row['z'])
            
            # Figure out a unix timestamp (ms)
            ts_ms = int(time.time() * 1000) # Default to right now
            
            # The structure from the earlier look at these CSVs suggests 'value 2' 
            # might have a long unix timestamp. Let's try that first if it exists.
            if has_value2:
                try:
                    # Sometimes logcat appends stuff, so safely cast
                    ts_ms = int(float(str(row['value 2']).strip()))
                except Exception:
                    pass
            
            record = SensorTrainingData(
                user_id=TARGET_USER_ID,
                timestamp=ts_ms,
                x=x_val,
                y=y_val,
                z=z_val,
                sensor_type="accelerometer",
                label=label,
                is_verified=True # It came from clean data!
            )
            records.append(record)
        except Exception as e:
            pass # Skip malformed rows

    # Batch insert logic
    BATCH_SIZE = 1000
    total_inserted = 0

    # Execute batch inserts
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        session.bulk_save_objects(batch)
        try:
            session.commit()
            total_inserted += len(batch)
            print(f"  → Inserted batch: {total_inserted}/{len(records)} rows")
        except Exception as e:
            session.rollback()
            print(f"  ❌ Batch insert failed: {e}")
            break

    print(f"✅ Finished {filename}: successfully inserted {total_inserted} rows.\n")
    return total_inserted


def seed():
    app = create_app()
    with app.app_context():
        total = 0
        
        # Optionally, ask before truncating existing data for this user
        print(f"Target User ID: {TARGET_USER_ID} (Abhraneel K5)")
        print(f"Checking existing verified data for this user...")
        existing_count = db.session.query(SensorTrainingData).filter_by(
            user_id=TARGET_USER_ID, is_verified=True
        ).count()
        
        if existing_count > 0:
            print(f"⚠️  User already has {existing_count} verified records in the database.")
            print("To prevent duplicate data poisoning, we should probably delete them first.")
            # For this script we will force clear the existing *verified* data for this user
            # so development iterators don't create an infinitely growing dataset of dupes.
            try:
                db.session.query(SensorTrainingData).filter_by(
                    user_id=TARGET_USER_ID, 
                    is_verified=True
                ).delete()
                db.session.commit()
                print("🗑️   Cleared old verified data for this user.")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Failed to clear old data: {e}")

        # Stream new data
        print("-" * 50)
        for cfg in CSV_FILES:
            total += process_csv(cfg, db.session)
            
        print("-" * 50)
        print(f"🎉 All done! Seeded {total} total rows into Supabase DB.")

if __name__ == "__main__":
    seed()
