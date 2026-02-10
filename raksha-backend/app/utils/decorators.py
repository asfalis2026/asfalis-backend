
from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt
from marshmallow import ValidationError

def validate_schema(schema):
    """Decorator to validate request body against a Marshmallow schema."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import request
            try:
                data = schema.load(request.json)
            except ValidationError as err:
                return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request body", "details": err.messages}), 400
            return f(*args, **kwargs)
        return wrapper
    return decorator

def admin_required():
    """Decorator to require admin role (not implemented yet, placeholder)."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("role") != "admin":
                return jsonify(success=False, error={"code": "FORBIDDEN", "message": "Admins only!"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator
