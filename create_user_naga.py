from werkzeug.security import generate_password_hash
from app import app, db
from models.user_model import User

TEST_EMAIL = "naga@gmail.com"
TEST_PASSWORD = "naga@123"

with app.app_context():
    db.create_all()
    user = User.query.filter_by(email=TEST_EMAIL).first()
    if not user:
        user = User(
            name="Naga Test",
            email=TEST_EMAIL,
            password=generate_password_hash(TEST_PASSWORD),
            profile_completed=True,
            face_image='static/faces/naga_face.jpg',
        )
        db.session.add(user)
        db.session.commit()
        print(f"Created test user: {TEST_EMAIL} / {TEST_PASSWORD}")
    else:
        user.password = generate_password_hash(TEST_PASSWORD)
        user.profile_completed = True
        user.face_image = 'static/faces/naga_face.jpg'
        db.session.add(user)
        db.session.commit()
        print(f"Updated test user: {TEST_EMAIL}")
