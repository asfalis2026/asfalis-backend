
from marshmallow import Schema, fields, validate

class SettingsSchema(Schema):
    emergency_number = fields.Str(validate=validate.Length(min=3))
    sos_message = fields.Str(validate=validate.Length(max=500))
    shake_sensitivity = fields.Str(validate=validate.OneOf(["low", "medium", "high"]))
    battery_optimization = fields.Bool()
    haptic_feedback = fields.Bool()
