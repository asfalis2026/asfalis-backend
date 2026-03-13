import os
import sys
import pandas as pd
import numpy as np

# Path setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(PROJECT_ROOT, "data_visualisation", "MEDIUM_SAFE.csv")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "safe_motion_distances.txt")

def calculate_distances():
    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found.")
        return

    # Read CSV
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip().lower() for c in df.columns]
    
    if not {"x", "y", "z"}.issubset(set(df.columns)):
        print("Missing x, y, or z columns.")
        return

    # Extract coordinates
    coords = df[['x', 'y', 'z']].values
    
    # Split into groups of 40
    GROUP_SIZE = 40
    n_groups = len(coords) // GROUP_SIZE
    
    if n_groups == 0:
        print("Not enough data points.")
        return
        
    group_means = []
    
    for i in range(n_groups):
        start_idx = i * GROUP_SIZE
        end_idx = start_idx + GROUP_SIZE
        
        group_coords = coords[start_idx:end_idx]
        
        # Calculate distances between successive points: sqrt((x_i - x_{i-1})^2 + ...)
        # group_coords shape is (40, 3)
        diffs = np.diff(group_coords, axis=0)  # shape (39, 3)
        distances = np.linalg.norm(diffs, axis=1)  # shape (39,)
        
        mean_distance = np.mean(distances)
        group_means.append(mean_distance)
        
    group_means = np.array(group_means)
    
    # Remove outliers (using IQR method)
    q1 = np.percentile(group_means, 25)
    q3 = np.percentile(group_means, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    
    valid_indices = (group_means >= lower_bound) & (group_means <= upper_bound)
    filtered_means = group_means[valid_indices]
    outliers = group_means[~valid_indices]
    
    final_average = np.mean(filtered_means)
    
    # Generate output
    output_lines = []
    output_lines.append(f"Total Groups Processed: {n_groups} (40 points per group)")
    output_lines.append(f"Total Outliers Removed: {len(outliers)}")
    output_lines.append("\n--- GROUP-WISE MEAN DISTANCES ---")
    
    for i in range(n_groups):
        status = " (OUTLIER - REMOVED)" if not valid_indices[i] else ""
        output_lines.append(f"Group {i+1:03d}: {group_means[i]:.6f}{status}")
        
    output_lines.append("\n" + "="*50)
    output_lines.append(f"FINAL AVERAGE DISTANCE (excluding outliers): {final_average:.6f}")
    output_lines.append("="*50 + "\n")
    
    output_text = "\n".join(output_lines)
    
    with open(OUTPUT_PATH, "w") as f:
        f.write(output_text)
        
    print(f"✅ Calculation complete. Results saved to {OUTPUT_PATH}")
    print(f"Final Average Distance: {final_average:.6f}")

if __name__ == "__main__":
    calculate_distances()
