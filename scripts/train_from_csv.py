"""
train_from_csv.py
─────────────────
Train the fall-detection ML model using the three labelled CSV datasets
collected from the Android app:

    data_visualisation/MEDIUM_DANGER.csv      → label 1 (danger)
    data_visualisation/MEDIUM_FALL_CLEANED.csv → label 1 (fall / danger)
    data_visualisation/MEDIUM_SAFE.csv         → label 0 (safe)

The script uses the *exact same* extract_features() function that the live
server uses for inference, so training and inference feature vectors are
always identical (17 features).

Usage
─────
    cd /path/to/asfalis-backend
    python scripts/train_from_csv.py

Output
──────
    model.pkl  (written to the project root)
    The server's protection_service.py will pick this up automatically as the
    file-based fallback model on the next request.
"""

import os
import sys
import joblib
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

load_dotenv()

# ── Path setup ──────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.services.protection_service import extract_features  # noqa: E402

# ── Dataset configuration ────────────────────────────────────────────────────
DATA_DIR = os.path.join(PROJECT_ROOT, "data_visualisation")

CSV_FILES = [
    {"path": os.path.join(DATA_DIR, "MEDIUM_DANGER.csv"),       "label": 1},
    {"path": os.path.join(DATA_DIR, "MEDIUM_FALL_CLEANED.csv"), "label": 1},
    {"path": os.path.join(DATA_DIR, "MEDIUM_SAFE.csv"),         "label": 0},
]

# Must match the window size expected by extract_features() and inference.
FEATURE_WINDOW_SIZE = 40

# Sensor type used for all recordings (the CSVs collected accelerometer data).
SENSOR_TYPE = "accelerometer"

MODEL_OUTPUT_PATH = os.path.join(PROJECT_ROOT, "model.pkl")


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_csv(file_cfg: dict) -> pd.DataFrame:
    """Load a single CSV file and attach its target label."""
    path  = file_cfg["path"]
    label = file_cfg["label"]

    if not os.path.exists(path):
        print(f"  ⚠️  File not found, skipping: {path}")
        return pd.DataFrame()

    df = pd.read_csv(path)

    # Normalise column names to lowercase for robust lookup
    df.columns = [c.strip().lower() for c in df.columns]

    # Validate required columns exist
    required = {"x", "y", "z"}
    if not required.issubset(set(df.columns)):
        print(f"  ⚠️  Missing required columns {required} in {path}, skipping.")
        return pd.DataFrame()

    df["label"] = label
    print(f"  ✅ Loaded {len(df):>6,} rows  ← {os.path.basename(path)}  (label={label})")
    return df


def build_windows(df: pd.DataFrame):
    """Chunk rows into fixed-size windows and extract features.

    Returns
    ───────
    X : np.ndarray  shape (n_windows, 17)
    y : np.ndarray  shape (n_windows,)
    """
    X_feats, y_labels = [], []

    raw_x  = df["x"].astype(float).values
    raw_y  = df["y"].astype(float).values
    raw_z  = df["z"].astype(float).values
    labels = df["label"].values

    n_readings = len(df)
    n_windows  = n_readings // FEATURE_WINDOW_SIZE

    if n_windows == 0:
        print(f"  ⚠️  Not enough rows to form a single window of {FEATURE_WINDOW_SIZE}.")
        return np.empty((0, 17)), np.empty((0,))

    for i in range(n_windows):
        start = i * FEATURE_WINDOW_SIZE
        end   = start + FEATURE_WINDOW_SIZE

        window = np.column_stack([
            raw_x[start:end],
            raw_y[start:end],
            raw_z[start:end],
        ])  # shape (FEATURE_WINDOW_SIZE, 3)

        feats = extract_features(window, SENSOR_TYPE).flatten()  # (17,)
        X_feats.append(feats)
        y_labels.append(labels[start])  # label is uniform within each CSV

    return np.array(X_feats), np.array(y_labels)


# ── Main ─────────────────────────────────────────────────────────────────────

def train():
    print("\n📂 Loading CSV datasets …")
    frames = []
    for cfg in CSV_FILES:
        df = load_csv(cfg)
        if not df.empty:
            frames.append(df)

    if not frames:
        print("❌ No valid CSV files found. Aborting.")
        return

    # ── Build feature windows per dataset so each dataset contributes
    #    independently (avoids label bleed across file boundaries).
    print(f"\n🔨 Building feature windows (window size = {FEATURE_WINDOW_SIZE}) …")
    all_X, all_y = [], []

    label_names = {0: "safe", 1: "danger/fall"}
    for df in frames:
        label_val = int(df["label"].iloc[0])
        X, y = build_windows(df)
        if X.shape[0] == 0:
            continue
        all_X.append(X)
        all_y.append(y)
        print(f"  → {X.shape[0]:>5} windows  (label={label_val} / {label_names[label_val]})")

    if not all_X:
        print("❌ Not enough data to create any windows. Aborting.")
        return

    X = np.vstack(all_X)
    y = np.concatenate(all_y)

    print(f"\n✅ Total windows: {len(X)}  |  Features per window: {X.shape[1]}")
    unique, counts = np.unique(y, return_counts=True)
    for cls, cnt in zip(unique, counts):
        print(f"   Class {int(cls)} ({label_names.get(int(cls), '?')}): {cnt} windows")

    # ── Train / test split ───────────────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"\n🚀 Training RandomForestClassifier (100 trees) …")
    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    # ── Evaluate ─────────────────────────────────────────────────────────────
    preds = model.predict(X_test)
    acc   = accuracy_score(y_test, preds)

    print(f"\n🎯 Test Accuracy : {acc:.4f}  ({acc * 100:.2f}%)")
    print("\n📊 Classification Report:")
    print(classification_report(
        y_test, preds,
        target_names=[label_names.get(int(c), str(c)) for c in sorted(unique)]
    ))

    # ── Save model ───────────────────────────────────────────────────────────
    joblib.dump(model, MODEL_OUTPUT_PATH)
    size_kb = os.path.getsize(MODEL_OUTPUT_PATH) / 1024
    print(f"💾 Model saved → {MODEL_OUTPUT_PATH}  ({size_kb:.1f} KB)")
    
    # ── Save to DB ───────────────────────────────────────────────────────────
    import io
    from datetime import datetime
    model_bytes = io.BytesIO()
    joblib.dump(model, model_bytes)
    model_data = model_bytes.getvalue()
    
    from app import create_app
    from app.models.ml_model import MLModel
    from app.extensions import db

    app = create_app()
    with app.app_context():
        # Deactivate old models
        db.session.query(MLModel).update({MLModel.is_active: False})
        
        # Save new model
        version = f"v{datetime.now().strftime('%Y%m%d%H%M')}-csv"
        new_model = MLModel(
            version=version,
            is_active=True,
            data=model_data,
            accuracy=float(acc)
        )
        db.session.add(new_model)
        db.session.commit()
        print(f"💾 Model {version} saved to database with accuracy {new_model.accuracy:.4f}")

    print("\n✅ Done! The server will load this model automatically from the DB.")
    print("   Auto-SOS is now enabled for testing.\n")


if __name__ == "__main__":
    train()
