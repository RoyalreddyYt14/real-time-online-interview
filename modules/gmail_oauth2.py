"""
Gmail OAuth2 (XOAUTH2) authentication helper.

This module handles generating, storing, and refreshing OAuth2 tokens for Gmail SMTP.
Instead of using a password or App Password, this authenticates using OAuth2.

Setup:
1. Create OAuth2 credentials in Google Cloud Console (credentials.json).
2. Set GMAIL_OAUTH2_CLIENT_ID, GMAIL_OAUTH2_CLIENT_SECRET, and GMAIL_OAUTH2_REDIRECT_URI env vars.
3. Run gmail_oauth2_generate_token.py to obtain and save a token.json.
4. Set GMAIL_OAUTH2_TOKEN_FILE to the path of token.json.
5. The email module will automatically use the token to authenticate.
"""

import json
import logging
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger("gmail_oauth2")

# Gmail SMTP scope for sending emails
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def get_gmail_oauth2_token(client_id: str, client_secret: str, redirect_uri: str, token_file: str) -> str:
    """
    Get a valid OAuth2 access token for Gmail, refreshing if necessary.

    Returns the access token string.
    Raises an exception if token cannot be obtained or refreshed.
    """
    token_path = Path(token_file)

    # Try to load existing token
    creds = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logger.debug("Loaded existing OAuth2 token from %s", token_file)
        except Exception as e:
            logger.warning("Failed to load OAuth2 token from %s: %s", token_file, e)

    # Refresh expired token or request new one
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            logger.info("Refreshed OAuth2 token for Gmail")
        except Exception as e:
            logger.error("Failed to refresh OAuth2 token: %s. User must re-authenticate.", e)
            raise
    elif not creds or not creds.valid:
        logger.error("No valid OAuth2 token found at %s. Run gmail_oauth2_generate_token.py to generate one.", token_file)
        raise ValueError(f"OAuth2 token not found or invalid at {token_file}")

    # Save updated token
    try:
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    except Exception as e:
        logger.warning("Failed to save refreshed token: %s", e)

    return creds.token


def generate_gmail_oauth2_token(client_id: str, client_secret: str, redirect_uri: str, token_file: str) -> str:
    """
    Interactively generate a new OAuth2 token for Gmail.
    Opens a browser for user to authorize the app.
    Saves token to token_file.
    Returns the access token.
    """
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uris": [redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        SCOPES,
    )

    creds = flow.run_local_server(port=0)
    logger.info("Generated new OAuth2 token for Gmail")

    # Save token
    token_path = Path(token_file)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with open(token_path, "w") as f:
        f.write(creds.to_json())
    logger.info("Saved OAuth2 token to %s", token_file)

    return creds.token
