#!/usr/bin/env python3
"""
Fetch and Decrypt SOS Alerts from the Asfalis database.
Demonstrates decryption of Floats (Coordinates) and JSON (Contacts).
"""

import sys
import os
import json

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import ScopedSession
from app.models.sos_alert import SOSAlert

def fetch_and_display_alerts():
    print("=" * 100)
    print(f"{'ID':<6} | {'User ID':<8} | {'Coordinates':<30} | {'Status':<10}")
    print("-" * 100)

    try:
        alerts = ScopedSession.query(SOSAlert).all()
        
        if not alerts:
            print("No SOS alerts found.")
            return

        for alert in alerts:
            coords = f"{alert.latitude}, {alert.longitude}" if alert.latitude is not None else "N/A"
            print(f"{str(alert.id):<6} | {str(alert.user_id):<8} | {coords:<30} | {str(alert.status):<10}")
            print(f"  Address: {alert.address or 'N/A'}")
            print(f"  Message: {alert.sos_message or 'N/A'}")
            contacted = json.dumps(alert.contacted_numbers) if alert.contacted_numbers is not None else "[]"
            print(f"  Contacted: {contacted}")
            print("-" * 100)

        print(f"Total Alerts: {len(alerts)}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        ScopedSession.remove()

if __name__ == "__main__":
    fetch_and_display_alerts()
