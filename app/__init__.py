
from flask import Flask, jsonify
from app.config import Config
from app.extensions import db, migrate, jwt, socketio, mail, cors, limiter

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so Alembic can detect them
    from app import models
    jwt.init_app(app)

    # ------------------------------------------------------------------ #
    # JWT error handlers — return structured error codes so the Android   #
    # app can distinguish expired vs. invalid vs. revoked tokens and act  #
    # accordingly (retry refresh vs. force logout vs. alert user).        #
    # ------------------------------------------------------------------ #

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        token_type = jwt_payload.get('type', 'access')
        if token_type == 'refresh':
            return jsonify(success=False, error={
                "code": "REFRESH_TOKEN_EXPIRED",
                "message": "Refresh token has expired. Please log in again."
            }), 401
        return jsonify(success=False, error={
            "code": "TOKEN_EXPIRED",
            "message": "Your session has expired. Please refresh your token."
        }), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error_string):
        return jsonify(success=False, error={
            "code": "TOKEN_INVALID",
            "message": "Invalid or malformed token. Please log in again."
        }), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error_string):
        return jsonify(success=False, error={
            "code": "UNAUTHORIZED",
            "message": "Authentication token is required."
        }), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify(success=False, error={
            "code": "REFRESH_TOKEN_REUSED",
            "message": "Token has been revoked. Please log in again."
        }), 401

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        """Only refresh tokens are tracked in the blocklist.

        Access tokens are short-lived (15 min) — blocklisting them would add
        a DB lookup to every single protected endpoint, which is unnecessary.
        """
        from app.models.revoked_token import RevokedToken
        if jwt_payload.get('type') == 'refresh':
            jti = jwt_payload.get('jti')
            return RevokedToken.query.filter_by(jti=jti).first() is not None
        return False

    socketio.init_app(app)
    from app.sockets import location_socket # Register socket events
    mail.init_app(app)
    cors.init_app(app)
    limiter.init_app(app)

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.user import user_bp
    from app.routes.contacts import contacts_bp
    from app.routes.sos import sos_bp
    from app.routes.location import location_bp
    from app.routes.settings import settings_bp
    from app.routes.device import device_bp
    from app.routes.support import support_bp
    from app.routes.protection import protection_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(user_bp, url_prefix='/api/user')
    app.register_blueprint(contacts_bp, url_prefix='/api/contacts')
    app.register_blueprint(sos_bp, url_prefix='/api/sos')
    app.register_blueprint(location_bp, url_prefix='/api/location')
    app.register_blueprint(settings_bp, url_prefix='/api/settings')
    app.register_blueprint(device_bp, url_prefix='/api/device')
    app.register_blueprint(support_bp, url_prefix='/api/support')
    app.register_blueprint(protection_bp, url_prefix='/api/protection')

    @app.route('/health')
    def health_check():
        db_status = "ok"
        try:
            db.session.execute(db.text("SELECT 1"))
        except Exception:
            db_status = "error"

        overall = "healthy" if db_status == "ok" else "degraded"
        return jsonify({
            "status": overall,
            "service": "Asfalis-backend",
            "auth": "ok",
            "database": db_status
        }), 200

    
    # Global Error Handlers
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(success=False, error={"code": "VALIDATION_ERROR", "message": str(e.description if hasattr(e, 'description') else e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify(success=False, error={"code": "UNAUTHORIZED", "message": "Authentication required"}), 401

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(success=False, error={"code": "NOT_FOUND", "message": "Resource not found"}), 404

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify(success=False, error={"code": "RATE_LIMITED", "message": "Too many requests. Try again later."}), 429

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify(success=False, error={"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}), 500

    return app
