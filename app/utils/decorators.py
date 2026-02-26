
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
