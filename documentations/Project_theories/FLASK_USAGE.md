# Flask Usage: Asfalis Backend

This document details how the Flask framework is utilized in the Asfalis project, including the server configuration and core patterns.

## ⚙️ Server Configuration

### Development Server
In development, the backend is typically started using the built-in Flask development server:
- **Command**: `python wsgi.py` (which runs `app.run()`)
- **Port**: Default is `5001`.
- **Note**: The development server includes a debugger and reloader for fast iteration.

### Production Server
In production (Docker/Cloud), the application uses **Gunicorn**, a production-grade WSGI HTTP Server.
- **Command**: `gunicorn --log-level info --access-logfile - -w 1 --threads 4 --bind 0.0.0.0:5000 wsgi:app`
- **Configuration**: Uses 1 worker with 4 threads. This provides concurrency while managing resource consumption effectively.
- **Environment**: Environment variables (like `PORT`, `DATABASE_URL`) are loaded via `python-dotenv`.

---

## 🏗️ Core Flask Patterns

### 1. Application Factory (`create_app`)
The project uses the Application Factory pattern to initialize the app. This allows for easier testing and configuration switching.

**Signature:**
```python
def create_app(config_class=Config) -> Flask:
    """Initialize and configure the Flask application instance."""
```
- **File**: `app/__init__.py`
- **Purpose**: Creates the `Flask` instance, pulls configuration from `app/config.py`, initializes extensions, and registers blueprints.

### 2. Blueprints
The application is split into specialized modules using Blueprints.

**Signature:**
```python
auth_bp = Blueprint('auth', __name__)
```
- **Usage**: Groups related routes (e.g., `api/auth`, `api/sos`).
- **Registration**: `app.register_blueprint(auth_bp, url_prefix='/api/auth')`

---

## 🛠️ Key Methods & Signatures

### 1. Routing & Decorators
- **`@bp.route(rule, methods=['GET', 'POST', ...])`**
    - **Description**: Defines an endpoint.
    - **Example**: `@auth_bp.route('/login/phone', methods=['POST'])`
- **`@jwt_required(optional=False)`**
    - **Description**: Protects a route, requiring a valid JWT in the `Authorization` header.
    - **Example**: 
      ```python
      @sos_bp.route('/history', methods=['GET'])
      @jwt_required()
      def get_sos_history(): ...
      ```

### 2. Request Handling
- **`request.get_json(silent=False)`**
    - **Description**: Accesses the incoming JSON payload.
- **`request.args`**
    - **Description**: Accesses URL query parameters.
- **`request.headers`**
    - **Description**: Accesses HTTP headers.

### 3. Responses
- **`jsonify(*args, **kwargs)`**
    - **Description**: Converts Python dictionaries/lists into a JSON HTTP response with `application/json` mimetype.
    - **Signature**: `jsonify(success=True, data={"id": 1}) -> Response`
- **Error Handling**: Using `@app.errorhandler(code_or_exception)` to return standardized JSON error messages for 404, 500, etc.

---

## 🔗 Extension Integration

### 🧩 SQLAlchemy & Migrations
- **Initialization**: `db.init_app(app)`
- **Usage**: Database interactions via `db.session.add()`, `db.session.commit()`, and model queries like `User.query.filter_by(...)`.

### 🛡️ Flask-JWT-Extended
- **`create_access_token(identity, expires_delta=None, additional_claims=None)`**
    - Generates short-lived tokens for authenticated requests.
- **`get_jwt_identity()`**
    - Retrieves the user ID (stored in the token's `sub` claim) within a protected route.

### 🌐 Flask-SocketIO
- **Purpose**: Real-time websocket communication for location tracking.
- **Usage**: 
  ```python
  @socketio.on('join_sos')
  def handle_join(data): ...
  ```

### 🚦 Flask-Limiter
- **Usage**: Decorator to prevent brute-force attacks on sensitive endpoints.
- **Signature**: `@limiter.limit("5/15minutes")`
- **Applied to**: Registration, Login, and Password Reset routes.
