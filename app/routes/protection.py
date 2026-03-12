
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.schemas.protection_schema import ToggleProtectionSchema, SensorDataSchema, SensorWindowSchema
from app.services.protection_service import (
    toggle_protection, get_protection_status, analyze_sensor_data,
    predict_from_window, submit_sos_feedback
)
from marshmallow import ValidationError
import threading
import logging

logger = logging.getLogger(__name__)

protection_bp = Blueprint('protection', __name__)

@protection_bp.route('/toggle', methods=['POST'])
@jwt_required()
def toggle():
    current_user_id = get_jwt_identity()
    schema = ToggleProtectionSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    success, msg = toggle_protection(current_user_id, data['is_active'])
    
    status = get_protection_status(current_user_id)
    return jsonify(success=True, data=status, message=msg), 200

@protection_bp.route('/status', methods=['GET'])
@jwt_required()
def status():
    current_user_id = get_jwt_identity()
    status = get_protection_status(current_user_id)
    return jsonify(success=True, data=status), 200

@protection_bp.route('/sensor-data', methods=['POST'])
@jwt_required()
def sensor_data():
    current_user_id = get_jwt_identity()
    schema = SensorDataSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    result = analyze_sensor_data(
        current_user_id, 
        data['sensor_type'], 
        data['data'], 
        data['sensitivity']
    )
    
    return jsonify(success=True, data=result), 200

@protection_bp.route('/predict', methods=['POST'])
@jwt_required()
def predict():
    """Auto SOS: ML-based danger prediction from a sensor window.

    The frontend calls this endpoint **only** when the local sensor magnitude
    already exceeded the user-configured threshold.  If the toggle is off the
    request is rejected.  If the model predicts danger an SOS countdown is
    started automatically.

    Request body::

        {
          "window":      [[x, y, z], ...],   // pre-filtered sensor readings
          "sensor_type": "accelerometer",    // or "gyroscope" (default: accelerometer)
          "location":    "optional string",  // human-readable location label
          "latitude":    12.9716,            // device GPS latitude  (optional but recommended)
          "longitude":   77.5946             // device GPS longitude (optional but recommended)
        }

    Response::

        {
          "prediction":  0 | 1,
          "confidence":  float,
          "sensor_type": str,
          "sos_sent":    bool,
          "alert_id":    str | null,
          "message":     str | null
        }
    """
    current_user_id = get_jwt_identity()
    schema = SensorWindowSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    result = predict_from_window(
        current_user_id,
        data['window'],
        sensor_type=data.get('sensor_type', 'accelerometer'),
        location=data.get('location', 'Unknown'),
        latitude=data.get('latitude'),
        longitude=data.get('longitude')
    )

    return jsonify(success=True, data=result), 200

@protection_bp.route('/collect', methods=['POST'])
@jwt_required()
def collect_data():
    """Endpoint to ingest labeled sensor data for training."""
    current_user_id = get_jwt_identity()
    from app.schemas.protection_schema import SensorTrainingSchema
    from app.services.protection_service import save_training_data

    schema = SensorTrainingSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    success, msg = save_training_data(
        current_user_id,
        data['sensor_type'],
        data['data'],
        data['label'],
        is_verified=True # Direct collection implies user knows the label
    )

    if success:
        return jsonify(success=True, message=msg), 201
    else:
        return jsonify(success=False, error={"code": "DB_ERROR", "message": msg}), 500

@protection_bp.route('/train-model', methods=['POST'])
def train_model():
    """
    Trigger ML model retraining with current training data.
    Runs in background thread to avoid blocking the request.
    No authentication required - designed for cron job usage.
    """
    from flask import current_app
    from app import create_app
    from app.extensions import db
    from app.models.ml_model import MLModel
    from app.services.protection_service import extract_features
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
    import pandas as pd
    import numpy as np
    import joblib
    import io
    from datetime import datetime
    
    def _train_in_background(app):
        """Background training function"""
        with app.app_context():
            try:
                logger.info("🔄 Starting model training...")
                
                # Fetch training data
                query = "SELECT * FROM sensor_training_data WHERE label IS NOT NULL"
                df = pd.read_sql(query, db.engine)
                
                if df.empty or len(df) < 40:
                    logger.warning("⚠️ Insufficient training data")
                    return
                
                # Prepare features
                FEATURE_WINDOW_SIZE = 40
                X_features = []
                y_labels = []
                
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

                        w_x = raw_x[start:end]
                        w_y = raw_y[start:end]
                        w_z = raw_z[start:end]
                        w_label = labels[start]

                        # Use the canonical extract_features() so training and
                        # inference are guaranteed to produce identical feature vectors.
                        window = np.column_stack([w_x, w_y, w_z])  # shape (N, 3)
                        feats = extract_features(window, stype).flatten()  # shape (17,)

                        X_features.append(feats)
                        y_labels.append(w_label)
                
                if not X_features:
                    logger.warning("⚠️ Not enough data to form windows")
                    return
                
                X = np.array(X_features)
                y = np.array(y_labels)
                
                logger.info(f"✅ Created {len(X)} training windows")
                
                # Train model
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
                model = RandomForestClassifier(n_estimators=100, random_state=42)
                model.fit(X_train, y_train)
                
                preds = model.predict(X_test)
                accuracy = accuracy_score(y_test, preds)
                
                logger.info(f"🎯 Training complete. Accuracy: {accuracy:.4f}")
                
                # Serialize model
                model_bytes = io.BytesIO()
                joblib.dump(model, model_bytes)
                model_data = model_bytes.getvalue()
                
                # Save to database
                db.session.query(MLModel).update({MLModel.is_active: False})
                
                version = f"v{datetime.now().strftime('%Y%m%d%H%M%S')}"
                new_model = MLModel(
                    version=version,
                    is_active=True,
                    data=model_data,
                    accuracy=float(accuracy)
                )
                db.session.add(new_model)
                db.session.commit()

                # Invalidate the in-memory model cache so the running server
                # immediately starts using this newly trained DB model instead
                # of the stale cached model (or the uncalibrated file fallback).
                from app.services.protection_service import _reset_model_cache
                _reset_model_cache()

                logger.info(f"💾 Model {version} saved with accuracy {accuracy:.4f} — cache invalidated.")
                
            except Exception as e:
                logger.error(f"❌ Training failed: {str(e)}")
                db.session.rollback()
    
    # Start training in background
    app = current_app._get_current_object()
    thread = threading.Thread(target=_train_in_background, args=(app,), daemon=True)
    thread.start()
    
    return jsonify(success=True, message="Model training started in background. Check server logs for progress."), 202


@protection_bp.route('/feedback/<string:alert_id>', methods=['POST'])
@jwt_required()
def sos_feedback(alert_id):
    """User feedback after an Auto SOS event (false alarm / confirmed danger).

    After the countdown resolves the frontend should call this endpoint so the
    ML model can learn from the user's correction.  Re-labelling the captured
    sensor data improves future predictions.

    Request body::

        {
          "is_false_alarm": true   // true = was NOT danger, false = was danger
        }

    Response::

        {
          "success": true,
          "message": "Feedback saved — N training record(s) re-labelled as safe."
        }
    """
    current_user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    if 'is_false_alarm' not in data:
        return jsonify(success=False, error={
            "code": "VALIDATION_ERROR",
            "message": "Missing required field: is_false_alarm (bool)"
        }), 400

    success, msg = submit_sos_feedback(
        current_user_id,
        alert_id,
        bool(data['is_false_alarm'])
    )

    if not success:
        code = "ALERT_NOT_FOUND" if "not found" in msg.lower() else "DB_ERROR"
        status = 404 if code == "ALERT_NOT_FOUND" else 500
        return jsonify(success=False, error={"code": code, "message": msg}), status

    return jsonify(success=True, message=msg), 200
