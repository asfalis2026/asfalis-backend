# Dead Code - Unused SOS Service Functions
# These functions were never called and are kept here for reference only

from app.config import settings


def _get_configured_cooldown():
    """
    DEPRECATED: Was intended to fetch SOS cooldown from settings.
    Currently using hardcoded values in sos_service.py instead.
    """
    value = getattr(settings, 'SOS_COOLDOWN_SECONDS', None)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
