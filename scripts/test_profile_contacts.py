"""End-to-end test of profile fetch and contact add via the ORM layer."""
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.trusted_contact import TrustedContact

app = create_app()

with app.app_context():
    # Pick a real user from DB
    user = db.session.execute(db.select(User).limit(1)).scalar_one_or_none()
    if not user:
        print("NO USERS IN DB")
        exit(1)

    uid = user.id
    print(f"Testing with user: id={uid}, phone={user.phone}")

    # --- Test 1: profile fetch (same logic as the route) ---
    print("\n=== Test 1: Profile Fetch ===")
    try:
        fetched = User.query.get(uid)
        print(f"  User.query.get() => {fetched}")
        contacts = TrustedContact.query.filter_by(user_id=uid).all()
        print(f"  contacts count: {len(contacts)}")
        settings = user.settings
        print(f"  settings: {settings}")
        emergency = settings.emergency_number if settings else None
        print(f"  emergency_number: {emergency}")

        profile_data = {
            "user_id": fetched.id,
            "full_name": fetched.full_name,
            "phone": fetched.phone,
            "emergency_contact": emergency,
            "trusted_contacts": [c.to_dict() for c in contacts],
        }
        print(f"  profile_data OK: {profile_data}")
    except Exception as e:
        import traceback
        print("  PROFILE FETCH ERROR:")
        traceback.print_exc()

    # --- Test 2: add a trusted contact ---
    print("\n=== Test 2: Add Trusted Contact ===")
    try:
        # Simulate bulk update of existing primary contacts
        TrustedContact.query.filter_by(user_id=uid, is_primary=True).update(
            {'is_primary': False}
        )
        new_contact = TrustedContact(
            user_id=uid,
            name="Test Contact",
            phone="+919000000001",
            relationship="Friend",
            is_primary=True,
        )
        db.session.add(new_contact)
        db.session.commit()
        print(f"  Contact added: id={new_contact.id}")

        # Clean up
        db.session.delete(new_contact)
        db.session.commit()
        print("  Contact deleted (cleanup OK)")
    except Exception as e:
        import traceback
        print("  ADD CONTACT ERROR:")
        traceback.print_exc()
        db.session.rollback()
