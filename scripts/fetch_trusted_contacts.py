#!/usr/bin/env python3
"""
Fetch and Decrypt Trusted Contacts from the Asfalis database.
"""

import sys
import os

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import ScopedSession
from app.models.trusted_contact import TrustedContact

def fetch_and_display_contacts():
    print("=" * 80)
    print(f"{'ID':<6} | {'Name':<20} | {'Phone':<15} | {'Email':<30}")
    print("-" * 80)

    try:
        contacts = ScopedSession.query(TrustedContact).all()
        
        if not contacts:
            print("No trusted contacts found.")
            return

        for contact in contacts:
            print(f"{str(contact.id):<6} | {str(contact.name):<20} | {str(contact.phone):<15} | {str(contact.email):<30}")

        print("-" * 80)
        print(f"Total Contacts: {len(contacts)}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        ScopedSession.remove()

if __name__ == "__main__":
    fetch_and_display_contacts()
