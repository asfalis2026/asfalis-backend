
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
    Strong password validation:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character (optional but recommended)
    """
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    return True
