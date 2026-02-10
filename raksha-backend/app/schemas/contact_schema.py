
from marshmallow import Schema, fields, validate

class ContactSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=2))
    phone = fields.Str(required=True, validate=validate.Length(min=10))
    email = fields.Email(allow_none=True)
    relationship = fields.Str(allow_none=True)
    is_primary = fields.Bool(missing=False)
