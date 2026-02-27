
from marshmallow import Schema, fields, validate

class EmailRegisterSchema(Schema):
    full_name = fields.Str(required=True, validate=validate.Length(min=2))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    country = fields.Str(required=True)

class EmailLoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)

class VerifyEmailOTPSchema(Schema):
    email = fields.Email(required=True)
    otp_code = fields.Str(required=True, validate=validate.Length(equal=6))

class RefreshTokenSchema(Schema):
    refresh_token = fields.Str(required=True)

class ForgotPasswordSchema(Schema):
    email = fields.Email(required=True)

class ResendEmailOtpSchema(Schema):
    email = fields.Email(required=True)

class GoogleLoginSchema(Schema):
    id_token = fields.Str(required=True)
