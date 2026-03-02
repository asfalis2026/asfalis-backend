
import re
from marshmallow import Schema, fields, validate, validates, ValidationError

# E.164 format: + followed by 7–15 digits (ITU-T E.164 standard)
E164_RE = re.compile(r'^\+[1-9]\d{6,14}$')


def _validate_e164(value):
    if not E164_RE.match(value):
        raise ValidationError(
            "Phone number must be in E.164 format (e.g. +919876543210)."
        )


class PhoneRegisterSchema(Schema):
    full_name = fields.Str(required=True, validate=validate.Length(min=2))
    phone_number = fields.Str(required=True, validate=_validate_e164)
    country = fields.Str(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))


class PhoneLoginSchema(Schema):
    phone_number = fields.Str(required=True, validate=_validate_e164)
    password = fields.Str(required=True)


class VerifyPhoneOTPSchema(Schema):
    phone_number = fields.Str(required=True, validate=_validate_e164)
    otp_code = fields.Str(required=True, validate=validate.Length(equal=6))


class ResendOTPSchema(Schema):
    phone_number = fields.Str(required=True, validate=_validate_e164)


class ForgotPasswordSchema(Schema):
    phone_number = fields.Str(required=True, validate=_validate_e164)


class RefreshTokenSchema(Schema):
    refresh_token = fields.Str(required=True)


class GoogleLoginSchema(Schema):
    id_token = fields.Str(required=True)


class ResetPasswordSchema(Schema):
    phone_number = fields.Str(required=True, validate=validate.Length(min=10))
    otp_code = fields.Str(required=True, validate=validate.Length(equal=6))
    new_password = fields.Str(required=True, validate=validate.Length(min=8))
