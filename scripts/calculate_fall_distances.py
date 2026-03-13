import os
import sys
import pandas as pd
import numpy as np

# Path setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(PROJECT_ROOT, "data_visualisation", "MEDIUM_FALL_CLEANED.csv")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "fall_motion_distances.txt")

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
        diffs = np.diff(group_coords, axis=0)  # shape (39, 3)
        distances = np.linalg.norm(diffs, axis=1)  # shape (39,)
        
        mean_distance = np.mean(distances)
        group_means.append(mean_distance)
        
    group_means = np.array(group_means)
    
    # The actual falls are the high spikes. 
    # We want to remove the low stationary "safe" data from this fall dataset 
    # so we can find the true average of the fall impacts.
    # We use a threshold of 0.2 (which is safely above the safe motion average of 0.01-0.08)
    # to isolate only the throws/falls.
    
    THRESHOLD = 0.20
    
    valid_indices = group_means >= THRESHOLD
    filtered_means = group_means[valid_indices]
    low_data_groups = group_means[~valid_indices]
    
    final_average = np.mean(filtered_means)
    
    # Generate output
    output_lines = []
    output_lines.append(f"Total Groups Processed: {n_groups} (40 points per group)")
    output_lines.append(f"Total Low-Data Baseline Groups Removed: {len(low_data_groups)}")
    output_lines.append(f"Total High-Spike Fall Groups Retained: {len(filtered_means)}")
    output_lines.append("\n--- GROUP-WISE MEAN DISTANCES ---")
    
    for i in range(n_groups):
        if not valid_indices[i]:
            status = " (LOW DATA - REMOVED)"
        else:
            status = " (HIGH SPIKE - RETAINED)"
        output_lines.append(f"Group {i+1:03d}: {group_means[i]:.6f}{status}")
        
    output_lines.append("\n" + "="*50)
    output_lines.append(f"FINAL AVERAGE FALL DISTANCE (spikes only): {final_average:.6f}")
    output_lines.append("="*50 + "\n")
    
    output_text = "\n".join(output_lines)
    
    with open(OUTPUT_PATH, "w") as f:
        f.write(output_text)
        
    print(f"✅ Calculation complete. Results saved to {OUTPUT_PATH}")
    print(f"Final Average Distance: {final_average:.6f}")

if __name__ == "__main__":
    calculate_distances()
