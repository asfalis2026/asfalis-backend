"""
Splice _block1.py into lines 355-406 and _block2.py into lines 439-497
of protection_service.py (all line numbers 1-indexed, inclusive).
Do FIX 2 first so FIX 1 line numbers stay stable.
"""
import sys, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVC  = os.path.join(BASE, 'app', 'services', 'protection_service.py')
BLK1 = os.path.join(BASE, 'scripts', '_block1.py')
BLK2 = os.path.join(BASE, 'scripts', '_block2.py')

with open(SVC,  'r', encoding='utf-8') as f:
    lines = f.readlines()

with open(BLK1, 'r', encoding='utf-8') as f:
    block1 = f.readlines()

with open(BLK2, 'r', encoding='utf-8') as f:
    block2 = f.readlines()

# Sanity checks
assert lines[354].rstrip() == '    if is_danger:', \
    f"Line 355 mismatch: {lines[354]!r}"
assert lines[403].rstrip() == '    return {"alert_triggered": False, "confidence": confidence_danger}', \
    f"Line 404 mismatch: {lines[403]!r}"
assert lines[438].rstrip() == '    if prediction == 1:', \
    f"Line 439 mismatch: {lines[438]!r}"
assert lines[493].rstrip() == '    return response', \
    f"Line 494 mismatch: {lines[493]!r}"

print(f"Sanity checks passed. File has {len(lines)} lines.")

# FIX 2 first (higher line numbers — keeps FIX 1 line numbers stable)
lines = lines[:438] + block2 + lines[494:]
print(f"FIX 2 applied: predict_from_window block replaced. Now {len(lines)} lines.")

# FIX 1 (lower line numbers — unaffected by FIX 2)
lines = lines[:354] + block1 + lines[404:]
print(f"FIX 1 applied: analyze_sensor_data block replaced. Now {len(lines)} lines.")

with open(SVC, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Done — protection_service.py updated.")
