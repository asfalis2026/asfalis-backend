# Machine Learning in Asfalis: Auto SOS Detection

The Auto SOS feature is the core intelligence of Asfalis. It uses real-time motion analysis to distinguish between normal activities (walking, sitting) and emergency events (falls, accidents, or vigorous shaking).

---

## 🔬 Core Theory: Motion Distance Analysis

Before applying advanced ML, the system relies on a mathematical foundation called **Successive Point Distance**.

### Euclidean Distance Metric
For every axis $(x, y, z)$, we calculate the distance between consecutive sensor readings ($P_i$ and $P_{i-1}$):
$$Distance = \sqrt{(x_i - x_{i-1})^2 + (y_i - y_{i-1})^2 + (z_i - z_{i-1})^2}$$

### Empirical Thresholds
Based on our research data:
- **Safe Baseline**: Normal movement produces mean distances between **0.01 and 0.08**.
- **Danger Spikes**: Impact events or falls produce spikes well above **0.20**.

The ML model is trained to recognize the *statistical patterns* within these distances and raw magnitudes.

---

## 🧠 Model Architecture

### Algorithm: Random Forest Classifier
We use a **Random Forest** (ensemble of 100 Decision Trees). This model was chosen for its:
1. **Robustness**: Handles noise in sensor data effectively.
2. **Probability Output**: Allows us to map "Confidence" to user-defined "Sensitivity" levels.
3. **Efficiency**: Prediction on a window takes milliseconds on a standard backend.

### Input: The Sensor Window
Data is processed in **Windows of 40 readings** (approx. 1-2 seconds of motion depending on sampling rate).

---

## 📊 Feature Engineering (17 Features)

For every 40-point window, we compress raw data into a **17-dimensional feature vector**:

| Category | Features | Count |
| :--- | :--- | :--- |
| **Statistical** | Mean, Standard Deviation, Max, Min, Sum of Squares (per axis) | 15 |
| **Sensor Type**| One-Hot Encoding [Accelerometer, Gyroscope] | 2 |
| **Total** | | **17** |

### Detailed Feature List
The 17-dimensional vector is strictly ordered to ensure compatibility between the training script and the live API:
1.  **[0-4] X-Axis**: `mean`, `std`, `max`, `min`, `sum_squares`
2.  **[5-9] Y-Axis**: `mean`, `std`, `max`, `min`, `sum_squares`
3.  **[10-14] Z-Axis**: `mean`, `std`, `max`, `min`, `sum_squares`
4.  **[15-16] Sensor ID**: `[1, 0]` for Accelerometer, `[0, 1]` for Gyroscope.


### Code Snippet: Feature Extraction
```python
def extract_features(window, sensor_type):
    # window shape: (40, 3) -> [x, y, z] readings
    feats = []
    for i in range(3): # For each axis x, y, z
        axis = window[:, i]
        feats += [
            axis.mean(), 
            axis.std(), 
            axis.max(), 
            axis.min(), 
            np.sum(axis ** 2)
        ]
    
    # One-Hot Encoding for Sensor Type
    if sensor_type == 'accelerometer':
        feats += [1, 0]
    else:
        feats += [0, 1]
        
    return np.array(feats).reshape(1, -1)
```

---

## ⚙️ Prediction & Sensitivity

The model doesn't just return 0 or 1; it returns a **probability of danger**. We map this to the user's sensitivity setting in `user_settings`:

| Sensitivity | Probability Threshold | Meaning |
| :--- | :--- | :--- |
| **High** | `> 35%` | Aggressive trigger; higher false alarm risk. |
| **Medium**| `> 60%` | Balanced (Default). |
| **Low** | `> 85%` | Conservative trigger; only fires on clear impacts. |

### Code Snippet: Prediction Logic
```python
def predict_danger(window_data, sensitivity="medium"):
    features = extract_features(window_data)
    # Get probability [prob_safe, prob_danger]
    proba = model.predict_proba(features)[0]
    confidence = proba[1] 
    
    threshold = {"high": 0.35, "medium": 0.60, "low": 0.85}.get(sensitivity)
    return confidence >= threshold
```

---

## 🔄 Self-Training & Feedback Loop

Asfalis implements a **Reinforcement-style Feedback Loop**:

1. **Prediction**: System detects a "Fall".
2. **Countdown**: User sees a 10s cancellation window on their phone.
3. **Feedback**:
   - If user taps **"False Alarm"**: The captured sensor data is re-labeled as `0` (Safe).
   - If user **dispatches SOS**: The data is confirmed as `1` (Danger).
4. **Retraining**: Periodic background tasks run `scripts/train_model.py` to update the model with this verified user-specific data, making it more accurate over time.

---

## 🔧 Training Pipeline
The training script (`train_model.py`) performs the following:
1. Fetches all labeled data from Supabase (`sensor_training_data`).
2. Reconstructs 40-point windows.
3. Splits data (80% Train / 20% Test).
4. Trains the `RandomForestClassifier`.
5. Serializes the model using `joblib` and saves it to the `ml_models` table in the database.
6. Calls `_reset_model_cache()` to trigger an immediate hot-reload of the server-side model.

---

## 📈 Evaluation Metrics

The system's performance is monitored using `scripts/generate_test_report.py`, which evaluates the model against verified ground-truth data from the `data_visualisation/` directory.

### Key Performance Indicators (KPIs)
- **Accuracy**: Overall percentage of correct predictions.
- **Recall (Sensitivity)**: Most critical for SOS. Measures the model's ability to find all "Danger" events. A high recall ensures that genuine falls are rarely missed.
- **Precision**: Measures the model's accuracy when it *does* predict danger. Higher precision reduces false alarms ("False Positives").
- **F1-Score**: The harmonic mean of Precision and Recall, providing a balanced view of model health.

### Feature Importance
Through analysis of the Random Forest's internal entropy, we have identified that **Standard Deviation** and **Max Magnitude** on the **Y-Axis** (typically representing the vertical drop during a fall) are the most significant predictors of danger.

---

## 🚀 Production Deployment & Hot-Reloading

Asfalis uses a **"Hot-Load"** strategy to ensure model updates don't require server downtime:

1.  **Pickled Storage**: Models are serialized as binary BLOBs in PostgreSQL (`ml_models.data`).
2.  **Lazy Loading**: The `protection_service.py` only loads the model from the DB on the first prediction request.
3.  **In-Memory Caching**: Once loaded, the model stays in RAM for sub-millisecond inference.
4.  **Cache Invalidation**: When a new model is trained via the `/protection/train-model` endpoint, the `_model` global variable is reset to `None`. The very next user request will then pull the latest version from the database automatically.

```python
# app/services/protection_service.py
def _get_model():
    global _model
    if _model is None:
        # Fetch the row where is_active=True
        active_model = MLModel.query.filter_by(is_active=True).first()
        _model = joblib.load(io.BytesIO(active_model.data))
    return _model
```
