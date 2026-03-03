"""Inspect DB schema and data for debugging profile/contacts issues."""
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    # Users
    r = db.session.execute(db.text(
        "SELECT id, full_name, phone, is_verified, auth_provider FROM users LIMIT 5"
    ))
    print("=== Users ===")
    for row in r.fetchall():
        print(" ", row)

    # trusted_contacts columns
    r2 = db.session.execute(db.text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='trusted_contacts' ORDER BY ordinal_position"
    ))
    print("\n=== trusted_contacts columns ===")
    for row in r2:
        print(" ", row)

    # user_settings columns
    r3 = db.session.execute(db.text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='user_settings' ORDER BY ordinal_position"
    ))
    print("\n=== user_settings columns ===")
    for row in r3:
        print(" ", row)

    # users columns
    r4 = db.session.execute(db.text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='users' ORDER BY ordinal_position"
    ))
    print("\n=== users columns ===")
    for row in r4:
        print(" ", row)

    # Test User.query.get equivalent
    from app.models.user import User
    users = db.session.execute(db.select(User).limit(3)).scalars().all()
    print("\n=== User ORM fetch ===")
    for u in users:
        print(f"  id={u.id}, phone={u.phone}, settings={u.settings}")
