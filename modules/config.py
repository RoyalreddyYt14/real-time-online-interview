"""
Configuration module for the Real-Time Online Interview system.
Centralizes all configuration settings and constants.
"""

import os
from pathlib import Path
from werkzeug.security import generate_password_hash

# Base paths
BASE_DIR = Path(__file__).parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Load local .env file if present, without overriding existing environment values
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    try:
        with ENV_PATH.open("r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass

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
INTERVIEW_DURATION_SECONDS = 2 * 60 * 60  # 2 hours
MAX_ATTEMPTS = 5

# Admin credentials (from environment or defaults)
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "kesavakunchala07@gmail.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Royalreddy@2001@")

# Hashed admin password (prefer setting ADMIN_PASSWORD_HASH in env for production).
# Support either a raw admin password or a pre-generated hashed password in the env.
admin_password_hash_env = os.environ.get("ADMIN_PASSWORD_HASH")
if admin_password_hash_env:
    if admin_password_hash_env.startswith(("pbkdf2:sha256:", "argon2:", "scrypt:")):
        ADMIN_PASSWORD_HASH = admin_password_hash_env
    else:
        ADMIN_PASSWORD_HASH = generate_password_hash(admin_password_hash_env)
else:
    ADMIN_PASSWORD_HASH = generate_password_hash(ADMIN_PASSWORD)

# Email / SMTP settings (can be provider-specific)
# Prefer explicit SMTP_* env vars; fall back to MAIL_* for compatibility.
MAIL_SERVER = os.environ.get("SMTP_SERVER", os.environ.get("MAIL_SERVER", "smtp.gmail.com"))
try:
    MAIL_PORT = int(os.environ.get("SMTP_PORT", os.environ.get("MAIL_PORT", "587")))
except Exception:
    MAIL_PORT = 587

# Support both STARTTLS (TLS) and SSL (SMTPS). Default to TLS on port 587.
MAIL_USE_TLS = os.environ.get("SMTP_USE_TLS", os.environ.get("MAIL_USE_TLS", "True")).lower() in (
    "1",
    "true",
    "yes",
)
MAIL_USE_SSL = os.environ.get("SMTP_USE_SSL", os.environ.get("MAIL_USE_SSL", "False")).lower() in (
    "1",
    "true",
    "yes",
)

# Credentials
MAIL_USERNAME = os.environ.get("SMTP_USERNAME", os.environ.get("MAIL_USERNAME"))
MAIL_PASSWORD = os.environ.get("SMTP_PASSWORD", os.environ.get("MAIL_PASSWORD"))

# Gmail OAuth2 (XOAUTH2) settings — use instead of MAIL_PASSWORD for Gmail
GMAIL_OAUTH2_ENABLED = os.environ.get("GMAIL_OAUTH2_ENABLED", "False").lower() in ("1", "true", "yes")
GMAIL_OAUTH2_CLIENT_ID = os.environ.get("GMAIL_OAUTH2_CLIENT_ID")
GMAIL_OAUTH2_CLIENT_SECRET = os.environ.get("GMAIL_OAUTH2_CLIENT_SECRET")
GMAIL_OAUTH2_REDIRECT_URI = os.environ.get("GMAIL_OAUTH2_REDIRECT_URI", "http://localhost:8080")
GMAIL_OAUTH2_TOKEN_FILE = os.environ.get("GMAIL_OAUTH2_TOKEN_FILE", "./gmail_token.json")

# Socket.IO settings
CORS_ALLOWED_ORIGINS = "*"

# ===========================
# OAUTH CREDENTIALS
# ===========================
# Get from environment variables. Set these in your deployment platform.
# For local development, create a .env file with these variables.

# Google OAuth
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

# GitHub OAuth
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")

# Microsoft OAuth
MICROSOFT_CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET", "")

# Application URL (for OAuth redirect)
APP_URL = os.environ.get("APP_URL", "http://localhost:5000")

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
