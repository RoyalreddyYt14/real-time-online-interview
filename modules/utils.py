"""
Utility functions module for the Real-Time Online Interview system.
Common helper functions used across the application.
"""

import os
import logging
from functools import wraps
from flask import session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)


def allowed_file(filename, allowed_extensions):
    """
    Check if file has allowed extension.

    Args:
        filename: Filename to check
        allowed_extensions: Set of allowed extensions

    Returns:
        bool: True if allowed
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def save_uploaded_file(file, upload_folder, allowed_extensions):
    """
    Save uploaded file securely.

    Args:
        file: FileStorage object
        upload_folder: Path to upload folder
        allowed_extensions: Set of allowed extensions

    Returns:
        str: Saved filename or None if failed
    """
    if not file or not allowed_file(file.filename, allowed_extensions):
        return None

    filename = secure_filename(file.filename)
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)
    return filename


def login_required(f):
    """
    Decorator to require login for routes.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """
    Decorator to require admin role for routes.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def get_user_role():
    """
    Get current user role from session.

    Returns:
        str: 'admin', 'candidate', or None
    """
    return session.get("user_role") or session.get("role")


def calculate_percentage(part, total):
    """
    Calculate percentage safely.

    Args:
        part: Numerator
        total: Denominator

    Returns:
        float: Percentage rounded to 1 decimal
    """
    if total == 0:
        return 0.0
    return round((part / total) * 100, 1)


def login_required():
    """Check if user is logged in as candidate."""
    return get_user_role() == "candidate" and "user_id" in session


def is_admin():
    """Check if current user is admin."""
    return get_user_role() == "admin"


def extract_text(file_path):
    """
    Extract text from PDF file.

    Args:
        file_path: Path to PDF file

    Returns:
        str: Extracted text
    """
    text = ""
    try:
        reader = PdfReader(file_path)
        for page in reader.pages:
            text += page.extract_text() or ""
    except:
        pass
    return text


# Skills list for resume parsing
SKILLS_LIST = [
    "python",
    "java",
    "c",
    "c++",
    "html",
    "css",
    "javascript",
    "sql",
    "machine learning",
    "django",
    "flask",
    "react",
]


def extract_skills(text):
    """
    Extract skills from text based on predefined skills list.

    Args:
        text: Text to search for skills

    Returns:
        list: List of found skills
    """
    found = []
    text = text.lower()
    for skill in SKILLS_LIST:
        if skill in text:
            found.append(skill)
    return list(set(found))


def format_mmss(total_seconds: int) -> str:
    """
    Format total seconds into MM:SS format.

    Args:
        total_seconds: Total seconds to format

    Returns:
        str: Formatted time string
    """
    total_seconds = max(0, int(total_seconds))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def get_proctor_stop_file(user_id: int) -> str:
    """
    Get path to proctor stop flag file for user.

    Args:
        user_id: User ID

    Returns:
        str: Path to flag file
    """
    from modules.config import INSTANCE_DIR

    return os.path.join(INSTANCE_DIR, f"proctor_stop_{user_id}.flag")


def format_duration(seconds):
    """
    Format seconds into MM:SS string.

    Args:
        seconds: Time in seconds

    Returns:
        str: Formatted time
    """
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes:02d}:{remaining_seconds:02d}"


def safe_int(value, default=0):
    """
    Safely convert value to int.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        int: Converted value or default
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value, default=0.0):
    """
    Safely convert value to float.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        float: Converted value or default
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def truncate_text(text, max_length=100, suffix="..."):
    """
    Truncate text to max length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        str: Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def get_file_size_mb(filepath):
    """
    Get file size in MB.

    Args:
        filepath: Path to file

    Returns:
        float: Size in MB
    """
    try:
        size_bytes = os.path.getsize(filepath)
        return size_bytes / (1024 * 1024)
    except OSError:
        return 0.0


def validate_email(email):
    """
    Basic email validation.

    Args:
        email: Email string

    Returns:
        bool: True if valid format
    """
    import re

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def generate_unique_filename(original_filename, prefix=""):
    """
    Generate unique filename with timestamp.

    Args:
        original_filename: Original filename
        prefix: Optional prefix

    Returns:
        str: Unique filename
    """
    import time

    name, ext = os.path.splitext(original_filename)
    timestamp = int(time.time())
    return f"{prefix}{name}_{timestamp}{ext}"
