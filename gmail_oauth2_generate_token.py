"""
gmail_oauth2_generate_token.py

Interactive script to generate an OAuth2 token for Gmail SMTP.
Run this once to authenticate, then the email module will use the saved token.

Setup before running:
1. Create a Google Cloud Console project
2. Create OAuth2 credentials (type: Desktop app / Installed app)
3. Download credentials.json from Google Cloud Console
4. Set environment variables:
   - GMAIL_OAUTH2_CLIENT_ID
   - GMAIL_OAUTH2_CLIENT_SECRET
   - GMAIL_OAUTH2_REDIRECT_URI (typically http://localhost:8080)
   - GMAIL_OAUTH2_TOKEN_FILE (path to save token, e.g. ./gmail_token.json)

Then run:
  python gmail_oauth2_generate_token.py

A browser will open for you to authorize. The token will be saved for future use.
"""

import os
import sys
import logging
from pathlib import Path

from modules.gmail_oauth2 import generate_gmail_oauth2_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    # Read environment variables
    client_id = os.environ.get("GMAIL_OAUTH2_CLIENT_ID")
    client_secret = os.environ.get("GMAIL_OAUTH2_CLIENT_SECRET")
    redirect_uri = os.environ.get("GMAIL_OAUTH2_REDIRECT_URI", "http://localhost:8080")
    token_file = os.environ.get("GMAIL_OAUTH2_TOKEN_FILE", "./gmail_token.json")

    if not client_id or not client_secret:
        print("Error: GMAIL_OAUTH2_CLIENT_ID and GMAIL_OAUTH2_CLIENT_SECRET environment variables are required.")
        print()
        print("Setup steps:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project (or select existing)")
        print("3. Enable Gmail API: APIs & Services > Enable APIs and services > search for Gmail > enable")
        print("4. Create OAuth2 credentials:")
        print("   - Go to APIs & Services > Credentials")
        print("   - Click 'Create Credentials' > 'OAuth client ID'")
        print("   - Choose 'Desktop app' as application type")
        print("   - Download the JSON file")
        print("5. Extract these values from the JSON:")
        print('   - "client_id" → set GMAIL_OAUTH2_CLIENT_ID')
        print('   - "client_secret" → set GMAIL_OAUTH2_CLIENT_SECRET')
        print("6. Optionally set GMAIL_OAUTH2_REDIRECT_URI (defaults to http://localhost:8080)")
        print("7. Optionally set GMAIL_OAUTH2_TOKEN_FILE (defaults to ./gmail_token.json)")
        sys.exit(1)

    print(f"Generating OAuth2 token for Gmail...")
    print(f"Client ID: {client_id[:20]}...")
    print(f"Redirect URI: {redirect_uri}")
    print(f"Token will be saved to: {token_file}")
    print()

    try:
        token = generate_gmail_oauth2_token(client_id, client_secret, redirect_uri, token_file)
        print()
        print("✓ Token generated and saved successfully!")
        print(f"✓ Token file: {token_file}")
        print()
        print("Next steps:")
        print(f"1. Set environment variable: GMAIL_OAUTH2_TOKEN_FILE={token_file}")
        print("2. Keep GMAIL_OAUTH2_CLIENT_ID and GMAIL_OAUTH2_CLIENT_SECRET set")
        print("3. The email module will automatically use the token for Gmail SMTP")
    except Exception as e:
        print()
        print(f"✗ Failed to generate token: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
