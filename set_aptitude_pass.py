from app import app, db
from models.user_model import User

EMAIL = 'naga@gmail.com'
PASS_SCORE = 15

with app.app_context():
    user = User.query.filter_by(email=EMAIL).first()
    if not user:
        print('User not found')
    else:
        user.aptitude_score = PASS_SCORE
        user.aptitude_done = True
        db.session.add(user)
        db.session.commit()
        print(f'Set {EMAIL} aptitude_score={PASS_SCORE} and aptitude_done=True')
