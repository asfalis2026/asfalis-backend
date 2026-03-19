# Maintenance & Utility Scripts

The Asfalis backend includes a suite of specialized Python scripts in the `scripts/` directory for database management, data science tasks, and system maintenance.

---

## 📂 1. Data Seeding & Migration

These scripts are used to populate the environment and move data between local files and the Supabase production database.
- **`seed_training_data.py`**: Reads raw accelerometer/gyroscope files and inserts thousands of rows into the `sensor_training_data` table. This is essential for bootstrapping a new environment for ML training.
- **`seed_training_data_from_csv.py`**: A specialized loader for formatted CSV datasets (e.g., specific fall studies).

---

## 🧹 2. Data Cleaning (Outlier Removal)

To ensure high model accuracy, we must remove "noisy" or mislabeled sensor readings from the training pipeline.
- **`remove_db_outliers.py`**: Calculates the motion distance for every reading in the DB. It identifies and deletes records that fall below the "motion baseline" (e.g., < 0.20 distance) in datasets that are supposed to be "Danger" events, ensuring the model only learns from the actual impact spikes.

---

## 🧠 3. ML Training & Evaluation

The core AI lifecycle is managed through these utilities.
- **`train_model.py` / `train_from_csv.py`**: These scripts perform the feature extraction, train the Random Forest, and **automatically update the database** with the new `model.pkl` BLOB.
- **`generate_test_report.py`**: Generates a detailed Markdown report (`model_test_report.md`) including:
    - **Accuracy, Precision, and Recall** metrics.
    - **Confusion Matrix** (visualizing False Positives vs False Negatives).
    - **Feature Importance** (showing which sensor axis were most predictive).

---

## 📊 4. Visualization

- **`visualise_acceleration.py`**: (Located in `data_visualisation/`) Generates PNG plots from CSV sensor data. These plots allow developers to visually inspect the "spikes" of a fall before deciding to include that data in the training set.

---

## 🛠️ Usage Summary

| Task | Command |
| :--- | :--- |
| **Bootstrapping** | `python scripts/seed_training_data.py` |
| **Data Cleanup** | `python scripts/remove_db_outliers.py` |
| **Model Update** | `python scripts/train_model.py` |
| **Performance Audit** | `python scripts/generate_test_report.py` |
