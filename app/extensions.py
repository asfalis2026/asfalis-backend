
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from flask_mail import Mail
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import os

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

# Use threading for tests to avoid eventlet/python 3.13 issues
async_mode = 'threading' if os.environ.get('FLASK_TESTING') else None
socketio = SocketIO(cors_allowed_origins="*", async_mode=async_mode) # Allow all origins for now
mail = Mail()
cors = CORS()
limiter = Limiter(key_func=get_remote_address, on_breach=lambda limit: None)
