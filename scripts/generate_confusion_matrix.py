import os
import sys
import joblib
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.metrics import confusion_matrix, classification_report, ConfusionMatrixDisplay
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()

# Path setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.config import Config
from app.services.protection_service import extract_features

DATA_DIR = os.path.join(PROJECT_ROOT, "data_visualisation")

CSV_FILES = [
    {"path": os.path.join(DATA_DIR, "MEDIUM_DANGER.csv"),       "label": 1},
    {"path": os.path.join(DATA_DIR, "MEDIUM_FALL_CLEANED.csv"), "label": 1},
    {"path": os.path.join(DATA_DIR, "MEDIUM_SAFE.csv"),         "label": 0},
]

FEATURE_WINDOW_SIZE = 40
SENSOR_TYPE = "accelerometer"
MODEL_PATH = os.path.join(PROJECT_ROOT, "auto_sos_model_LightGBM.pkl")
SCALER_PATH = os.path.join(PROJECT_ROOT, "auto_sos_scaler.pkl")

def load_csv(file_cfg: dict) -> pd.DataFrame:
    path = file_cfg["path"]
    label = file_cfg["label"]
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    required = {"x", "y", "z"}
    if not required.issubset(set(df.columns)):
        return pd.DataFrame()
    df["label"] = label
    return df

def build_windows_from_csv_df(df: pd.DataFrame):
    X_feats, y_labels = [], []
    raw_x = df["x"].astype(float).values
    raw_y = df["y"].astype(float).values
    raw_z = df["z"].astype(float).values
    labels = df["label"].values
    
    n_windows = len(df) // FEATURE_WINDOW_SIZE
    for i in range(n_windows):
        start = i * FEATURE_WINDOW_SIZE
        end = start + FEATURE_WINDOW_SIZE
        window = np.column_stack([raw_x[start:end], raw_y[start:end], raw_z[start:end]])
        feats = extract_features(window, SENSOR_TYPE).flatten()
        X_feats.append(feats)
        y_labels.append(labels[start])
    
    if len(X_feats) == 0:
        return np.empty((0, 17)), np.empty((0,))
    return np.array(X_feats), np.array(y_labels)

def get_db_windows():
    print("Connecting to database...")
    db_url = Config.SQLALCHEMY_DATABASE_URI
    engine = create_engine(db_url)
    
    query = "SELECT * FROM sensor_training_data WHERE label IS NOT NULL"
    try:
        df = pd.read_sql(query, engine)
    except Exception as e:
        print(f"Failed to read from db: {e}")
        return np.empty((0, 17)), np.empty((0,))
        
    if df.empty:
        print("No training data found in database.")
        return np.empty((0, 17)), np.empty((0,))

    X_features, y_labels = [], []
    grouped = df.groupby(['user_id', 'sensor_type'])
    
    for (uid, stype), group in grouped:
        group = group.sort_values('timestamp')
        
        raw_x = group['x'].values
        raw_y = group['y'].values
        raw_z = group['z'].values
        labels = group['label'].values
        
        num_readings = len(group)
        if num_readings < FEATURE_WINDOW_SIZE:
            continue
            
        num_windows = num_readings // FEATURE_WINDOW_SIZE
        
        for i in range(num_windows):
            start = i * FEATURE_WINDOW_SIZE
            end = start + FEATURE_WINDOW_SIZE
            window = np.column_stack([raw_x[start:end], raw_y[start:end], raw_z[start:end]])
            feats = extract_features(window, stype).flatten()
            
            X_features.append(feats)
            y_labels.append(labels[start])

    if not X_features:
        return np.empty((0, 17)), np.empty((0,))
        
    return np.array(X_features), np.array(y_labels)

def generate_matrix():
    print(f"Loading model from {MODEL_PATH}...")
    if not os.path.exists(MODEL_PATH):
        print("Model not found. Please train the model first.")
        return
    model = joblib.load(MODEL_PATH)

    # Load scaler
    scaler = None
    if os.path.exists(SCALER_PATH):
        scaler = joblib.load(SCALER_PATH)
        print(f"✅ Loaded scaler from {SCALER_PATH}")
    else:
        print(f"⚠️ Scaler not found at {SCALER_PATH}, predictions will use unscaled features.")

    all_X, all_y = [], []

    print("Loading data from CSVs...")
    for cfg in CSV_FILES:
        df = load_csv(cfg)
        if not df.empty:
            X, y = build_windows_from_csv_df(df)
            if X.shape[0] > 0:
                all_X.append(X)
                all_y.append(y)
                
    print("Loading data from DB...")
    X_db, y_db = get_db_windows()
    if X_db.shape[0] > 0:
        all_X.append(X_db)
        all_y.append(y_db)

    if not all_X:
        print("Not enough data to create any windows.")
        return

    X = np.vstack(all_X)
    y_true = np.concatenate(all_y)
    
    # Apply scaler if available
    if scaler is not None:
        X = scaler.transform(X)

    print(f"Generating predictions for {len(X)} windows...")
    y_pred = model.predict(X)
    
    class_names = ["safe (0)", "danger/fall (1)"]
    
    report = classification_report(y_true, y_pred, target_names=class_names)
    cm = confusion_matrix(y_true, y_pred)
    
    output_text = f"EVALUATION REPORT\n{'='*50}\n\n"
    output_text += "CLASSIFICATION REPORT:\n"
    output_text += report + "\n"
    output_text += f"\n{'='*50}\nCONFUSION MATRIX:\n"
    output_text += str(cm) + "\n"

    print(output_text)

    # Save to text file
    txt_out_path = os.path.join(PROJECT_ROOT, "evaluation_report.txt")
    with open(txt_out_path, "w") as f:
        f.write(output_text)
    print(f"✅ Saved evaluation report to: {txt_out_path}")
    
    # Try to plot the confusion matrix and save it
    try:
        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=class_names)
        fig, ax = plt.subplots(figsize=(8, 6))
        disp.plot(ax=ax, cmap='Blues')
        
        plt.title('Model Confusion Matrix', fontsize=16, fontweight='bold')
        
        plt.tight_layout()
        out_path = os.path.join(PROJECT_ROOT, "confusion_matrix.png")
        plt.savefig(out_path, dpi=300)
        print(f"✅ Saved confusion matrix visualization to: {out_path}")
    except Exception as e:
        print(f"\nFailed to save plot: {e}")

if __name__ == "__main__":
    generate_matrix()
