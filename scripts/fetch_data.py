#!/usr/bin/env python3
"""
Unified data fetcher for Asfalis.
Usage:
    python3 scripts/fetch_data.py users
    python3 scripts/fetch_data.py contacts
    python3 scripts/fetch_data.py alerts
    python3 scripts/fetch_data.py locations
    python3 scripts/fetch_data.py tickets
"""

import sys
import os
import json
from argparse import ArgumentParser

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import ScopedSession
from app.models.user import User
from app.models.trusted_contact import TrustedContact
from app.models.sos_alert import SOSAlert
from app.models.location import LocationHistory
from app.models.support import SupportTicket

def print_table_header(columns, widths):
    header = " | ".join(f"{col:<{widths[i]}}" for i, col in enumerate(columns))
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    return len(header)

def fetch_users():
    items = ScopedSession.query(User).all()
    widths = [6, 20, 30, 15, 10]
    cols = ["ID", "Full Name", "Email", "Phone", "Verified"]
    line_len = print_table_header(cols, widths)
    for item in items:
        print(f"{str(item.id):<{widths[0]}} | {str(item.full_name):<{widths[1]}} | {str(item.email):<{widths[2]}} | {str(item.phone):<{widths[3]}} | {str(item.is_verified):<{widths[4]}}")
    print("-" * line_len)
    print(f"Total: {len(items)}")

def fetch_contacts():
    items = ScopedSession.query(TrustedContact).all()
    widths = [6, 20, 15, 30]
    cols = ["ID", "Name", "Phone", "Email"]
    line_len = print_table_header(cols, widths)
    for item in items:
        print(f"{str(item.id):<{widths[0]}} | {str(item.name):<{widths[1]}} | {str(item.phone):<{widths[2]}} | {str(item.email):<{widths[3]}}")
    print("-" * line_len)
    print(f"Total: {len(items)}")

def fetch_alerts():
    items = ScopedSession.query(SOSAlert).all()
    print("=" * 100)
    for item in items:
        print(f"ID: {item.id} | User ID: {item.user_id} | Status: {item.status}")
        print(f"  Location: {item.latitude}, {item.longitude}")
        print(f"  Address:  {item.address}")
        print(f"  Message:  {item.sos_message}")
        print(f"  Numbers:  {json.dumps(item.contacted_numbers)}")
        print("-" * 100)
    print(f"Total: {len(items)}")

def fetch_locations():
    items = ScopedSession.query(LocationHistory).limit(50).all() # Limit to avoid huge output
    widths = [6, 8, 30, 40]
    cols = ["ID", "User ID", "Coordinates", "Address"]
    line_len = print_table_header(cols, widths)
    for item in items:
        coords = f"{item.latitude}, {item.longitude}"
        print(f"{str(item.id):<{widths[0]}} | {str(item.user_id):<{widths[1]}} | {coords:<{widths[2]}} | {str(item.address):<{widths[3]}}")
    print("-" * line_len)
    print(f"Total: {len(items)} (Showing up to 50)")

def fetch_tickets():
    items = ScopedSession.query(SupportTicket).all()
    print("=" * 100)
    for item in items:
        print(f"ID: {item.id} | User ID: {item.user_id} | Status: {item.status}")
        print(f"  Subject: {item.subject}")
        print(f"  Message: {item.message}")
        print("-" * 100)
    print(f"Total: {len(items)}")

def main():
    parser = ArgumentParser(description="Asfalis Data Fetcher")
    parser.add_argument("table", choices=["users", "contacts", "alerts", "locations", "tickets"], help="Table to fetch data from")
    args = parser.parse_args()

    # Suppress SQLAlchemy logging unless needed
    import logging
    logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)

    try:
        if args.table == "users":
            fetch_users()
        elif args.table == "contacts":
            fetch_contacts()
        elif args.table == "alerts":
            fetch_alerts()
        elif args.table == "locations":
            fetch_locations()
        elif args.table == "tickets":
            fetch_tickets()
    except Exception as e:
        print(f"Error fetching {args.table}: {e}")
    finally:
        ScopedSession.remove()

if __name__ == "__main__":
    main()
