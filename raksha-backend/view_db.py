import sqlite3
import os

DB_PATH = 'instance/raksha.db'

def print_table(conn, table_name):
    print(f"\n{'='*20} {table_name} {'='*20}")
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        if not rows:
            print("(Empty)")
            return
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        print(f"Columns: {', '.join(column_names)}\n")
        
        for i, row in enumerate(rows, 1):
            print(f"Row {i}: {row}")
            
    except sqlite3.OperationalError as e:
        print(f"Error accessing table {table_name}: {e}")

if not os.path.exists(DB_PATH):
    print(f"Database not found at {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)

# Tables to inspect
tables = ['users', 'trusted_contacts', 'sos_alerts', 'otp_records']

for table in tables:
    print_table(conn, table)

conn.close()
