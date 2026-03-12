    if prediction == 1:
        # Block auto-SOS when only the uncalibrated file-fallback model is loaded.
        if not _has_db_model():
            current_app.logger.warning(
                f"Auto SOS (predict) blocked for user {user_id}: no calibrated DB model."
            )
            response["sos_sent"] = False
            response["message"] = "Auto SOS suspended: model not calibrated. Complete calibration first."
            response["trigger_reason"] = "model_not_calibrated"
            return response

        # Fresh DB check — guards against the user disarming between the
        # top-of-function cache check and this point (race condition).
        from app.models.settings import UserSettings
        fresh_settings = UserSettings.query.filter_by(user_id=user_id).first()
        if not (fresh_settings and fresh_settings.auto_sos_enabled):
            current_app.logger.info(
                f"Auto SOS (predict) suppressed for user {user_id}: "
                "system disarmed (fresh DB check)."
            )
            response["sos_sent"] = False
            response["message"] = "Auto SOS suppressed: system is disarmed."
            return response

        # Check cooldown
        on_cooldown, secs_left = _is_on_cooldown(user_id)
        if on_cooldown:
            mins_left = (secs_left + 59) // 60
            response["sos_sent"] = False
            response["message"] = f"Auto SOS rate-limited. Next trigger allowed in {mins_left} min."
            response["retry_after_seconds"] = secs_left
            return response

        # Resolve coordinates: prefer device-supplied GPS, fall back to DB
        if latitude is not None and longitude is not None:
            lat, lng = latitude, longitude
        else:
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
        # in the WhatsApp notification when /send-now -> dispatch_sos fires.
        trigger_prefix = (
            f"⚠️ AUTO-SOS: {trigger_reason} ({int(confidence * 100)}% confidence)\\n"
            f"Sensor: {sensor_type} | Location: {location} | System was armed"
        )
        alert, msg = trigger_sos(user_id, lat, lng, trigger_type=trigger_type,
                                  trigger_prefix=trigger_prefix)
        _mark_sos_triggered(user_id)

        current_app.logger.warning(
            f"Auto SOS (predict) countdown started for user {user_id}: "
            f"{trigger_reason} confidence={confidence:.2f} sensor={sensor_type}"
        )

        # Do NOT dispatch (send WhatsApp) here.
        # The frontend receives the alert_id and shows a cancellation countdown.
        # If not cancelled, the frontend calls /sos/send-now which invokes
        # dispatch_sos — this ensures:
        #   • Alert status correctly transitions countdown -> sent in history
        #   • WhatsApp body includes the trigger reason (stored in sos_message)
        #   • No double-dispatch (contacts previously received TWO messages)
        response["sos_sent"] = True
        response["alert_id"] = alert.id if alert else None
        response["message"] = msg
        response["trigger_reason"] = trigger_reason
        response["countdown_seconds"] = current_app.config.get("SOS_COUNTDOWN_SECONDS", 10)

    else:
        response["sos_sent"] = False

    return response
