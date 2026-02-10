
from marshmallow import Schema, fields, validate

class EmailRegisterSchema(Schema):
    full_name = fields.Str(required=True, validate=validate.Length(min=2))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))

class EmailLoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)

class PhoneLoginSchema(Schema):
    phone = fields.Str(required=True, validate=validate.Length(min=10))

class VerifyOTPSchema(Schema):
    phone = fields.Str(required=True, validate=validate.Length(min=10))
    otp_code = fields.Str(required=True, validate=validate.Length(equal=4))

class RefreshTokenSchema(Schema):
    refresh_token = fields.Str(required=True)

class ForgotPasswordSchema(Schema):
    email = fields.Email(required=True)

class ResendOtpSchema(Schema):
    phone = fields.Str(required=True, validate=validate.Length(min=10))

class GoogleLoginSchema(Schema):
    id_token = fields.Str(required=True)
