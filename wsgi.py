from dotenv import load_dotenv
import os
import logging

# Load environment variables from .env file
load_dotenv()

# Configure logging so gunicorn workers propagate app-level logs
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    force=True,
)

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
