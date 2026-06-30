from app import app, db
from models.user_model import User

TEST_EMAIL = "test_candidate@example.com"

with app.app_context():
    user = User.query.filter_by(email=TEST_EMAIL).first()
    if user:
        user.face_image = 'static/faces/test_face.jpg'
        user.profile_completed = True
        db.session.add(user)
        db.session.commit()
        print(f"Marked {TEST_EMAIL} as face-verified")
    else:
        print("Test user not found")
