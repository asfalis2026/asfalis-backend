from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Optional, Tuple

import pytz
from pytz import BaseTzInfo

# Build lookup maps once so we can resolve country names to ISO codes
_COUNTRY_NAME_TO_CODE = {name.lower(): code for code, name in pytz.country_names.items()}


def _normalize_country(country: Optional[str]) -> Optional[str]:
    if not country:
        return None
    return country.strip().lower()


def _match_country_code(country: Optional[str]) -> Optional[str]:
    """Return the ISO country code that best matches the provided country name."""
    normalized = _normalize_country(country)
    if not normalized:
        return None

    if normalized in _COUNTRY_NAME_TO_CODE:
        return _COUNTRY_NAME_TO_CODE[normalized]

    # Attempt loose matching by removing punctuation and checking startswith
    normalized_simple = normalized.replace('.', '').replace(',', '')
    for name, code in _COUNTRY_NAME_TO_CODE.items():
        simple_name = name.replace('.', '').replace(',', '')
        if normalized_simple == simple_name:
            return code
        if normalized_simple in simple_name or simple_name in normalized_simple:
            return code

    return None


@lru_cache(maxsize=128)
def get_timezone_for_country(country: Optional[str]) -> BaseTzInfo:
    """Return a pytz timezone for the user's country with UTC fallback."""
    country_code = _match_country_code(country)
    if country_code:
        tz_names = pytz.country_timezones.get(country_code)
        if tz_names:
            return pytz.timezone(tz_names[0])
    return pytz.utc


def convert_utc_to_local(dt: Optional[datetime], country: Optional[str]) -> Optional[datetime]:
    """Convert a naive/UTC datetime to the user's local timezone."""
    if dt is None:
        return None

    tz = get_timezone_for_country(country)
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    else:
        dt = dt.astimezone(pytz.utc)
    return dt.astimezone(tz)


def format_datetime_for_response(dt: Optional[datetime], country: Optional[str]) -> Optional[str]:
    """Return ISO formatted string in user's timezone."""
    local_dt = convert_utc_to_local(dt, country)
    if not local_dt:
        return None
    return local_dt.isoformat()


def format_datetime_for_display(dt: Optional[datetime], country: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Return a human friendly string and timezone abbreviation for messages."""
    local_dt = convert_utc_to_local(dt, country)
    if not local_dt:
        return None, None
    display = local_dt.strftime('%b %d, %Y at %I:%M %p')
    return display, local_dt.tzname()
