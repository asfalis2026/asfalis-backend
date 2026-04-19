#!/usr/bin/env python3
"""
One-time data migration: encrypt existing plaintext rows in the database.

Run this ONCE after deploying the Alembic migration:
    PYTHONPATH=. python3 scripts/migrate_plaintext_to_encrypted.py

Prerequisites:
  • FIELD_ENCRYPTION_KEY and FIELD_HMAC_KEY must be set in .env (or the environment).
  • DATABASE_URL must point to the live database (or SQLite default is used).
  • The Alembic migration j1k2l3m4n5o6 must already have been applied.
"""

import sys
import os
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format='%(levelname)s  %(message)s')
logger = logging.getLogger('encrypt_migration')

enc_key = os.environ.get('FIELD_ENCRYPTION_KEY')
hmac_key_val = os.environ.get('FIELD_HMAC_KEY')
db_url = os.environ.get('DATABASE_URL', 'sqlite:///Asfalis.db')

if not enc_key:
    logger.error("FIELD_ENCRYPTION_KEY is not set. Aborting.")
    logger.error('Generate: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
    sys.exit(1)

if not hmac_key_val:
    logger.error("FIELD_HMAC_KEY is not set. Aborting.")
    logger.error('Generate: python3 -c "import secrets; print(secrets.token_hex(32))"')
    sys.exit(1)

from sqlalchemy import create_engine, text
from app.utils.encryption import encrypt, compute_hmac, is_encrypted

BATCH_SIZE = 100


def _safe_encrypt(value):
    if value is None:
        return None
    s = str(value)
    return s if is_encrypted(s) else encrypt(s)


def _encrypt_float(value):
    if value is None:
        return None
    s = str(value)
    if is_encrypted(s):
        return s
    try:
        return encrypt(repr(float(s)))
    except ValueError:
        return encrypt(s)


def _encrypt_json(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        s = json.dumps(value, ensure_ascii=False)
    else:
        s = str(value)
    return s if is_encrypted(s) else encrypt(s)


# ── Per-table migration functions ─────────────────────────────────────────────
# SQLAlchemy 2.x: use with conn.begin() as a context manager for explicit txns.

def migrate_users(engine):
    logger.info("Migrating 'users' table ...")
    updated = 0
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, full_name, email, phone, sos_message, fcm_token, profile_image_url FROM users"
        )).fetchall()

        for i, row in enumerate(rows):
            uid, full_name, email, phone, sos_msg, fcm, pic = row
            p_hmac = compute_hmac(phone) if (phone and not is_encrypted(str(phone))) else None
            e_hmac = compute_hmac(email) if (email and not is_encrypted(str(email))) else None
            conn.execute(text(
                """UPDATE users SET
                    full_name=:fn, email=:em, phone=:ph, sos_message=:sm,
                    fcm_token=:ft, profile_image_url=:pi,
                    phone_hmac=COALESCE(:phm, phone_hmac),
                    email_hmac=COALESCE(:ehm, email_hmac)
                   WHERE id=:id"""
            ), {
                'fn': _safe_encrypt(full_name), 'em': _safe_encrypt(email),
                'ph': _safe_encrypt(phone), 'sm': _safe_encrypt(sos_msg),
                'ft': _safe_encrypt(fcm), 'pi': _safe_encrypt(pic),
                'phm': p_hmac, 'ehm': e_hmac, 'id': uid,
            })
            updated += 1
            if updated % BATCH_SIZE == 0:
                conn.commit()
                logger.info("  users: %d rows committed", updated)

        conn.commit()
    logger.info("  users: %d rows total", updated)


def migrate_trusted_contacts(engine):
    logger.info("Migrating 'trusted_contacts' table ...")
    updated = 0
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, name, phone, email FROM trusted_contacts"
        )).fetchall()
        for row in rows:
            cid, name, phone, email = row
            p_hmac = compute_hmac(phone) if (phone and not is_encrypted(str(phone))) else None
            conn.execute(text(
                """UPDATE trusted_contacts SET
                    name=:nm, phone=:ph, email=:em,
                    phone_hmac=COALESCE(:phm, phone_hmac)
                   WHERE id=:id"""
            ), {'nm': _safe_encrypt(name), 'ph': _safe_encrypt(phone),
                'em': _safe_encrypt(email), 'phm': p_hmac, 'id': cid})
            updated += 1
            if updated % BATCH_SIZE == 0:
                conn.commit()
        conn.commit()
    logger.info("  trusted_contacts: %d rows", updated)


def migrate_connected_devices(engine):
    logger.info("Migrating 'connected_devices' table ...")
    updated = 0
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, device_name, device_mac FROM connected_devices"
        )).fetchall()
        for row in rows:
            did, dname, dmac = row
            m_hmac = compute_hmac(dmac) if (dmac and not is_encrypted(str(dmac))) else None
            conn.execute(text(
                """UPDATE connected_devices SET
                    device_name=:dn, device_mac=:dm,
                    mac_hmac=COALESCE(:mh, mac_hmac)
                   WHERE id=:id"""
            ), {'dn': _safe_encrypt(dname), 'dm': _safe_encrypt(dmac),
                'mh': m_hmac, 'id': did})
            updated += 1
            if updated % BATCH_SIZE == 0:
                conn.commit()
        conn.commit()
    logger.info("  connected_devices: %d rows", updated)


def migrate_device_bindings(engine):
    logger.info("Migrating 'user_device_bindings' table ...")
    updated = 0
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, device_imei FROM user_device_bindings"
        )).fetchall()
        for row in rows:
            bid, imei = row
            i_hmac = compute_hmac(imei) if (imei and not is_encrypted(str(imei))) else None
            conn.execute(text(
                "UPDATE user_device_bindings SET device_imei=:im, imei_hmac=COALESCE(:ih, imei_hmac) WHERE id=:id"
            ), {'im': _safe_encrypt(imei), 'ih': i_hmac, 'id': bid})
            updated += 1
        conn.commit()
    logger.info("  user_device_bindings: %d rows", updated)


def migrate_handset_requests(engine):
    logger.info("Migrating 'handset_change_requests' table ...")
    updated = 0
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, old_device_imei, new_device_imei FROM handset_change_requests"
        )).fetchall()
        for row in rows:
            hid, old_imei, new_imei = row
            ni_hmac = compute_hmac(new_imei) if (new_imei and not is_encrypted(str(new_imei))) else None
            conn.execute(text(
                """UPDATE handset_change_requests SET
                    old_device_imei=:oi, new_device_imei=:ni,
                    new_imei_hmac=COALESCE(:nih, new_imei_hmac)
                   WHERE id=:id"""
            ), {'oi': _safe_encrypt(old_imei), 'ni': _safe_encrypt(new_imei),
                'nih': ni_hmac, 'id': hid})
            updated += 1
        conn.commit()
    logger.info("  handset_change_requests: %d rows", updated)


def migrate_location_history(engine):
    logger.info("Migrating 'location_history' table ...")
    updated = 0
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, latitude, longitude, address, accuracy FROM location_history"
        )).fetchall()
        for row in rows:
            lid, lat, lng, addr, acc = row
            conn.execute(text(
                "UPDATE location_history SET latitude=:la, longitude=:lo, address=:ad, accuracy=:ac WHERE id=:id"
            ), {'la': _encrypt_float(lat), 'lo': _encrypt_float(lng),
                'ad': _safe_encrypt(addr), 'ac': _encrypt_float(acc), 'id': lid})
            updated += 1
            if updated % BATCH_SIZE == 0:
                conn.commit()
        conn.commit()
    logger.info("  location_history: %d rows", updated)


def migrate_sos_alerts(engine):
    logger.info("Migrating 'sos_alerts' table ...")
    updated = 0
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, latitude, longitude, address, sos_message, contacted_numbers FROM sos_alerts"
        )).fetchall()
        for row in rows:
            sid, lat, lng, addr, msg, contacts = row
            conn.execute(text(
                """UPDATE sos_alerts SET
                    latitude=:la, longitude=:lo, address=:ad, sos_message=:sm, contacted_numbers=:cn
                   WHERE id=:id"""
            ), {'la': _encrypt_float(lat), 'lo': _encrypt_float(lng),
                'ad': _safe_encrypt(addr), 'sm': _safe_encrypt(msg),
                'cn': _encrypt_json(contacts), 'id': sid})
            updated += 1
            if updated % BATCH_SIZE == 0:
                conn.commit()
        conn.commit()
    logger.info("  sos_alerts: %d rows", updated)


def migrate_user_settings(engine):
    logger.info("Migrating 'user_settings' table ...")
    updated = 0
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, emergency_number, sos_message FROM user_settings"
        )).fetchall()
        for row in rows:
            sid, enum_, smsg = row
            conn.execute(text(
                "UPDATE user_settings SET emergency_number=:en, sos_message=:sm WHERE id=:id"
            ), {'en': _safe_encrypt(enum_), 'sm': _safe_encrypt(smsg), 'id': sid})
            updated += 1
        conn.commit()
    logger.info("  user_settings: %d rows", updated)


def migrate_support_tickets(engine):
    logger.info("Migrating 'support_tickets' table ...")
    updated = 0
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, subject, message FROM support_tickets"
        )).fetchall()
        for row in rows:
            tid, subj, msg = row
            conn.execute(text(
                "UPDATE support_tickets SET subject=:su, message=:ms WHERE id=:id"
            ), {'su': _safe_encrypt(subj), 'ms': _safe_encrypt(msg), 'id': tid})
            updated += 1
        conn.commit()
    logger.info("  support_tickets: %d rows", updated)


def main():
    logger.info("Starting plaintext → encrypted data migration ...")
    logger.info("Database: %s", db_url.split('@')[-1] if '@' in db_url else db_url)

    engine = create_engine(db_url)

    migrate_users(engine)
    migrate_trusted_contacts(engine)
    migrate_connected_devices(engine)
    migrate_device_bindings(engine)
    migrate_handset_requests(engine)
    migrate_location_history(engine)
    migrate_sos_alerts(engine)
    migrate_user_settings(engine)
    migrate_support_tickets(engine)

    logger.info("")
    logger.info("✅  Migration complete — all rows encrypted.")


if __name__ == '__main__':
    main()
