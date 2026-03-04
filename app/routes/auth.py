
from flask import Blueprint, request, jsonify, current_app
from app.extensions import db, jwt, limiter
from app.models.user import User
from app.models.settings import UserSettings
from app.models.trusted_contact import TrustedContact
from app.models.revoked_token import RevokedToken
from app.models.device_security import UserDeviceBinding, HandsetChangeRequest
from app.utils.validators import validate_password
from app.utils.otp import generate_otp, store_otp, verify_otp
from app.services.sms_service import send_otp_sms
from app.schemas.auth_schema import (
    PhoneRegisterSchema, PhoneLoginSchema,
    RefreshTokenSchema, ResendOTPSchema,
    ForgotPasswordSchema, GoogleLoginSchema, VerifyPhoneOTPSchema,
    ResetPasswordSchema
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


def _latest_handover_request(user_id: str, new_device_imei: str) -> HandsetChangeRequest | None:
    return HandsetChangeRequest.query.filter_by(
        user_id=user_id,
        new_device_imei=new_device_imei,
        status='pending'
    ).order_by(HandsetChangeRequest.requested_at.desc()).first()


def _begin_or_get_handover_request(user_id: str, old_device_imei: str | None, new_device_imei: str) -> HandsetChangeRequest:
    existing = _latest_handover_request(user_id, new_device_imei)
    if existing:
        return existing

    req = HandsetChangeRequest(
        user_id=user_id,
        old_device_imei=old_device_imei,
        new_device_imei=new_device_imei,
        status='pending',
        requested_at=datetime.utcnow(),
        eligible_at=datetime.utcnow() + timedelta(hours=12)
    )
    db.session.add(req)
    db.session.commit()
    return req


def _bind_user_to_device(user_id: str, device_imei: str):
    binding = UserDeviceBinding.query.filter_by(user_id=user_id).first()
    if not binding:
        binding = UserDeviceBinding(user_id=user_id, device_imei=device_imei)
        db.session.add(binding)
    else:
        binding.device_imei = device_imei
        binding.updated_at = datetime.utcnow()
    binding.last_login_at = datetime.utcnow()
    db.session.commit()


# ------------------------------------------------------------------ #
# Registration & Verification (phone-based, OTP sent via Twilio)     #
# ------------------------------------------------------------------ #

@auth_bp.route('/register/phone', methods=['POST'])
def register_phone():
    """Register a new user with phone number.

    The backend generates a 6-digit OTP, stores it in the DB, and sends
    it to the user's phone via Twilio Messaging (SMS). The OTP is NOT
    returned in the response — Twilio delivers it directly.
    """
    schema = PhoneRegisterSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(status="error", error_code="VALIDATION_ERROR",
                       message="Invalid request", details=err.messages), 400

    if User.query.filter_by(phone=data['phone_number']).first():
        return jsonify(status="error", error_code="CONFLICT",
                       message="This phone number is already registered."), 409

    if not validate_password(data['password']):
        return jsonify(status="error", error_code="VALIDATION_ERROR",
                       message="Password is too weak."), 400

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

    otp_code = generate_otp(length=6)
    store_otp(phone=new_user.phone, otp_code=otp_code, purpose='phone_verification')

    db.session.commit()

    sms_status = send_otp_sms(new_user.phone, otp_code)

    resp_data = {
        "phone_number": new_user.phone,
        "expires_in": int(current_app.config.get('OTP_EXPIRY_SECONDS', 300)),
        "sms_status": sms_status,
    }
    # In development mode expose the OTP so testing is possible without
    # a working Twilio account.
    if current_app.debug:
        resp_data["otp_code"] = otp_code

    return jsonify(status="success", message="OTP sent to your phone via SMS",
                   data=resp_data), 201


@auth_bp.route('/verify-phone-otp', methods=['POST'])
def verify_phone_otp():
    """Verify the OTP sent to the user's phone number."""
    schema = VerifyPhoneOTPSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(status="error", error_code="VALIDATION_ERROR",
                       message="Invalid request", details=err.messages), 400

    phone = data['phone_number']
    otp_code = data['otp_code']

    valid, msg = verify_otp(phone=phone, otp_code=otp_code, purpose='phone_verification')
    if not valid:
        return jsonify(status="error", error_code="OTP_INVALID", message=msg), 422

    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify(status="error", error_code="NOT_FOUND",
                       message="User not found"), 404

    user.is_verified = True
    db.session.commit()

    access_token, refresh_token, sos_token, expires_in = _make_tokens(user.id)

    return jsonify(status="success", message="Phone verified successfully", data={
        "user_id": user.id,
        "full_name": user.full_name,
        "phone_number": user.phone,
        "is_new_user": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "sos_token": sos_token,
        "expires_in": expires_in
    }), 200


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
        return jsonify(status="error", error_code="VALIDATION_ERROR",
                       message="Invalid request", details=err.messages), 400

    user = User.query.filter_by(phone=data['phone_number']).first()

    if not user or not user.password_hash:
        return jsonify(status="error", error_code="UNAUTHORIZED",
                       message="Invalid credentials"), 401

    if not bcrypt.checkpw(
        data['password'].encode('utf-8'),
        user.password_hash.encode('utf-8')
    ):
        return jsonify(status="error", error_code="UNAUTHORIZED",
                       message="Invalid credentials"), 401

    if not user.is_verified:
        return jsonify(status="error", error_code="PHONE_NOT_VERIFIED",
                       message="Please verify your phone number before logging in."), 403

    device_imei = (data.get('device_imei') or '').strip()
    confirm_handover = bool(data.get('confirm_handover', False))

    if device_imei and current_app.config.get('IMEI_BINDING_ENABLED', False):
        binding = UserDeviceBinding.query.filter_by(user_id=user.id).first()

        # First known login device for this account
        if not binding:
            _bind_user_to_device(user.id, device_imei)
        # Normal login from currently bound device
        elif binding.device_imei == device_imei:
            binding.last_login_at = datetime.utcnow()
            db.session.commit()
        # Different device: create/return a pending handset change request
        else:
            req = _begin_or_get_handover_request(
                user_id=user.id,
                old_device_imei=binding.device_imei,
                new_device_imei=device_imei,
            )

            if datetime.utcnow() < req.eligible_at:
                remaining_seconds = int((req.eligible_at - datetime.utcnow()).total_seconds())
                if remaining_seconds < 0:
                    remaining_seconds = 0
                return jsonify(
                    status="error",
                    error_code="HANDSET_CHANGE_PENDING",
                    message="Login blocked on new device. Handset transfer becomes available after 12 hours.",
                    data={
                        "request_id": req.id,
                        "eligible_at": req.eligible_at.isoformat() + "Z",
                        "remaining_seconds": remaining_seconds,
                        "confirm_handover_required": False,
                    }
                ), 403

            if not confirm_handover:
                return jsonify(
                    status="error",
                    error_code="HANDSET_CHANGE_CONFIRMATION_REQUIRED",
                    message="Handset transfer window is open. Re-submit login with confirm_handover=true to transfer account to this device.",
                    data={
                        "request_id": req.id,
                        "eligible_at": req.eligible_at.isoformat() + "Z",
                        "confirm_handover_required": True,
                    }
                ), 403

            # Finalize transfer to the new device
            _bind_user_to_device(user.id, device_imei)
            req.status = 'completed'
            req.completed_at = datetime.utcnow()
            db.session.commit()

    access_token, refresh_token, sos_token, expires_in = _make_tokens(user.id)

    response_data = {
        "user_id": user.id,
        "full_name": user.full_name,
        "phone_number": user.phone,
        "is_new_user": False,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "sos_token": sos_token,
        "expires_in": expires_in,
    }
    if device_imei:
        response_data["device_imei"] = device_imei
        response_data["device_binding_status"] = "BOUND"

    return jsonify(status="success", message="Login successful", data=response_data), 200


@auth_bp.route('/handset-change/status', methods=['POST'])
def handset_change_status():
    """Get pending handset transfer request status for a phone + device IMEI."""
    data = request.get_json(silent=True) or {}
    phone_number = data.get('phone_number')
    device_imei = (data.get('device_imei') or '').strip()

    if not phone_number or not device_imei:
        return jsonify(
            status="error",
            error_code="VALIDATION_ERROR",
            message="phone_number and device_imei are required"
        ), 400

    user = User.query.filter_by(phone=phone_number).first()
    if not user:
        return jsonify(status="error", error_code="NOT_FOUND", message="User not found"), 404

    req = _latest_handover_request(user.id, device_imei)
    if not req:
        return jsonify(status="success", data={"has_pending_request": False}), 200

    remaining_seconds = int((req.eligible_at - datetime.utcnow()).total_seconds())
    if remaining_seconds < 0:
        remaining_seconds = 0

    return jsonify(status="success", data={
        "has_pending_request": True,
        "request_id": req.id,
        "status": req.status,
        "eligible_at": req.eligible_at.isoformat() + "Z",
        "remaining_seconds": remaining_seconds,
        "confirm_handover_required": datetime.utcnow() >= req.eligible_at,
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
        return jsonify(status="error", error_code="REFRESH_TOKEN_INVALID",
                       message="Refresh token is required (body or Authorization header)."), 401

    # Decode and validate the token
    try:
        decoded = decode_token(token_str)
    except JWTDecodeError as e:
        if 'expired' in str(e).lower():
            return jsonify(status="error", error_code="REFRESH_TOKEN_EXPIRED",
                           message="Refresh token has expired. Please log in again."), 401
        return jsonify(status="error", error_code="REFRESH_TOKEN_INVALID",
                       message="Invalid refresh token."), 401

    if decoded.get('type') != 'refresh':
        return jsonify(status="error", error_code="TOKEN_INVALID",
                       message="Provided token is not a refresh token."), 401

    jti = decoded.get('jti')
    identity = decoded.get('sub')

    # Rotation guard: fail if this refresh token was already used
    if RevokedToken.query.filter_by(jti=jti).first():
        return jsonify(status="error", error_code="REFRESH_TOKEN_REUSED",
                       message="Refresh token has already been used. Please log in again."), 401

    # Rotate: revoke the old refresh token, issue fresh pair
    db.session.add(RevokedToken(jti=jti, token_type='refresh'))

    access_token = create_access_token(identity=identity)
    new_refresh_token = create_refresh_token(identity=identity)
    expires_in = int(current_app.config['JWT_ACCESS_TOKEN_EXPIRES'].total_seconds())

    db.session.commit()

    return jsonify(status="success", message="Token refreshed", data={
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

    return jsonify(status="success", message="Logged out successfully"), 200

@auth_bp.route('/validate', methods=['GET'])
@jwt_required()
def validate_token():
    current_user_id = get_jwt_identity()
    return jsonify(status="success", message="Token is valid",
                   data={"user_id": current_user_id, "is_valid": True}), 200


# ------------------------------------------------------------------ #
# OTP helpers (resend / forgot password)                              #
# ------------------------------------------------------------------ #

@auth_bp.route('/resend-otp', methods=['POST'])
@limiter.limit("3/15minutes")
def resend_otp():
    """Resend a verification OTP for an unverified phone number.

    Generates a fresh OTP, stores it in the DB, and sends it via
    Twilio Messaging. The code is NOT returned in the response.
    """
    schema = ResendOTPSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(status="error", error_code="VALIDATION_ERROR",
                       message="Invalid request", details=err.messages), 400

    phone = data['phone_number']

    user = User.query.filter_by(phone=phone).first()
    if not user:
        # Don't reveal whether the number is registered
        return jsonify(status="success",
                       message="If the number is registered, a new OTP will be sent.",
                       data={"expires_in": int(current_app.config.get('OTP_EXPIRY_SECONDS', 300))}), 200

    if user.is_verified:
        return jsonify(status="error", error_code="ALREADY_VERIFIED",
                       message="Phone number is already verified."), 400

    otp_code = generate_otp(length=6)
    store_otp(phone=phone, otp_code=otp_code, purpose='phone_verification')
    sms_status = send_otp_sms(phone, otp_code)

    resp_data = {
        "expires_in": int(current_app.config.get('OTP_EXPIRY_SECONDS', 300)),
        "sms_status": sms_status,
    }
    if current_app.debug:
        resp_data["otp_code"] = otp_code

    return jsonify(status="success", message="OTP resent via SMS",
                   data=resp_data), 200


@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3/15minutes")
def forgot_password():
    """Send a password-reset OTP via Twilio Messaging.

    Generates OTP, stores in DB, sends via Twilio SMS. The code is NOT
    returned in the response. Follow up with POST /reset-password.
    """
    schema = ForgotPasswordSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(status="error", error_code="VALIDATION_ERROR",
                       message="Invalid request", details=err.messages), 400

    phone = data['phone_number']
    user = User.query.filter_by(phone=phone).first()

    if not user:
        # Don't reveal whether the number is registered
        return jsonify(status="success",
                       message="If this number exists, an OTP will be sent.",
                       data={"expires_in": int(current_app.config.get('OTP_EXPIRY_SECONDS', 300))}), 200

    otp_code = generate_otp(length=6)
    store_otp(phone=phone, otp_code=otp_code, purpose='reset_password')
    sms_status = send_otp_sms(phone, otp_code)

    resp_data = {
        "expires_in": int(current_app.config.get('OTP_EXPIRY_SECONDS', 300)),
        "sms_status": sms_status,
    }
    if current_app.debug:
        resp_data["otp_code"] = otp_code

    return jsonify(status="success", message="Password reset OTP sent via SMS",
                   data=resp_data), 200


@auth_bp.route('/reset-password', methods=['POST'])
@limiter.limit("3/15minutes")
def reset_password():
    """Verify the Twilio OTP and set a new password.

    Use this after POST /forgot-password delivers the OTP to the user's phone.
    """
    schema = ResetPasswordSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(status="error", error_code="VALIDATION_ERROR",
                       message="Invalid request", details=err.messages), 400

    phone = data['phone_number']
    otp_code = data['otp_code']
    new_password = data['new_password']

    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify(status="error", error_code="NOT_FOUND",
                       message="User not found."), 404

    valid, msg = verify_otp(phone=phone, otp_code=otp_code, purpose='reset_password')
    if not valid:
        return jsonify(status="error", error_code="OTP_INVALID", message=msg), 422

    if not validate_password(new_password):
        return jsonify(status="error", error_code="VALIDATION_ERROR",
                       message="Password is too weak."), 400

    user.password_hash = bcrypt.hashpw(
        new_password.encode('utf-8'), bcrypt.gensalt()
    ).decode('utf-8')
    db.session.commit()

    return jsonify(status="success", message="Password reset successfully."), 200


# ------------------------------------------------------------------ #
# Google OAuth (kept for future use — still mocked)                   #
# ------------------------------------------------------------------ #

@auth_bp.route('/google', methods=['POST'])
def google_auth():
    schema = GoogleLoginSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(status="error", error_code="VALIDATION_ERROR",
                       message="Invalid request", details=err.messages), 400

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

    return jsonify(status="success", message="Google login successful", data={
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "is_new_user": is_new,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "sos_token": sos_token,
        "expires_in": expires_in
    }), 200
