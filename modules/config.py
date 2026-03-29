"""
Configuration module for the Real-Time Online Interview system.
Centralizes all configuration settings and constants.
"""

import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Ensure directories exist
INSTANCE_DIR.mkdir(exist_ok=True)
(STATIC_DIR / "resumes").mkdir(exist_ok=True)
(STATIC_DIR / "faces").mkdir(exist_ok=True)

# Database
DB_PATH = INSTANCE_DIR / "interview.db"
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"

# Flask settings
SECRET_KEY = "interview_secret_key"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Upload settings
UPLOAD_FOLDER = STATIC_DIR / "resumes"
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

# Interview settings
INTERVIEW_DURATION_SECONDS = 15 * 60  # 15 minutes
MAX_ATTEMPTS = 3

# Admin credentials (from environment or defaults)
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "chennakesava.edu.7@gmail.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Royalreddy@1431@")

# Socket.IO settings
CORS_ALLOWED_ORIGINS = "*"

# Scoring thresholds
SELECTION_THRESHOLD = 70  # Minimum total score to be selected

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Session settings
SESSION_TYPE = "filesystem"
SESSION_PERMANENT = False
SESSION_USE_SIGNER = True

# Security
WTF_CSRF_ENABLED = True
WTF_CSRF_SECRET_KEY = SECRET_KEY


def get_config_dict():
    """Return configuration as dictionary for Flask app.config.update()"""
    return {
        "SECRET_KEY": SECRET_KEY,
        "SQLALCHEMY_DATABASE_URI": SQLALCHEMY_DATABASE_URI,
        "SQLALCHEMY_TRACK_MODIFICATIONS": SQLALCHEMY_TRACK_MODIFICATIONS,
        "UPLOAD_FOLDER": str(UPLOAD_FOLDER),
        "MAX_CONTENT_LENGTH": MAX_CONTENT_LENGTH,
        "SESSION_TYPE": SESSION_TYPE,
        "SESSION_PERMANENT": SESSION_PERMANENT,
        "SESSION_USE_SIGNER": SESSION_USE_SIGNER,
        "WTF_CSRF_ENABLED": WTF_CSRF_ENABLED,
        "WTF_CSRF_SECRET_KEY": WTF_CSRF_SECRET_KEY,
    }
