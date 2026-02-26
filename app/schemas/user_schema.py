
from marshmallow import Schema, fields, validate

class UpdateProfileSchema(Schema):
    full_name = fields.Str(validate=validate.Length(min=2, max=100))
    phone = fields.Str(validate=validate.Length(min=10, max=20))
    sos_message = fields.Str(validate=validate.Length(min=1, max=500))
    profile_image_url = fields.Url()

class FCMTokenSchema(Schema):
    fcm_token = fields.Str(required=True)
