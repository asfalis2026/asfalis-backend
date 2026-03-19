# ML Model Test Report
Generated on: 2026-03-13 17:03:51

## 📊 Summary Metrics
- **Accuracy:** 0.6822 (68.22%)
- **Precision:** 0.6324
- **Recall (Sensitivity):** 0.9952
- **F1-Score:** 0.7734

## ⚙️ Model Details
- **Type:** RandomForestClassifier
- **Parameters:** {'bootstrap': True, 'ccp_alpha': 0.0, 'class_weight': None, 'criterion': 'gini', 'max_depth': None, 'max_features': 'sqrt', 'max_leaf_nodes': None, 'max_samples': None, 'min_impurity_decrease': 0.0, 'min_samples_leaf': 1, 'min_samples_split': 2, 'min_weight_fraction_leaf': 0.0, 'monotonic_cst': None, 'n_estimators': 100, 'n_jobs': -1, 'oob_score': False, 'random_state': 42, 'verbose': 0, 'warm_start': False}
- **Model Size:** 103.62 KB
- **Path:** `/Users/abhraneelkarmakar/Codes/Old_version/asfalis-backend/model.pkl`

## 📂 Dataset Information
- **Total Windows Tested:** 771
- **Safe Windows (0):** 351
- **Danger/Fall Windows (1):** 420
- **Window Size:** 40 points

## 📉 Evaluation Results

### Classification Report
```text
              precision    recall  f1-score   support

        Safe       0.98      0.31      0.47       351
      Danger       0.63      1.00      0.77       420

    accuracy                           0.68       771
   macro avg       0.81      0.65      0.62       771
weighted avg       0.79      0.68      0.63       771

```

### Confusion Matrix
| | Predicted Safe | Predicted Danger |
| :--- | :---: | :---: |
| **Actual Safe** | 108 | 243 |
| **Actual Danger** | 2 | 418 |


### Feature Importances
| Feature | Importance |
| :--- | :--- |
| std_x | 0.3257 |
| mag_mean | 0.1496 |
| mag_std | 0.1356 |
| mean_x | 0.1214 |
| min_z | 0.0516 |
| mean_z | 0.0513 |
| min_y | 0.0264 |
| max_y | 0.0263 |
| max_x | 0.0204 |
| mean_y | 0.0192 |
| std_y | 0.0191 |
| min_x | 0.0186 |
| max_z | 0.0148 |
| mag_max | 0.0133 |
| std_z | 0.0067 |
| z_crossing_rate | 0.0000 |
| sma | 0.0000 |


## 📝 Analysis Note
- False Positives (Safe as Danger): 243
- False Negatives (Danger as Safe): 2
