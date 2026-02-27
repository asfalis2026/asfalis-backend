
from flask import Blueprint, request, jsonify, current_app
from app.extensions import db, jwt, limiter
from app.models.user import User
from app.models.settings import UserSettings
from app.models.trusted_contact import TrustedContact
from app.models.revoked_token import RevokedToken
from app.utils.validators import validate_password
from app.utils.otp import generate_otp, store_otp, verify_otp
from app.schemas.auth_schema import (
    PhoneRegisterSchema, PhoneLoginSchema,
    RefreshTokenSchema, ResendOTPSchema,
    ForgotPasswordSchema, GoogleLoginSchema, VerifyPhoneOTPSchema
)
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jwt, decode_token
)
from flask_jwt_extended.exceptions import JWTDecodeError
from marshmallow import ValidationError
import bcrypt
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

# Expanded emergency numbers list
EMERGENCY_NUMBERS = {
    "India": "112",
    "United States": "911",
    "United Kingdom": "999",
    "Australia": "000",
    "Canada": "911",
    "China": "110",
    "Japan": "119",
    "Brazil": "190",
    "South Africa": "10111",
    "France": "112",
    "Germany": "112",
    "Mexico": "911",
    "United Arab Emirates": "999",
    "South Korea": "112",
    "Russia": "112",
    "USA": "911",
    "UK": "999",
    "Spain": "112",
    "Italy": "112",
    "Singapore": "995",
    "New Zealand": "111",
    "Israel": "100",
    "Pakistan": "15",
    "Nigeria": "112",
    "Argentina": "911",
    "Switzerland": "112",
    "Netherlands": "112",
    "Sweden": "112",
    "Norway": "112",
    "Greece": "112",
    "Ireland": "112",
    "Portugal": "112",
    "Turkey": "112",
    "Saudi Arabia": "999",
    "Egypt": "122",
    "Indonesia": "112",
    "Thailand": "191",
    "Malaysia": "999",
    "Philippines": "911",
    "Vietnam": "113",
}


def _make_tokens(user_id: str):
    """Return (access_token, refresh_token, sos_token, expires_in).

    sos_token is a long-lived access token (30 days by default) stored by
    the Android app and used ONLY for /sos/trigger.  This ensures emergency
    alerts always work even if the regular 15-minute access token has expired.
    """
    access_token = create_access_token(identity=user_id)
    refresh_token = create_refresh_token(identity=user_id)

    sos_days = current_app.config.get('JWT_SOS_TOKEN_EXPIRES_DAYS', 30)
    sos_token = create_access_token(
        identity=user_id,
        expires_delta=timedelta(days=sos_days),
        additional_claims={"token_purpose": "sos"}
    )
    expires_in = int(current_app.config['JWT_ACCESS_TOKEN_EXPIRES'].total_seconds())
    return access_token, refresh_token, sos_token, expires_in


def _extract_bearer(request_obj) -> str | None:
    """Return the raw token from the Authorization: Bearer header, or None."""
    header = request_obj.headers.get('Authorization', '')
    if header.startswith('Bearer '):
        return header[len('Bearer '):]
    return None


# ------------------------------------------------------------------ #
# Registration & Verification (phone-based, OTP sent by Android app) #
# ------------------------------------------------------------------ #

@auth_bp.route('/register/phone', methods=['POST'])
def register_phone():
    """Register a new user with phone number.

    The backend generates an OTP and returns it in the response.
    The Android app is responsible for sending this OTP to the user's
    phone via the built-in SmsManager (no server-side SMS cost).
    """
    schema = PhoneRegisterSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={
            "code": "VALIDATION_ERROR",
            "message": "Invalid request",
            "details": err.messages
        }), 400

    if User.query.filter_by(phone=data['phone_number']).first():
        return jsonify(success=False, error={
            "code": "CONFLICT",
            "message": "Phone number already registered"
        }), 409

    if not validate_password(data['password']):
        return jsonify(success=False, error={
            "code": "VALIDATION_ERROR",
            "message": "Password weak"
        }), 400

    hashed_pw = bcrypt.hashpw(
        data['password'].encode('utf-8'), bcrypt.gensalt()
    ).decode('utf-8')

    emergency_number = EMERGENCY_NUMBERS.get(data.get('country', ''), "112")

    new_user = User(
        full_name=data['full_name'],
        phone=data['phone_number'],
        country=data['country'],
        password_hash=hashed_pw,
        auth_provider='phone',
        is_verified=False
    )
    db.session.add(new_user)
    db.session.flush()

    # Create default settings
    default_settings = UserSettings(
        user_id=new_user.id, emergency_number=emergency_number
    )
    db.session.add(default_settings)

    # Generate OTP — returned to the app so the device can SMS it
    otp_code = generate_otp(length=6)
    store_otp(phone=new_user.phone, otp_code=otp_code, purpose='phone_verification')

    db.session.commit()

    return jsonify(success=True, message="Registration successful. OTP generated.", data={
        "phone_number": new_user.phone,
        "otp_code": otp_code,
        "expires_in": int(current_app.config.get('OTP_EXPIRY_SECONDS', 300))
    }), 201


@auth_bp.route('/verify-phone-otp', methods=['POST'])
def verify_phone_otp():
    """Verify the OTP sent to the user's phone number."""
    schema = VerifyPhoneOTPSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={
            "code": "VALIDATION_ERROR",
            "message": "Invalid request",
            "details": err.messages
        }), 400

    phone = data['phone_number']
    otp_code = data['otp_code']

    valid, msg = verify_otp(phone=phone, otp_code=otp_code, purpose='phone_verification')
    if not valid:
        return jsonify(success=False, error={
            "code": "OTP_INVALID",
            "message": msg
        }), 422

    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify(success=False, error={
            "code": "NOT_FOUND",
            "message": "User not found"
        }), 404

    user.is_verified = True
    db.session.commit()

    access_token, refresh_token, sos_token, expires_in = _make_tokens(user.id)

    return jsonify(success=True, data={
        "user_id": user.id,
        "full_name": user.full_name,
        "phone_number": user.phone,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "sos_token": sos_token,
        "expires_in": expires_in
    }, message="Phone verified successfully"), 200


# ------------------------------------------------------------------ #
# Login                                                               #
# ------------------------------------------------------------------ #

@auth_bp.route('/login/phone', methods=['POST'])
@limiter.limit("5/15minutes")
def login_phone():
    schema = PhoneLoginSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={
            "code": "VALIDATION_ERROR",
            "message": "Invalid request",
            "details": err.messages
        }), 400

    user = User.query.filter_by(phone=data['phone_number']).first()

    if not user or not user.password_hash:
        return jsonify(success=False, error={
            "code": "UNAUTHORIZED",
            "message": "Invalid credentials"
        }), 401

    if not bcrypt.checkpw(
        data['password'].encode('utf-8'),
        user.password_hash.encode('utf-8')
    ):
        return jsonify(success=False, error={
            "code": "UNAUTHORIZED",
            "message": "Invalid credentials"
        }), 401

    if not user.is_verified:
        return jsonify(success=False, error={
            "code": "PHONE_NOT_VERIFIED",
            "message": "Please verify your phone number before logging in."
        }), 403

    access_token, refresh_token, sos_token, expires_in = _make_tokens(user.id)

    return jsonify(success=True, data={
        "user_id": user.id,
        "full_name": user.full_name,
        "phone_number": user.phone,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "sos_token": sos_token,
        "expires_in": expires_in
    }), 200


# ------------------------------------------------------------------ #
# Token management                                                    #
# ------------------------------------------------------------------ #

@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """Exchange a valid refresh token for a new access + refresh token pair.

    Accepts the refresh token from:
      1. JSON body  { "refresh_token": "..." }   ← Android AuthInterceptor sends this
      2. Authorization: Bearer <token> header    ← legacy / curl usage

    Implements refresh token rotation: the presented refresh token is revoked
    immediately and a brand-new one is issued.  If the same token is presented
    again (e.g. parallel requests), the server returns REFRESH_TOKEN_REUSED.
    """
    body_data = request.get_json(silent=True) or {}
    token_str = body_data.get('refresh_token') or _extract_bearer(request)

    if not token_str:
        return jsonify(success=False, error={
            "code": "REFRESH_TOKEN_INVALID",
            "message": "Refresh token is required (body or Authorization header)."
        }), 401

    # Decode and validate the token
    try:
        decoded = decode_token(token_str)
    except JWTDecodeError as e:
        if 'expired' in str(e).lower():
            return jsonify(success=False, error={
                "code": "REFRESH_TOKEN_EXPIRED",
                "message": "Refresh token has expired. Please log in again."
            }), 401
        return jsonify(success=False, error={
            "code": "REFRESH_TOKEN_INVALID",
            "message": "Invalid refresh token."
        }), 401

    if decoded.get('type') != 'refresh':
        return jsonify(success=False, error={
            "code": "TOKEN_INVALID",
            "message": "Provided token is not a refresh token."
        }), 401

    jti = decoded.get('jti')
    identity = decoded.get('sub')

    # Rotation guard: fail if this refresh token was already used
    if RevokedToken.query.filter_by(jti=jti).first():
        return jsonify(success=False, error={
            "code": "REFRESH_TOKEN_REUSED",
            "message": "Refresh token has already been used. Please log in again."
        }), 401

    # Rotate: revoke the old refresh token, issue fresh pair
    db.session.add(RevokedToken(jti=jti, token_type='refresh'))

    access_token = create_access_token(identity=identity)
    new_refresh_token = create_refresh_token(identity=identity)
    expires_in = int(current_app.config['JWT_ACCESS_TOKEN_EXPIRES'].total_seconds())

    db.session.commit()

    return jsonify(success=True, data={
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "expires_in": expires_in
    }), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Invalidate the user's refresh token so it cannot be reused after logout.

    Accepts the refresh token (to revoke) from the JSON body:
      { "refresh_token": "..." }
    The access token in the Authorization header identifies the caller as usual.
    """
    body_data = request.get_json(silent=True) or {}
    refresh_token_str = body_data.get('refresh_token')

    if refresh_token_str:
        try:
            decoded = decode_token(refresh_token_str)
            jti = decoded.get('jti')
            if jti and not RevokedToken.query.filter_by(jti=jti).first():
                db.session.add(RevokedToken(jti=jti, token_type='refresh'))
                db.session.commit()
        except JWTDecodeError:
            pass

    return jsonify(success=True, message="Logged out successfully"), 200

@auth_bp.route('/validate', methods=['GET'])
@jwt_required()
def validate_token():
    current_user_id = get_jwt_identity()
    return jsonify(success=True, data={"user_id": current_user_id, "is_valid": True}), 200


# ------------------------------------------------------------------ #
# OTP helpers (resend / forgot password)                              #
# ------------------------------------------------------------------ #

@auth_bp.route('/resend-otp', methods=['POST'])
@limiter.limit("3/15minutes")
def resend_otp():
    """Resend a verification OTP for an unverified phone number.

    Returns the OTP in the response so the Android app can send it via SMS.
    """
    schema = ResendOTPSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={
            "code": "VALIDATION_ERROR",
            "message": "Invalid request",
            "details": err.messages
        }), 400

    phone = data['phone_number']

    user = User.query.filter_by(phone=phone).first()
    if not user:
        # Don't reveal whether the number is registered
        return jsonify(success=True, message="If the number is registered, a new OTP has been generated.", data={
            "expires_in": int(current_app.config.get('OTP_EXPIRY_SECONDS', 300))
        }), 200

    if user.is_verified:
        return jsonify(success=False, error={
            "code": "ALREADY_VERIFIED",
            "message": "Phone number is already verified."
        }), 400

    otp_code = generate_otp(length=6)
    store_otp(phone=phone, otp_code=otp_code, purpose='phone_verification')

    return jsonify(success=True, message="OTP generated successfully.", data={
        "otp_code": otp_code,
        "expires_in": int(current_app.config.get('OTP_EXPIRY_SECONDS', 300))
    }), 200


@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3/15minutes")
def forgot_password():
    """Generate a password-reset OTP for the given phone number.

    Returns the OTP so the Android app can send it to the user via SMS.
    """
    schema = ForgotPasswordSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={
            "code": "VALIDATION_ERROR",
            "message": "Invalid request",
            "details": err.messages
        }), 400

    phone = data['phone_number']
    user = User.query.filter_by(phone=phone).first()

    if not user:
        # Don't reveal whether the number is registered
        return jsonify(success=True, message="If an account exists, a reset OTP has been generated.", data={
            "expires_in": int(current_app.config.get('OTP_EXPIRY_SECONDS', 300))
        }), 200

    otp_code = generate_otp(length=6)
    store_otp(phone=phone, otp_code=otp_code, purpose='reset_password')

    return jsonify(success=True, message="Password reset OTP generated.", data={
        "otp_code": otp_code,
        "expires_in": int(current_app.config.get('OTP_EXPIRY_SECONDS', 300))
    }), 200


# ------------------------------------------------------------------ #
# Google OAuth (kept for future use — still mocked)                   #
# ------------------------------------------------------------------ #

@auth_bp.route('/google', methods=['POST'])
def google_auth():
    schema = GoogleLoginSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={
            "code": "VALIDATION_ERROR",
            "message": "Invalid request",
            "details": err.messages
        }), 400

    id_token = data['id_token']

    # TODO: Replace with real Google token verification
    email = "mock_google_user@gmail.com"
    full_name = "Google User"

    user = User.query.filter_by(email=email).first()
    is_new = False

    if not user:
        is_new = True
        user = User(
            full_name=full_name,
            email=email,
            auth_provider='google',
            is_verified=True
        )
        db.session.add(user)
        db.session.flush()

        db.session.add(UserSettings(user_id=user.id))
        db.session.commit()

    access_token, refresh_token, sos_token, expires_in = _make_tokens(user.id)

    return jsonify(success=True, data={
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "is_new_user": is_new,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "sos_token": sos_token,
        "expires_in": expires_in
    }, message="Login successful"), 200
