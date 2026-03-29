from database.db import db
from datetime import datetime, timezone


class InterviewAttempt(db.Model):
    __tablename__ = "interview_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), index=True, nullable=False
    )
    attempt_number = db.Column(db.Integer, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    completed_at = db.Column(db.DateTime)

    def is_completed(self) -> bool:
        return self.completed_at is not None

    def __repr__(self):
        return (
            f"<InterviewAttempt user_id={self.user_id} attempt={self.attempt_number}>"
        )
