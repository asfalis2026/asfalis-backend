
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from flask_mail import Mail
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

# Use threading mode for Socket.IO (eventlet has compatibility issues with Python 3.13)
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading') # Allow all origins for now
mail = Mail()
cors = CORS()
limiter = Limiter(key_func=get_remote_address, on_breach=lambda limit: None)
