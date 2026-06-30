from werkzeug.security import generate_password_hash
from app import app, db
from models.user_model import User

TEST_EMAIL = "test_candidate@example.com"
TEST_PASSWORD = "TestPass123!"

with app.app_context():
    db.create_all()
    user = User.query.filter_by(email=TEST_EMAIL).first()
    if not user:
        user = User(
            name="Test Candidate",
            email=TEST_EMAIL,
            password=generate_password_hash(TEST_PASSWORD),
            profile_completed=True,
            face_image="",
        )
        db.session.add(user)
        db.session.commit()
        print(f"Created test user: {TEST_EMAIL} / {TEST_PASSWORD}")
    else:
        print(f"Test user already exists: {TEST_EMAIL}")
