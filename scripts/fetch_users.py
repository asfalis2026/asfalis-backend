#!/usr/bin/env python3
"""
Fetch and Decrypt Users from the Asfalis database.
This script demonstrates fetching sensitive user data which is automatically
decrypted by the EncryptedString TypeDecorator in the SQLAlchemy model.
"""

import sys
import os

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import ScopedSession
from app.models.user import User

def fetch_and_display_users():
    print("=" * 100)
    print(f"{'ID':<6} | {'Full Name':<20} | {'Email':<30} | {'Phone':<15} | {'Verified':<8}")
    print("-" * 100)

    try:
        users = ScopedSession.query(User).all()
        
        if not users:
            print("No users found in the database.")
            return

        for user in users:
            print(f"{str(user.id):<6} | {str(user.full_name):<20} | {str(user.email):<30} | {str(user.phone):<15} | {str(user.is_verified):<8}")

        print("-" * 100)
        print(f"Total Users: {len(users)}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        ScopedSession.remove()

if __name__ == "__main__":
    fetch_and_display_users()
