
from marshmallow import Schema, fields, validate

class ToggleProtectionSchema(Schema):
    is_active = fields.Bool(required=True)

class SensorReadingSchema(Schema):
    x = fields.Float(required=True)
    y = fields.Float(required=True)
    z = fields.Float(required=True)
    timestamp = fields.Int(required=True)

class SensorDataSchema(Schema):
    sensor_type = fields.Str(required=True, validate=validate.OneOf(["accelerometer", "gyroscope"]))
    data = fields.List(fields.Nested(SensorReadingSchema), required=True)
    sensitivity = fields.Str(missing="medium")

class SensorWindowSchema(Schema):
    """Schema for the /predict endpoint.

    The frontend calls this endpoint **only** when the local sensor reading
    already exceeded the user-configured threshold.  The backend then runs
    the ML model and, if danger is predicted, triggers an Auto SOS countdown.
    """
    # Pre-filtered window of [x, y, z] readings
    window = fields.List(
        fields.List(fields.Float(), required=True),
        required=True,
        validate=validate.Length(min=3)
    )
    # Which sensor produced the reading
    sensor_type = fields.Str(
        missing='accelerometer',
        validate=validate.OneOf(['accelerometer', 'gyroscope'])
    )
    location = fields.Str(missing="Unknown")
    latitude = fields.Float(load_default=None, allow_none=True)
    longitude = fields.Float(load_default=None, allow_none=True)

class SensorTrainingSchema(Schema):
    sensor_type = fields.Str(required=True, validate=validate.OneOf(["accelerometer", "gyroscope"]))
    data = fields.List(fields.Nested(SensorReadingSchema), required=True)
    label = fields.Int(required=True, validate=validate.OneOf([0, 1])) # 0=Safe, 1=Danger
