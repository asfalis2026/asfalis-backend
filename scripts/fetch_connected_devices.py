#!/usr/bin/env python3
"""
Fetch and Decrypt Connected Devices from the Asfalis database.
"""

import sys
import os

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import ScopedSession
from app.models.device import ConnectedDevice

def fetch_and_display_devices():
    print("=" * 80)
    print(f"{'ID':<6} | {'Device Name':<25} | {'MAC Address':<20} | {'User ID':<8}")
    print("-" * 80)

    try:
        devices = ScopedSession.query(ConnectedDevice).all()
        
        if not devices:
            print("No connected devices found.")
            return

        for device in devices:
            print(f"{str(device.id):<6} | {str(device.device_name):<25} | {str(device.device_mac):<20} | {str(device.user_id):<8}")

        print("-" * 80)
        print(f"Total Devices: {len(devices)}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        ScopedSession.remove()

if __name__ == "__main__":
    fetch_and_display_devices()
