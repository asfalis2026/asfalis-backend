
import re
from marshmallow import Schema, fields, validate, ValidationError

_E164_RE = re.compile(r'^\+[1-9]\d{6,14}$')


def _validate_e164(value):
    if value and not _E164_RE.match(value):
        raise ValidationError(
            "Phone number must be in E.164 format (e.g. +919876543210)."
        )


class ContactSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=2))
    phone = fields.Str(required=True, validate=_validate_e164)
    email = fields.Email(allow_none=True, load_default=None)
    relationship = fields.Str(allow_none=True, load_default=None)
    is_primary = fields.Bool(load_default=False)
