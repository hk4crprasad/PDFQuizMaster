import os
import logging
import json
from flask import Flask, Blueprint
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create and configure the app
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure upload folder
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get("MAX_CONTENT_LENGTH", 33554432))  # 32MB max upload size

# Create upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Configure CSRF protection
csrf = CSRFProtect(app)

# Initialize MongoDB and related extensions
from mongodb_config import init_mongo
init_mongo(app)

# Import and register routes
from routes import *
from auth import auth
app.register_blueprint(auth)

# Configure error handlers
from routes import page_not_found, server_error
app.register_error_handler(404, page_not_found)
app.register_error_handler(500, server_error)

# Custom template filters
from datetime import datetime

@app.template_filter('datetime')
def format_datetime(value, format='%b %d, %Y'):
    """Format a datetime to a pretty string"""
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            try:
                value = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f')
            except (ValueError, TypeError):
                return value
    return value.strftime(format)

if __name__ == '__main__':
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)