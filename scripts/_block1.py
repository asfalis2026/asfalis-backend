    if is_danger:
        # Block auto-SOS when only the uncalibrated file-fallback model is
        # loaded.  Only a DB-trained model (produced by /protection/train-model
        # on real user data) is reliable enough to trigger an emergency alert.
        if not _has_db_model():
            current_app.logger.warning(
                f"Auto SOS blocked for user {user_id}: no calibrated DB model. "
                "Complete calibration and run /protection/train-model first."
            )
            return {
                "alert_triggered": False,
                "confidence": confidence_danger,
                "message": "Auto SOS suspended: model not calibrated. Complete calibration first.",
                "trigger_reason": "model_not_calibrated"
            }

        # Fresh DB check — guards against race conditions where the user
        # disarmed between the top-of-function cache check and here.
        from app.models.settings import UserSettings
        fresh_settings = UserSettings.query.filter_by(user_id=user_id).first()
        if not (fresh_settings and fresh_settings.auto_sos_enabled):
            current_app.logger.info(
                f"Auto SOS suppressed for user {user_id}: "
                "system disarmed (fresh DB check caught race with cache)."
            )
            return {"alert_triggered": False, "confidence": confidence_danger,
                    "message": "Auto SOS suppressed: system is disarmed."}

        # Check cooldown before triggering SOS
        on_cooldown, secs_left = _is_on_cooldown(user_id)
        if on_cooldown:
            mins_left = (secs_left + 59) // 60
            return {
                "alert_triggered": False,
                "confidence": confidence_danger,
                "message": f"Auto SOS rate-limited. Next trigger allowed in {mins_left} min.",
                "retry_after_seconds": secs_left
            }

        # Resolve GPS coordinates
        from app.services.location_service import get_last_location
        last_loc = get_last_location(user_id)
        lat = last_loc.latitude if last_loc else 0.0
        lng = last_loc.longitude if last_loc else 0.0

        trigger_type = SENSOR_TRIGGER_MAP.get(sensor_type, "auto_fall")
        trigger_reason = (
            "Unusual fall detected" if sensor_type == "accelerometer"
            else "Unusual shake/motion detected"
        )
        # Embed the trigger reason in the alert's SOS message so it appears
        # in the WhatsApp notification when dispatch_sos is called.
        trigger_prefix = (
            f"⚠️ AUTO-SOS: {trigger_reason} ({int(confidence_danger * 100)}% confidence)\\n"
            f"Sensor: {sensor_type} | System was armed at time of trigger"
        )
        alert, msg = trigger_sos(user_id, lat, lng, trigger_type=trigger_type,
                                  trigger_prefix=trigger_prefix)
        _mark_sos_triggered(user_id)

        current_app.logger.warning(
            f"Auto SOS triggered for user {user_id}: {trigger_reason} "
            f"confidence={confidence_danger:.2f} sensor={sensor_type}"
        )

        # Dispatch immediately via the standard dispatch_sos path so that:
        # 1. Alert status transitions countdown -> sent (visible correctly in history)
        # 2. WhatsApp body includes the trigger reason (via trigger_prefix in sos_message)
        # 3. Delivery errors are captured in delivery_report
        delivery_report = []
        if alert:
            _, _, delivery_report = dispatch_sos(alert.id, user_id)

        return {
            "alert_triggered": True,
            "alert_id": alert.id if alert else None,
            "confidence": confidence_danger,
            "trigger_reason": trigger_reason,
            "delivery_report": delivery_report
        }

    return {"alert_triggered": False, "confidence": confidence_danger}
