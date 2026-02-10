
from flask import Blueprint, request, jsonify
from app.extensions import db, jwt, limiter
from app.models.user import User
from app.models.settings import UserSettings
from app.utils.validators import validate_password, validate_phone
from app.utils.otp import generate_otp, store_otp, verify_otp
from app.schemas.auth_schema import (
    EmailRegisterSchema, EmailLoginSchema, PhoneLoginSchema, 
    VerifyOTPSchema, RefreshTokenSchema, ResendOtpSchema,
    ForgotPasswordSchema, GoogleLoginSchema
)
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required, 
    get_jwt_identity, get_jwt
)
from marshmallow import ValidationError
import bcrypt
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register/email', methods=['POST'])
def register_email():
    schema = EmailRegisterSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify(success=False, error={"code": "CONFLICT", "message": "Email already exists"}), 409

    if not validate_password(data['password']):
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Password weak"}), 400

    hashed_pw = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    new_user = User(
        full_name=data['full_name'],
        email=data['email'],
        password_hash=hashed_pw,
        auth_provider='email',
        is_verified=False
    )
    db.session.add(new_user)
    db.session.flush() # Get ID

    # Create default settings
    default_settings = UserSettings(user_id=new_user.id)
    db.session.add(default_settings)
    
    db.session.commit()

    access_token = create_access_token(identity=new_user.id)
    refresh_token = create_refresh_token(identity=new_user.id)

    return jsonify(success=True, data={
        "user_id": new_user.id,
        "email": new_user.email,
        "access_token": access_token,
        "refresh_token": refresh_token
    }, message="Registration successful"), 201

@auth_bp.route('/login/email', methods=['POST'])
@limiter.limit("5/15minutes") 
def login_email():
    schema = EmailLoginSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not user.password_hash:
        return jsonify(success=False, error={"code": "UNAUTHORIZED", "message": "Invalid credentials"}), 401

    if not bcrypt.checkpw(data['password'].encode('utf-8'), user.password_hash.encode('utf-8')):
        return jsonify(success=False, error={"code": "UNAUTHORIZED", "message": "Invalid credentials"}), 401

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    return jsonify(success=True, data={
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "access_token": access_token,
        "refresh_token": refresh_token
    }), 200

@auth_bp.route('/send-otp', methods=['POST'])
@limiter.limit("3/15minutes")
def send_otp_route():
    schema = PhoneLoginSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    phone = data['phone']
    # In production remove this mock
    otp_code = generate_otp()
    
    # Store OTP
    store_otp(phone, otp_code, 'login')

    # Send SMS (Mock for now, would call SMS service)
    print(f"------------ OTP for {phone}: {otp_code} ------------")

    return jsonify(success=True, message="OTP sent successfully", data={"expires_in": 300}), 200

@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp_route():
    schema = VerifyOTPSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    phone = data['phone']
    otp_code = data['otp_code']

    valid, msg = verify_otp(phone, otp_code, 'login')
    if not valid:
        return jsonify(success=False, error={"code": "OTP_INVALID", "message": msg}), 422

    user = User.query.filter_by(phone=phone).first()
    is_new_user = False

    if not user:
        is_new_user = True
        user = User(
            full_name="New User", # Placeholder
            phone=phone,
            auth_provider='phone',
            is_verified=True
        )
        db.session.add(user)
        db.session.flush()
        
        default_settings = UserSettings(user_id=user.id)
        db.session.add(default_settings)
        db.session.commit()

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    return jsonify(success=True, data={
        "user_id": user.id,
        "is_new_user": is_new_user,
        "access_token": access_token,
        "refresh_token": refresh_token
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return jsonify(success=True, data={"access_token": access_token}), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # In a real app we'd blacklist the token in Redis here
    # jti = get_jwt()["jti"]
    # redis_client.set(jti, "", ex=Config.JWT_ACCESS_TOKEN_EXPIRES)
    return jsonify(success=True, message="Logged out successfully"), 200

@auth_bp.route('/validate', methods=['GET'])
@jwt_required()
def validate_token():
    current_user_id = get_jwt_identity()
    return jsonify(success=True, data={"user_id": current_user_id, "is_valid": True}), 200

@auth_bp.route('/resend-otp', methods=['POST'])
@limiter.limit("3/15minutes")
def resend_otp():
    schema = ResendOtpSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    phone = data['phone']
    # Check if user exists or if it's a new login flow? 
    # For now, just resend if valid phone format
    otp_code = generate_otp()
    store_otp(phone, otp_code, 'login')
    
    print(f"------------ RESENT OTP for {phone}: {otp_code} ------------")
    
    # Return same format as send-otp
    # OTP ID isn't currently used/returned by store_otp but could be added
    return jsonify(success=True, message="OTP resent successfully", data={"expires_in": 300}), 200

@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3/15minutes")
def forgot_password():
    schema = ForgotPasswordSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    email = data['email']
    user = User.query.filter_by(email=email).first()
    
    # Always return success to prevent user enumeration
    if user:
        # Generate token/link and send email
        # Mocking email sending for now
        print(f"--- PASSWORD RESET LINK SENT TO {email} ---")
    
    return jsonify(success=True, message="If an account exists, a reset link has been sent."), 200

@auth_bp.route('/google', methods=['POST'])
def google_auth():
    schema = GoogleLoginSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": "Invalid request", "details": err.messages}), 400

    id_token = data['id_token']
    
    # Verify ID token with Google (Mock for now)
    # In production:
    # from google.oauth2 import id_token as google_id_token
    # from google.auth.transport import requests
    # id_info = google_id_token.verify_oauth2_token(id_token, requests.Request(), GOOGLE_CLIENT_ID)
    
    # Mocking successful verification
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

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    return jsonify(success=True, data={
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "is_new_user": is_new,
        "access_token": access_token,
        "refresh_token": refresh_token
    }, message="Login successful"), 200
