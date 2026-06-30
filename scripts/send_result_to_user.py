"""Send result email to a user by email address using app context.

Usage:
  python scripts/send_result_to_user.py chennakesavareddy909@gmail.com

This script looks up the user in the database and calls the application's
`send_result_email()` helper. Run it from the repository root where the app
can be imported.
"""

import sys
import os

sys.path.insert(0, os.getcwd())

from app import app
from database.db import db
from models.user_model import User
from modules.email_utils import send_result_email, is_email_configured


def main(email_address: str):
    if not is_email_configured():
        print("Email sending is not configured. Check environment or .env file.")
        return 2

    with app.app_context():
        user = User.query.filter_by(email=(email_address or "").strip().lower()).first()
        if not user:
            print(f"User with email {email_address} not found in database.")
            return 3

        print(f"Found user: id={user.id}, name={user.name}, email={user.email}")

        # Default: mark as selected if not specified
        selection = "selected"
        message = "Result sent by admin via script."

        ok = send_result_email(user, user.email, selection, message)
        if ok:
            print("Result email sent successfully.")
            return 0
        else:
            print(
                "Failed to send result email. Check server logs and mail configuration."
            )
            return 4


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts\\send_result_to_user.py user@example.com")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
