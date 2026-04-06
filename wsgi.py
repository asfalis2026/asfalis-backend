"""wsgi.py — entry point for uvicorn (replaces gunicorn + Flask wsgi.py)."""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO').strip().upper() or 'INFO',
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)

# Import the combined ASGI app (FastAPI + Socket.IO)
# socketio_app wraps the FastAPI app so that:
#   - All /socket.io/* routes → handled by Socket.IO
#   - All other routes         → handled by FastAPI
from app.main import socketio_app as app  # noqa: E402

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        'wsgi:app',
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 8000)),
        reload=os.environ.get('DEBUG', 'false').lower() == 'true',
        log_level='info',
    )
