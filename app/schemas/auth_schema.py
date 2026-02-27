
from marshmallow import Schema, fields, validate


class PhoneRegisterSchema(Schema):
    full_name = fields.Str(required=True, validate=validate.Length(min=2))
    phone_number = fields.Str(required=True, validate=validate.Length(min=10))
    country = fields.Str(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))


class PhoneLoginSchema(Schema):
    phone_number = fields.Str(required=True, validate=validate.Length(min=10))
    password = fields.Str(required=True)


class VerifyPhoneOTPSchema(Schema):
    phone_number = fields.Str(required=True, validate=validate.Length(min=10))
    otp_code = fields.Str(required=True, validate=validate.Length(equal=6))


class ResendOTPSchema(Schema):
    phone_number = fields.Str(required=True, validate=validate.Length(min=10))


class ForgotPasswordSchema(Schema):
    phone_number = fields.Str(required=True, validate=validate.Length(min=10))


class RefreshTokenSchema(Schema):
    refresh_token = fields.Str(required=True)


class GoogleLoginSchema(Schema):
    id_token = fields.Str(required=True)
