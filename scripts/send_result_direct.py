import sys
import os
sys.path.insert(0, os.getcwd())
from app import app
from database.db import db
from models.user_model import User
from modules.email_utils import send_result_email

if len(sys.argv) < 3:
    print("Usage: send_result_direct.py <user_email> <recipient_email> [selection] [message]")
    sys.exit(2)

user_email = sys.argv[1]
recipient = sys.argv[2]
selection = sys.argv[3] if len(sys.argv) > 3 else 'selected'
message = sys.argv[4] if len(sys.argv) > 4 else 'Result sent by admin.'

with app.app_context():
    user = User.query.filter_by(email=user_email.lower()).first()
    if not user:
        print(f'User with email {user_email} not found')
        sys.exit(3)
    sent = send_result_email(user, recipient, selection, message)
    print('Sent:', sent)
    if not sent:
        sys.exit(4)
