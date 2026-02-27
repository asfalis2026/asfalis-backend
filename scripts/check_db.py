import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

# Check all tables
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
print('Tables:', [r[0] for r in cur.fetchall()])

# Check columns in otp_records
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'otp_records' ORDER BY ordinal_position")
print('otp_records columns:', cur.fetchall())

# Check columns in users
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'users' ORDER BY ordinal_position")
print('users columns:', cur.fetchall())

# Check enums
cur.execute("SELECT unnest(enum_range(NULL::otp_purpose_enum))::text")
print('otp_purpose_enum values:', [r[0] for r in cur.fetchall()])

cur.execute("SELECT unnest(enum_range(NULL::auth_provider_enum))::text")
print('auth_provider_enum values:', [r[0] for r in cur.fetchall()])

# Check row counts
for table in ['users', 'otp_records', 'trusted_contacts', 'sos_alerts', 'revoked_tokens', 'user_settings']:
    try:
        cur.execute(f'SELECT COUNT(*) FROM {table}')
        print(f'{table} count: {cur.fetchone()[0]}')
    except Exception as e:
        print(f'{table}: ERROR - {e}')
        conn.rollback()

conn.close()
