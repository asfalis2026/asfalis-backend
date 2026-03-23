"""
AUTO SOS — Step 4: TFLite Model Conversion
===================================================================

This script:
1. Loads extracted features (from 300-reading windows)
2. Trains a lightweight Neural Network (Deep Learning with Keras)
3. Converts the trained model to TFLite format
4. Applies post-training quantization for minimal size (KB)
5. Exports metadata documenting the expected input shapes

Run: python step4_tflite_model_conversion.py
"""

import numpy as np
import json
from pathlib import Path
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import pickle

# ============================================================================
# CONFIG
# ============================================================================

OUTPUT_DIR = Path(__file__).parent / 'output_images'
INPUT_FEATURES = OUTPUT_DIR / 'features.npz'

TEST_SIZE = 0.2
RANDOM_STATE = 42

print("\n" + "="*80)
print("STEP 4: NEURAL NETWORK TRAINING & TFLITE CONVERSION")
print("="*80)

print("\n-> Loading features...")
features_data = np.load(INPUT_FEATURES)
X = features_data['X']
y = features_data['y']

print(f"  Features shape: {X.shape}")
print(f"  Labels shape: {y.shape}")

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Save scaler for mobile inference
scaler_path = OUTPUT_DIR / 'auto_sos_tflite_scaler.pkl'
with open(scaler_path, 'wb') as f:
    pickle.dump(scaler, f)

# ============================================================================
# BUILD AND TRAIN NEURAL NETWORK
# ============================================================================

print("\n-> Building Lightweight Neural Network...")
nn_model = keras.Sequential([
    layers.Dense(64, activation='relu', input_shape=(17,)),
    layers.BatchNormalization(),
    layers.Dropout(0.2),
    
    layers.Dense(32, activation='relu'),
    layers.BatchNormalization(),
    layers.Dropout(0.1),
    
    layers.Dense(16, activation='relu'),
    
    layers.Dense(1, activation='sigmoid')  # Binary classification
])

nn_model.compile(
    optimizer=keras.optimizers.Adam(learning_rate=0.001),
    loss='binary_crossentropy',
    metrics=['accuracy', keras.metrics.AUC(name='auc')]
)

print("-> Training Neural Network...")

class_weight = {
    0: (y_train == 1).sum() / len(y_train),  # SAFE weight
    1: (y_train == 0).sum() / len(y_train)   # DANGER weight
}

nn_model.fit(
    X_train_scaled, y_train,
    epochs=50,
    batch_size=32,
    validation_split=0.2,
    class_weight=class_weight,
    verbose=1
)

loss, accuracy, auc = nn_model.evaluate(X_test_scaled, y_test, verbose=0)
print(f"\n+ Training Complete. Test Accuracy: {accuracy:.4f}, AUC: {auc:.4f}")

# Save Keras Model
keras_model_path = OUTPUT_DIR / 'auto_sos_mobile_model.keras'
nn_model.save(keras_model_path)
print(f"+ Saved Keras model to {keras_model_path}")

# ============================================================================
# CONVERT TO TFLITE WITH QUANTIZATION
# ============================================================================

print("\n-> Converting to TFLite (Post-Training Quantization)...")

# Convert the model
converter = tf.lite.TFLiteConverter.from_keras_model(nn_model)
converter.optimizations = [tf.lite.Optimize.DEFAULT] # Enable post-training quantization

tflite_model = converter.convert()

tflite_model_path = OUTPUT_DIR / 'auto_sos_mobile.tflite'
with open(tflite_model_path, 'wb') as f:
    f.write(tflite_model)
    
model_size_kb = len(tflite_model) / 1024
print(f"+ Saved TFLite model to {tflite_model_path}")
print(f"  TFLite Model Size: {model_size_kb:.2f} KB")

# ============================================================================
# EXPORT METADATA
# ============================================================================

print("\n-> Exporting Metadata...")

metadata = {
    "model_name": "auto_sos_mobile.tflite",
    "description": "Mobile optimized neural network for SOS detection from accelerometer features.",
    "input": {
        "shape": "(1, 17)",
        "type": "float32",
        "description": "17 extracted statistical features from a 300-point 50Hz window.",
        "features": [
            "X_mean", "X_std", "X_max", "X_min", "X_sum_sq",
            "Y_mean", "Y_std", "Y_max", "Y_min", "Y_sum_sq",
            "Z_mean", "Z_std", "Z_max", "Z_min", "Z_sum_sq",
            "is_accelerometer", "is_gyroscope"
        ],
        "normalization": {
            "method": "StandardScaler",
            "mean": scaler.mean_.tolist(),
            "scale": scaler.scale_.tolist()
        }
    },
    "output": {
        "shape": "(1, 1)",
        "type": "float32",
        "description": "Probability of DANGER (0.0 to 1.0). If probability > threshold, trigger SOS."
    },
    "recommended_threshold": 0.60
}

metadata_file = OUTPUT_DIR / 'model_metadata.json'
with open(metadata_file, 'w') as f:
    json.dump(metadata, f, indent=4)

print(f"+ Saved metadata to {metadata_file}")

print("\n" + "="*80)
print("SUCCESSFULLY CONVERTED AND EXPORTED MODELS!")
print("="*80)
