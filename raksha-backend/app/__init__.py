
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
    socketio.init_app(app)
    from app.sockets import location_socket # Register socket events
    mail.init_app(app)
    cors.init_app(app)
    limiter.init_app(app)

    # Initialize Celery
    from app.utils.celery_utils import celery_init_app
    celery_init_app(app)

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
        return jsonify({"status": "healthy", "service": "raksha-backend"}), 200

    
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
