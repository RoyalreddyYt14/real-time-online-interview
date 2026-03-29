from database.db import db
from datetime import datetime, timezone


class User(db.Model):

    __tablename__ = "users"

    # =========================
    # PRIMARY KEY
    # =========================
    id = db.Column(db.Integer, primary_key=True)

    # =========================
    # BASIC INFORMATION
    # =========================
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # =========================
    # CANDIDATE PROFILE INFO
    # =========================
    phone = db.Column(db.String(20))
    education = db.Column(db.String(100))
    experience = db.Column(db.String(100))

    # 🔥 UPDATED SKILLS (INCREASE SIZE)
    skills = db.Column(db.String(500))  # changed 200 → 500

    # 🔥 NEW RESUME FIELD
    resume = db.Column(db.String(200))  # stores path like resumes/file.pdf

    # =========================
    # FACE IMAGE (faces/filename.jpg)
    # =========================
    face_image = db.Column(db.String(200))

    # =========================
    # HR INTERVIEW ANSWERS
    # =========================
    hr_answer = db.Column(db.Text)

    # =========================
    # SCORES
    # =========================
    aptitude_score = db.Column(db.Integer, default=0)
    technical_score = db.Column(db.Integer, default=0)
    coding_score = db.Column(db.Integer, default=0)
    hr_score = db.Column(db.Integer, default=0)

    # =========================
    # CHEATING / WARNING SYSTEM 🔥
    # =========================
    warning_count = db.Column(db.Integer, default=0)
    last_warning = db.Column(db.String(200))

    # =========================
    # INTERVIEW PROGRESS
    # =========================
    aptitude_done = db.Column(db.Boolean, default=False)
    technical_done = db.Column(db.Boolean, default=False)
    coding_done = db.Column(db.Boolean, default=False)
    hr_done = db.Column(db.Boolean, default=False)

    # =========================
    # PROFILE STATUS
    # =========================
    profile_completed = db.Column(db.Boolean, default=False)

    # =========================
    # CREATED TIME
    # =========================
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # =========================
    # HELPER METHODS
    # =========================
    def total_score(self):
        return (
            (self.aptitude_score or 0)
            + (self.technical_score or 0)
            + (self.coding_score or 0)
            + (self.hr_score or 0)
        )

    def is_selected(self):
        return self.total_score() >= 70

    # =========================
    # DEBUG
    # =========================
    def __repr__(self):
        return f"<User {self.name}>"
