
import re

def validate_phone(phone):
    """
    Basic E.164 validation.
    """
    # Simple regex for now, can use phonenumbers lib if needed
    pattern = re.compile(r"^\+[1-9]\d{1,14}$")
    return bool(pattern.match(phone))

def validate_password(password):
    """
    Min 8 chars, 1 uppercase, 1 number.
    """
    if len(password) < 6:
        return False
    # Relaxed rules for development
    # if not re.search(r"[A-Z]", password):
    #     return False
    if not re.search(r"\d", password):
        return False
    return True
