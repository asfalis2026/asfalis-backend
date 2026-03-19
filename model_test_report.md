# ML Model Test Report
Generated on: 2026-03-18 16:56:48

## 📊 Summary Metrics
- **Accuracy:** 0.8442 (84.42%)
- **Precision:** 0.7772
- **Recall (Sensitivity):** 0.9621
- **F1-Score:** 0.8598

## ⚙️ Model Details
- **Type:** LGBMClassifier
- **Parameters:** {'boosting_type': 'gbdt', 'class_weight': None, 'colsample_bytree': 0.8, 'importance_type': 'split', 'learning_rate': 0.1, 'max_depth': 7, 'min_child_samples': 20, 'min_child_weight': 0.001, 'min_split_gain': 0.0, 'n_estimators': 200, 'n_jobs': -1, 'num_leaves': 31, 'objective': None, 'random_state': 42, 'reg_alpha': 0.0, 'reg_lambda': 0.0, 'subsample': 0.8, 'subsample_for_bin': 200000, 'subsample_freq': 0, 'is_unbalance': True, 'verbosity': -1}
- **Model Size:** 158.60 KB
- **Path:** `/Users/abhraneelkarmakar/Codes/Old_version/asfalis-backend/auto_sos_model_LightGBM.pkl`

## 📂 Dataset Information
- **Total Windows Tested:** 584
- **Safe Windows (0):** 294
- **Danger/Fall Windows (1):** 290
- **Window Size:** 40 points

## 📉 Evaluation Results

### Classification Report
```text
              precision    recall  f1-score   support

        Safe       0.95      0.73      0.82       294
      Danger       0.78      0.96      0.86       290

    accuracy                           0.84       584
   macro avg       0.86      0.84      0.84       584
weighted avg       0.86      0.84      0.84       584

```

### Confusion Matrix
| | Predicted Safe | Predicted Danger |
| :--- | :---: | :---: |
| **Actual Safe** | 214 | 80 |
| **Actual Danger** | 11 | 279 |


### Feature Importances
| Feature | Importance |
| :--- | :--- |
| std_x | 179.0000 |
| mag_std | 122.0000 |
| std_z | 109.0000 |
| min_x | 68.0000 |
| min_z | 61.0000 |
| mean_z | 60.0000 |
| min_y | 60.0000 |
| mag_mean | 57.0000 |
| max_x | 55.0000 |
| mean_x | 44.0000 |
| mag_max | 44.0000 |
| mean_y | 44.0000 |
| max_y | 28.0000 |
| std_y | 26.0000 |
| max_z | 17.0000 |
| z_crossing_rate | 0.0000 |
| sma | 0.0000 |


## 📝 Analysis Note
- False Positives (Safe as Danger): 80
- False Negatives (Danger as Safe): 11
