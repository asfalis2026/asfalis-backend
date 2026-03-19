import os
import sys
import joblib
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.metrics import confusion_matrix, classification_report, accuracy_score, precision_recall_fscore_support
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from datetime import datetime

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

FEATURE_NAMES = [
    "mean_x", "mean_y", "mean_z",
    "std_x", "std_y", "std_z",
    "max_x", "max_y", "max_z",
    "min_x", "min_y", "min_z",
    "mag_mean", "mag_max", "mag_std",
    "z_crossing_rate", "sma"
]

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
    db_url = Config.SQLALCHEMY_DATABASE_URI
    engine = create_engine(db_url)
    
    query = "SELECT * FROM sensor_training_data WHERE label IS NOT NULL"
    try:
        df = pd.read_sql(query, engine)
    except Exception:
        return np.empty((0, 17)), np.empty((0,))
        
    if df.empty:
        return np.empty((0, 17)), np.empty((0,))

    X_features, y_labels = [], []
    grouped = df.groupby(['user_id', 'sensor_type'])
    
    for (uid, stype), group in grouped:
        group = group.sort_values('timestamp')
        raw_x, raw_y, raw_z, labels = group['x'].values, group['y'].values, group['z'].values, group['label'].values
        
        num_windows = len(group) // FEATURE_WINDOW_SIZE
        for i in range(num_windows):
            start, end = i * FEATURE_WINDOW_SIZE, (i + 1) * FEATURE_WINDOW_SIZE
            window = np.column_stack([raw_x[start:end], raw_y[start:end], raw_z[start:end]])
            feats = extract_features(window, stype).flatten()
            X_features.append(feats)
            y_labels.append(labels[start])

    if not X_features: return np.empty((0, 17)), np.empty((0,))
    return np.array(X_features), np.array(y_labels)

def generate_report():
    if not os.path.exists(MODEL_PATH):
        print("Model file not found.")
        return
    model = joblib.load(MODEL_PATH)

    # Load scaler
    scaler = None
    if os.path.exists(SCALER_PATH):
        scaler = joblib.load(SCALER_PATH)
        print(f"✅ Loaded scaler from {SCALER_PATH}")
    else:
        print(f"⚠️ Scaler not found at {SCALER_PATH}, predictions will use unscaled features.")
    
    # Data Loading
    csv_X, csv_y = [], []
    for cfg in CSV_FILES:
        df = load_csv(cfg)
        if not df.empty:
            X, y = build_windows_from_csv_df(df)
            if X.shape[0] > 0:
                csv_X.append(X); csv_y.append(y)
    
    X_db, y_db = get_db_windows()
    
    all_X = []
    if csv_X: all_X.append(np.vstack(csv_X))
    if X_db.shape[0] > 0: all_X.append(X_db)
    
    if not all_X:
        print("No data found.")
        return
        
    X = np.vstack(all_X)
    y_true = np.concatenate(csv_y + ([y_db] if y_db.shape[0] > 0 else []))

    # Apply scaler if available
    if scaler is not None:
        X = scaler.transform(X)

    y_pred = model.predict(X)
    
    # Metrics
    acc = accuracy_score(y_true, y_pred)
    prec, rec, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='binary')
    cm = confusion_matrix(y_true, y_pred)
    report_str = classification_report(y_true, y_pred, target_names=["Safe", "Danger"])
    
    # Model Stats
    size_kb = os.path.getsize(MODEL_PATH) / 1024
    
    # Feature Importance (if RFC)
    importance_md = ""
    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
        sorted_indices = np.argsort(importances)[::-1]
        importance_md = "\n### Feature Importances\n| Feature | Importance |\n| :--- | :--- |\n"
        for idx in sorted_indices:
            importance_md += f"| {FEATURE_NAMES[idx]} | {importances[idx]:.4f} |\n"
    
    # Build MD Report
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md_content = f"""# ML Model Test Report
Generated on: {timestamp}

## 📊 Summary Metrics
- **Accuracy:** {acc:.4f} ({acc*100:.2f}%)
- **Precision:** {prec:.4f}
- **Recall (Sensitivity):** {rec:.4f}
- **F1-Score:** {f1:.4f}

## ⚙️ Model Details
- **Type:** {type(model).__name__}
- **Parameters:** {model.get_params()}
- **Model Size:** {size_kb:.2f} KB
- **Path:** `{MODEL_PATH}`

## 📂 Dataset Information
- **Total Windows Tested:** {len(X)}
- **Safe Windows (0):** {np.sum(y_true == 0)}
- **Danger/Fall Windows (1):** {np.sum(y_true == 1)}
- **Window Size:** {FEATURE_WINDOW_SIZE} points

## 📉 Evaluation Results

### Classification Report
```text
{report_str}
```

### Confusion Matrix
| | Predicted Safe | Predicted Danger |
| :--- | :---: | :---: |
| **Actual Safe** | {cm[0][0]} | {cm[0][1]} |
| **Actual Danger** | {cm[1][0]} | {cm[1][1]} |

{importance_md}

## 📝 Analysis Note
- False Positives (Safe as Danger): {cm[0][1]}
- False Negatives (Danger as Safe): {cm[1][0]}
"""

    report_path = os.path.join(PROJECT_ROOT, "model_test_report.md")
    with open(report_path, "w") as f:
        f.write(md_content)
    
    print(f"✅ Test report generated at: {report_path}")

if __name__ == "__main__":
    generate_report()
