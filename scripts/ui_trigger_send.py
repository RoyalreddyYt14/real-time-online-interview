"""Simulate admin clicking 'Send Result Email' via Flask test client.

Usage:
    python scripts/ui_trigger_send.py <user_email> [recipient_override]

This script sets `session['user_role']='admin'` and posts the form to
`/admin/user/<id>/send_result_email` to reproduce the UI flow and capture
server response and log entries.
"""
import sys
import os
import time

sys.path.insert(0, os.getcwd())

from app import app
from database.db import db
from models.user_model import User


def main(user_email, recipient=None):
    with app.app_context():
        user = User.query.filter_by(email=(user_email or "").strip().lower()).first()
        if not user:
            print(f"User {user_email} not found")
            return 2

    with app.test_client() as c:
        # Simulate admin session
        with c.session_transaction() as sess:
            sess["user_role"] = "admin"
            sess["role"] = "admin"

        data = {
            "email": recipient or user_email,
            "result": "selected",
            "message": "Test send from UI simulation",
        }

        url = f"/admin/user/{user.id}/send_result_email"
        print("POSTing to", url, "with", data)
        rv = c.post(url, data=data, follow_redirects=True)
        print("Response status:", rv.status)
        print("Response length:", len(rv.data or b""))
        if rv.data:
            print(rv.data.decode("utf-8")[:1000])

    # Wait briefly for log to flush
    time.sleep(1)
    log_path = os.path.join(os.getcwd(), "instance", "email.log")
    print("--- Last 50 lines of email.log ---")
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            for l in lines[-50:]:
                print(l)
    else:
        print("email.log not found")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/ui_trigger_send.py user@example.com [recipient_override]")
        sys.exit(1)
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
