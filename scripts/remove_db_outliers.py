import os
import sys
import pandas as pd
import numpy as np
from dotenv import load_dotenv

load_dotenv()

# Path setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.config import Config
from sqlalchemy import create_engine
from app.extensions import db
from app.models.sensor_data import SensorTrainingData

def remove_outliers():
    app = create_app()
    with app.app_context():
        print("🔄 Connecting to database...")
        db_url = Config.SQLALCHEMY_DATABASE_URI
        engine = db.engine
        
        # Fetch labeled training data
        query = "SELECT * FROM sensor_training_data WHERE label IS NOT NULL"
        df = pd.read_sql(query, engine)
        
        if df.empty:
            print("⚠️ No training data found in 'sensor_training_data'. Aborting.")
            return

        print(f"✅ Loaded {len(df)} records.")
        
        FEATURE_WINDOW_SIZE = 40
        
        # Group by user, sensor type, AND label to keep safe/danger sequences totally separate
        grouped = df.groupby(['user_id', 'sensor_type', 'label'])
        
        ids_to_delete = []
        
        for (uid, stype, label), group in grouped:
            # Sort by timestamp to recreate chronological windows
            group = group.sort_values('timestamp')
            
            raw_x = group['x'].values
            raw_y = group['y'].values
            raw_z = group['z'].values
            ids = group['id'].values
            
            num_readings = len(group)
            if num_readings < FEATURE_WINDOW_SIZE:
                continue
                
            num_windows = num_readings // FEATURE_WINDOW_SIZE
            
            group_means = []
            group_window_ids = []
            
            for i in range(num_windows):
                start = i * FEATURE_WINDOW_SIZE
                end = start + FEATURE_WINDOW_SIZE

                w_x = raw_x[start:end]
                w_y = raw_y[start:end]
                w_z = raw_z[start:end]
                w_ids = ids[start:end]
                
                coords = np.column_stack([w_x, w_y, w_z])
                diffs = np.diff(coords, axis=0)
                distances = np.linalg.norm(diffs, axis=1)
                mean_dist = np.mean(distances)
                
                group_means.append(mean_dist)
                group_window_ids.append(w_ids)
                
            group_means = np.array(group_means)
            
            if label == 0:
                # Safe dataset logic: Remove mathematical outliers using IQR
                q1 = np.percentile(group_means, 25)
                q3 = np.percentile(group_means, 75)
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                
                valid_indices = (group_means >= lower) & (group_means <= upper)
                
                for i, valid in enumerate(valid_indices):
                    if not valid:
                        ids_to_delete.extend(group_window_ids[i])
            else:
                # Danger/Fall dataset logic (label = 1): Keep spikes, remove low-baseline safe data
                THRESHOLD = 0.20
                valid_indices = group_means >= THRESHOLD
                
                for i, valid in enumerate(valid_indices):
                    if not valid:
                        ids_to_delete.extend(group_window_ids[i])

        print(f"Found {len(ids_to_delete) // 40} outlier groups ({len(ids_to_delete)} total data points) to delete.")
        
        if not ids_to_delete:
            print("No outliers to remove!")
            return
            
        BATCH_SIZE = 500
        total_deleted = 0
        
        for i in range(0, len(ids_to_delete), BATCH_SIZE):
            batch_ids = ids_to_delete[i:i + BATCH_SIZE]
            db.session.query(SensorTrainingData).filter(SensorTrainingData.id.in_(batch_ids)).delete(synchronize_session=False)
            db.session.commit()
            total_deleted += len(batch_ids)
            
        print(f"✅ Successfully deleted {total_deleted} outlier rows from the database.")

if __name__ == "__main__":
    remove_outliers()
