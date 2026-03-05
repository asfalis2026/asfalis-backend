"""Quick smoke-test for every item in IOT_WEARABLE_BACKEND_CONTRACT.md."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv; load_dotenv()
from app import create_app
app = create_app()

with app.app_context():
    from app.extensions import db
    import inspect

    results = {}

    # 1. iot_button in DB enum
    rows = db.session.execute(db.text(
        "SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
        "WHERE pg_type.typname = 'trigger_type_enum' ORDER BY enumsortorder"
    )).fetchall()
    enum_vals = [r[0] for r in rows]
    results["1. iot_button in trigger_type_enum"] = "iot_button" in enum_vals

    # 2. trigger_type persisted (SOSAlert model has the column)
    from app.models.sos_alert import SOSAlert
    results["2. trigger_type column on SOSAlert"] = hasattr(SOSAlert, "trigger_type")

    # 3. /sos/trigger accepts iot_button (no whitelist validation)
    from app.routes.sos import trigger
    src_trigger = inspect.getsource(trigger)
    # Schema uses fields.Str() without OneOf — any string accepted
    from app.routes.sos import SOSTriggerSchema
    from marshmallow import fields as ma_fields
    schema_fields = SOSTriggerSchema().fields
    is_plain_str = isinstance(schema_fields.get("trigger_type"), ma_fields.String)
    results["3. trigger accepts any trigger_type string (no whitelist)"] = is_plain_str

    # 4. countdown_seconds in trigger response (expected by app)
    results["4. countdown_seconds in POST /sos/trigger response"] = "countdown_seconds" in src_trigger

    # 5. contacts_to_notify in trigger response (expected by app)
    results["5. contacts_to_notify in POST /sos/trigger response"] = "contacts_to_notify" in src_trigger

    # 6. cancel enforces ownership
    from app.services.sos_service import cancel_sos
    src_cancel = inspect.getsource(cancel_sos)
    results["6. cancel_sos enforces ownership"] = "alert.user_id != user_id" in src_cancel

    # 7. mark_user_safe handles both countdown and sent states
    from app.services.sos_service import mark_user_safe
    src_safe = inspect.getsource(mark_user_safe)
    results["7. mark_user_safe handles countdown + sent"] = "sent" in src_safe and "countdown" in src_safe

    # 8. history serialiser includes trigger_type
    from app.routes.sos import _serialize_sos_alert
    results["8. _serialize_sos_alert returns trigger_type"] = "trigger_type" in inspect.getsource(_serialize_sos_alert)

    print("\n=== IoT Backend Contract Check ===\n")
    all_pass = True
    for label, ok in results.items():
        status = "✅" if ok else "❌ MISSING"
        print(f"  {status}  {label}")
        if not ok:
            all_pass = False

    print()
    if all_pass:
        print("All items DONE ✅")
    else:
        print("Some items need attention ⚠️")
