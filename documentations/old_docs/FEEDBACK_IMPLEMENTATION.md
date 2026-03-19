# Feedback Loop Implementation Guide

This document outlines the architecture and implementation of the **ML Feedback Path** in the Asfalis backend. This system allows the machine learning model to improve over time by learning from real-world user corrections.

---

## 🔄 The Feedback Lifecycle
The system follows a 4-step reinforcement loop:
1. **Inference & Capture**: Sensor data is analyzed, and the raw window is saved to the DB.
2. **Alert Trigger**: If danger is predicted, an `alert_id` is generated.
3. **User Correction**: The user provides feedback (Confirm or False Alarm).
4. **Data Refinement**: The backend re-labels the captured data based on the feedback.
5. **Retraining**: The model is retrained on the refined dataset.

---

## 🛠 1. Data Ingestion (Capture)
When the frontend detects a potential fall, it calls the `predict` or `analyze` endpoints.

- **Endpoint**: `POST /protection/predict` or `POST /protection/sensor-data`
- **Logic**: 
  - The `analyze_sensor_data` service function receives the 40-step sensor window.
  - It runs the model and saves the data to the `sensor_training_data` table using `save_training_data`.
  - Initially, the data is saved with `is_verified=False` and a `label` matching the model's prediction.

```python
# app/services/protection_service.py
def analyze_sensor_data(...):
    # ... predict danger ...
    predicted_label = 1 if is_danger else 0
    save_training_data(user_id, sensor_type, readings, label=predicted_label, is_verified=False)
```

---

## 🛠 2. SOS Alert Generation
If the prediction suggests danger, an `SOSAlert` record is created. This record stores the `triggered_at` timestamp, which serves as the "anchor" for finding the relevant sensor data later.

- **Model**: `SOSAlert` (table: `sos_alerts`)
- **Key field**: `triggered_at`

---

## 🛠 3. User Feedback (The Correction)
After an Auto-SOS event, the app displays a countdown. The user can either confirm it was an actual emergency or dismiss it as a false alarm.

- **Endpoint**: `POST /protection/feedback/<alert_id>`
- **Payload**: `{"is_false_alarm": boolean}`
- **Logic**: This calls `submit_sos_feedback`.

---

## 🛠 4. Data Refinement (Re-labeling)
This is the core of the feedback path. The system searches for the raw sensor data that caused that specific alert and corrects its label.

- **Implementation**: `submit_sos_feedback` in `app/services/protection_service.py`.
- **Finding the Data**: Since the sensor data and the alert are separate tables, the system looks for any **unverified** data from that user within a **+/- 5 second window** of the alert's `triggered_at` time.
- **Action**:
  - Updates the `label` (0 for safe, 1 for danger).
  - Sets `is_verified=True`.

```python
# Refinement Logic in app/services/protection_service.py
window_start = alert.triggered_at - timedelta(seconds=5)
window_end   = alert.triggered_at + timedelta(seconds=5)

records = SensorTrainingData.query.filter(
    SensorTrainingData.user_id == user_id,
    SensorTrainingData.is_verified == False,
    SensorTrainingData.created_at.between(window_start, window_end)
).all()

for record in records:
    record.label = 0 if is_false_alarm else 1
    record.is_verified = True
```

---

## 🛠 5. Model Retraining
The final step is to use this verified data to produce a better model.

- **Endpoint**: `POST /protection/train-model`
- **Logic**: 
  - Fetches all records from `sensor_training_data` where `label IS NOT NULL` (prioritizing `is_verified=True` data).
  - Reconstructs the 40-step windows.
  - Trains a new `RandomForestClassifier`.
  - Saves the new model binary to the `ml_models` table in the DB.
  - **Cache Invalidation**: Calls `_reset_model_cache()` so the live server immediately picks up the new model without a restart.

---

## 📂 Key Files
- `app/routes/protection.py`: API Endpoints for prediction and feedback.
- `app/services/protection_service.py`: Business logic for ML and feedback processing.
- `app/models/sensor_data.py`: Database model for captured sensor data.
- `app/models/ml_model.py`: Database model for storing trained model binaries.
