"""Send a custom result email without requiring a DB user.

Usage:
  python scripts/send_custom_result.py recipient@example.com [name]
"""

import sys
import os

sys.path.insert(0, os.getcwd())

from modules.email_utils import send_result_email, is_email_configured


class SimpleUser:
    def __init__(self, name="Candidate", aptitude=10, technical=10, coding=20, hr=10):
        self.name = name
        self.aptitude_score = aptitude
        self.technical_score = technical
        self.coding_score = coding
        self.hr_score = hr


def main(recipient, name=None):
    if not is_email_configured():
        print("Email sending is not configured. Check environment or .env file.")
        return 2

    user = SimpleUser(name or "Candidate")
    selection = (
        "selected"
        if (
            user.aptitude_score
            + user.technical_score
            + user.coding_score
            + user.hr_score
        )
        >= 70
        else "rejected"
    )
    message = "Result sent by admin (custom script)."

    sent = send_result_email(user, recipient, selection, message)
    print("Sent" if sent else "Failed to send")
    return 0 if sent else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python scripts\\send_custom_result.py recipient@example.com [name]"
        )
        sys.exit(1)
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
