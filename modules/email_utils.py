"""
Email utilities: lightweight SMTP wrapper for sending notifications.

This module centralizes email sending so configuration lives in
`modules.config` and the rest of the app can call simple helpers.

Supports both password-based auth and Gmail OAuth2 (XOAUTH2) token-based auth.
"""
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
import time
import traceback

from .config import (
    ENV_PATH,
    INSTANCE_DIR,
    ADMIN_EMAIL,
)

logger = logging.getLogger("email_utils")
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    email_log_file = INSTANCE_DIR / "email.log"
    try:
        email_handler = logging.FileHandler(email_log_file, encoding="utf-8")
        email_handler.setLevel(logging.DEBUG)
        email_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(email_handler)
    except Exception:
        pass


def _is_placeholder_value(value: str) -> bool:
    placeholder_tokens = [
        "your-email",
        "your-password",
        "your-app-password",
        "example.com",
        "your-gmail",
        "your-google-client-id",
        "your-google-client-secret",
        "gmail_token.json",
    ]
    if not value:
        return False
    lowered = value.strip().lower()
    return any(token in lowered for token in placeholder_tokens)


def _reload_env():
    """Reload .env values into os.environ for runtime email config updates."""
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
                    os.environ[key] = value
        except Exception:
            pass


def _load_smtp_config():
    """Load SMTP/Gmail auth config dynamically from environment."""
    _reload_env()
    from .config import (
        MAIL_SERVER,
        MAIL_PORT,
        MAIL_USE_TLS,
        MAIL_USE_SSL,
        MAIL_USERNAME,
        MAIL_PASSWORD,
        GMAIL_OAUTH2_ENABLED,
        GMAIL_OAUTH2_CLIENT_ID,
        GMAIL_OAUTH2_CLIENT_SECRET,
        GMAIL_OAUTH2_REDIRECT_URI,
        GMAIL_OAUTH2_TOKEN_FILE,
    )
    return {
        "MAIL_SERVER": MAIL_SERVER,
        "MAIL_PORT": MAIL_PORT,
        "MAIL_USE_TLS": MAIL_USE_TLS,
        "MAIL_USE_SSL": MAIL_USE_SSL,
        "MAIL_USERNAME": MAIL_USERNAME,
        "MAIL_PASSWORD": MAIL_PASSWORD,
        "GMAIL_OAUTH2_ENABLED": GMAIL_OAUTH2_ENABLED,
        "GMAIL_OAUTH2_CLIENT_ID": GMAIL_OAUTH2_CLIENT_ID,
        "GMAIL_OAUTH2_CLIENT_SECRET": GMAIL_OAUTH2_CLIENT_SECRET,
        "GMAIL_OAUTH2_REDIRECT_URI": GMAIL_OAUTH2_REDIRECT_URI,
        "GMAIL_OAUTH2_TOKEN_FILE": GMAIL_OAUTH2_TOKEN_FILE,
    }


smtp_config = _load_smtp_config()

if not smtp_config["MAIL_USERNAME"] or _is_placeholder_value(smtp_config["MAIL_USERNAME"]):
    logger.warning("MAIL_USERNAME is not configured or is still a placeholder. Email sending will fail until SMTP credentials are set.")
if not smtp_config["GMAIL_OAUTH2_ENABLED"] and (not smtp_config["MAIL_PASSWORD"] or _is_placeholder_value(smtp_config["MAIL_PASSWORD"])):
    logger.warning("MAIL_PASSWORD is not configured or is still a placeholder, and OAuth2 is disabled. Email sending is disabled.")


def get_email_config_issues() -> list:
    """Return a list of current email configuration issues."""
    smtp_config = _load_smtp_config()
    issues = []
    has_username = bool(smtp_config["MAIL_USERNAME"] and not _is_placeholder_value(smtp_config["MAIL_USERNAME"]))
    if not has_username:
        issues.append("MAIL_USERNAME or SMTP_USERNAME is not configured or is still a placeholder")

    if smtp_config["GMAIL_OAUTH2_ENABLED"]:
        if not smtp_config["GMAIL_OAUTH2_CLIENT_ID"] or _is_placeholder_value(smtp_config["GMAIL_OAUTH2_CLIENT_ID"]):
            issues.append("GMAIL_OAUTH2_CLIENT_ID is not configured or is still a placeholder")
        if not smtp_config["GMAIL_OAUTH2_CLIENT_SECRET"] or _is_placeholder_value(smtp_config["GMAIL_OAUTH2_CLIENT_SECRET"]):
            issues.append("GMAIL_OAUTH2_CLIENT_SECRET is not configured or is still a placeholder")
        if not smtp_config["GMAIL_OAUTH2_TOKEN_FILE"] or _is_placeholder_value(smtp_config["GMAIL_OAUTH2_TOKEN_FILE"]):
            issues.append("GMAIL_OAUTH2_TOKEN_FILE is not configured or is still a placeholder")
        elif not Path(smtp_config["GMAIL_OAUTH2_TOKEN_FILE"]).expanduser().exists():
            issues.append(f"Gmail OAuth2 token file not found at {smtp_config['GMAIL_OAUTH2_TOKEN_FILE']}")
    else:
        has_password = bool(smtp_config["MAIL_PASSWORD"] and not _is_placeholder_value(smtp_config["MAIL_PASSWORD"]))
        if not has_password:
            issues.append("MAIL_PASSWORD or SMTP_PASSWORD is not configured or is still a placeholder")

    return issues


def log_email_config_status() -> None:
    """Log email configuration status on startup."""
    issues = get_email_config_issues()
    if issues:
        logger.warning("Email configuration issues found: %s", "; ".join(issues))
    else:
        logger.info("Email sending is configured and ready.")


def is_email_configured() -> bool:
    """Return True when email sending is properly configured."""
    smtp_config = _load_smtp_config()
    if not smtp_config["MAIL_USERNAME"] or _is_placeholder_value(smtp_config["MAIL_USERNAME"]):
        return False
    if smtp_config["GMAIL_OAUTH2_ENABLED"]:
        if not smtp_config["GMAIL_OAUTH2_CLIENT_ID"] or _is_placeholder_value(smtp_config["GMAIL_OAUTH2_CLIENT_ID"]):
            return False
        if not smtp_config["GMAIL_OAUTH2_CLIENT_SECRET"] or _is_placeholder_value(smtp_config["GMAIL_OAUTH2_CLIENT_SECRET"]):
            return False
        if not smtp_config["GMAIL_OAUTH2_TOKEN_FILE"] or _is_placeholder_value(smtp_config["GMAIL_OAUTH2_TOKEN_FILE"]):
            return False
        return Path(smtp_config["GMAIL_OAUTH2_TOKEN_FILE"]).expanduser().exists()
    if not smtp_config["MAIL_PASSWORD"] or _is_placeholder_value(smtp_config["MAIL_PASSWORD"]):
        return False
    return True


def _get_oauth2_access_token():
    """Get OAuth2 access token for Gmail. Returns token string or raises exception."""
    smtp_config = _load_smtp_config()
    if not smtp_config["GMAIL_OAUTH2_ENABLED"]:
        raise ValueError("OAuth2 not enabled")

    if not smtp_config["GMAIL_OAUTH2_CLIENT_ID"] or not smtp_config["GMAIL_OAUTH2_CLIENT_SECRET"]:
        raise ValueError("OAuth2 credentials not set: GMAIL_OAUTH2_CLIENT_ID and GMAIL_OAUTH2_CLIENT_SECRET required")

    from .gmail_oauth2 import get_gmail_oauth2_token

    try:
        token = get_gmail_oauth2_token(
            smtp_config["GMAIL_OAUTH2_CLIENT_ID"],
            smtp_config["GMAIL_OAUTH2_CLIENT_SECRET"],
            smtp_config["GMAIL_OAUTH2_REDIRECT_URI"],
            smtp_config["GMAIL_OAUTH2_TOKEN_FILE"],
        )
        logger.debug("Obtained OAuth2 access token for Gmail")
        return token
    except Exception as e:
        logger.error("Failed to get OAuth2 token: %s", e)
        raise


def _send_mail_message(subject: str, body: str, recipient: str, sender: str = None) -> bool:
    smtp_config = _load_smtp_config()
    if not smtp_config["MAIL_USERNAME"] or _is_placeholder_value(smtp_config["MAIL_USERNAME"]):
        logger.warning("Email sender (MAIL_USERNAME or SMTP_USERNAME) not set or is a placeholder. Skipping send.")
        return False

    # Check for OAuth2 or password-based auth
    use_oauth2 = smtp_config["GMAIL_OAUTH2_ENABLED"]
    if use_oauth2:
        if not smtp_config["GMAIL_OAUTH2_CLIENT_ID"] or _is_placeholder_value(smtp_config["GMAIL_OAUTH2_CLIENT_ID"]):
            logger.warning("OAuth2 enabled but GMAIL_OAUTH2_CLIENT_ID is not configured or is a placeholder. Skipping send.")
            return False
        if not smtp_config["GMAIL_OAUTH2_CLIENT_SECRET"] or _is_placeholder_value(smtp_config["GMAIL_OAUTH2_CLIENT_SECRET"]):
            logger.warning("OAuth2 enabled but GMAIL_OAUTH2_CLIENT_SECRET is not configured or is a placeholder. Skipping send.")
            return False
        if not smtp_config["GMAIL_OAUTH2_TOKEN_FILE"] or _is_placeholder_value(smtp_config["GMAIL_OAUTH2_TOKEN_FILE"]):
            logger.warning("OAuth2 enabled but GMAIL_OAUTH2_TOKEN_FILE is not configured or is a placeholder. Skipping send.")
            return False
    else:
        if not smtp_config["MAIL_PASSWORD"] or _is_placeholder_value(smtp_config["MAIL_PASSWORD"]):
            logger.warning("Email password not set or is a placeholder and OAuth2 is not enabled. Skipping send.")
            return False

    msg = MIMEMultipart()
    msg["From"] = sender or smtp_config["MAIL_USERNAME"]
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    max_retries = 3
    backoff = 2
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug("Attempt %d sending email to %s via %s:%s (ssl=%s tls=%s oauth2=%s)", attempt, recipient, smtp_config["MAIL_SERVER"], smtp_config["MAIL_PORT"], smtp_config["MAIL_USE_SSL"], smtp_config["MAIL_USE_TLS"], use_oauth2)

            # Choose SSL vs TLS transport
            if smtp_config["MAIL_USE_SSL"]:
                server = smtplib.SMTP_SSL(smtp_config["MAIL_SERVER"], smtp_config["MAIL_PORT"], timeout=30)
            else:
                server = smtplib.SMTP(smtp_config["MAIL_SERVER"], smtp_config["MAIL_PORT"], timeout=30)
                if smtp_config["MAIL_USE_TLS"]:
                    server.starttls()

            # Authenticate using OAuth2 or password
            if use_oauth2:
                try:
                    access_token = _get_oauth2_access_token()
                    # XOAUTH2 format: "user=<email>\x01auth=Bearer <token>\x01\x01"
                    auth_string = f"user={smtp_config['MAIL_USERNAME']}\x01auth=Bearer {access_token}\x01\x01"
                    server.auth("XOAUTH2", lambda: auth_string)
                    logger.info("Authenticated to Gmail SMTP using OAuth2")
                except Exception as oauth_e:
                    logger.error("OAuth2 authentication failed: %s", oauth_e)
                    logger.debug(traceback.format_exc())
                    server.quit()
                    raise
            else:
                server.login(smtp_config["MAIL_USERNAME"], smtp_config["MAIL_PASSWORD"])
                logger.debug("Authenticated to SMTP using password")

            server.sendmail(msg["From"], recipient, msg.as_string())
            server.quit()
            logger.info("Email sent to %s: %s", recipient, subject)
            return True

        except smtplib.SMTPAuthenticationError as auth_e:
            # Authentication errors are not transient — stop retrying
            logger.error("SMTP authentication failed when sending to %s: %s", recipient, auth_e)
            if use_oauth2:
                logger.error("If using Gmail OAuth2, ensure GMAIL_OAUTH2_TOKEN_FILE is valid and not expired. Run gmail_oauth2_generate_token.py to refresh.")
            else:
                logger.error("If using Gmail, enable 2-Step Verification and use an App Password or configure a relay.")
            logger.debug(traceback.format_exc())
            return False
        except smtplib.SMTPException as smtp_e:
            logger.warning("SMTP error on attempt %d for %s: %s", attempt, recipient, smtp_e)
            logger.debug(traceback.format_exc())
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            logger.error("Exceeded retries sending email to %s", recipient)
            return False
        except Exception as e:
            logger.warning("Unexpected error on attempt %d sending to %s: %s", attempt, recipient, e)
            logger.debug(traceback.format_exc())
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            logger.error("Exceeded retries sending email to %s", recipient)
            return False


def send_login_notification(candidate_name: str, candidate_email: str) -> bool:
    """Send notification to admin when a candidate logs in."""
    subject = f"Candidate Login Notification - {candidate_name}"
    body = (
        f"A candidate has logged into the interview system.\n\n"
        f"Candidate Name: {candidate_name}\n"
        f"Candidate Email: {candidate_email}\n"
        f"Login Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "This is an automated notification."
    )
    return _send_mail_message(subject, body, ADMIN_EMAIL)


def send_result_email(user, recipient_email: str, selection: str, extra_message: str = "") -> bool:
    """Send interview result email to a candidate.

    Keeps the same simple contract used elsewhere in the app.
    """
    aptitude = max(0, min(getattr(user, "aptitude_score", 0) or 0, 20))
    technical = max(0, min(getattr(user, "technical_score", 0) or 0, 20))
    coding = max(0, min(getattr(user, "coding_score", 0) or 0, 40))
    hr = max(0, min(getattr(user, "hr_score", 0) or 0, 20))
    total = aptitude + technical + coding + hr

    subject = f"Interview Results - {getattr(user, 'name', 'Candidate')}: {total}/100"
    status_text = "Selected" if selection == "selected" or total >= 70 else "Rejected"

    candidate_name = getattr(user, 'name', '') or 'Candidate'
    interview_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    body = (
        f"Hello {candidate_name},\n\n"
        "Thank you for participating in our interview process. Below are your results: \n\n"
        f"Aptitude: {aptitude}/20\n"
        f"Technical: {technical}/20\n"
        f"Coding: {coding}/40\n"
        f"HR: {hr}/20\n\n"
        f"Total: {total}/100\n"
        f"Status: {status_text}\n\n"
    )

    if extra_message:
        body += f"Message from Admin: {extra_message}\n\n"

    body += (
        "Next steps: "
        + ("Our HR team will contact you with further details within 3 business days.\n\n" if status_text.lower() == 'selected' else "Thank you for your time. We encourage you to apply again in the future.\n\n")
    )

    body += (
        "If you have any questions, reply to this email or contact the recruiting team.\n\n"
        f"Interview Date/Time: {interview_time}\n\n"
        "Best regards,\n"
        "Recruiting Team"
    )

    return _send_mail_message(subject, body, recipient_email)
