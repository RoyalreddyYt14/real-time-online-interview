from database.db import db
from datetime import datetime, timezone


class WarningEvent(db.Model):
    __tablename__ = "warning_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), index=True, nullable=False
    )
    message = db.Column(db.String(200), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self):
        return f"<WarningEvent user_id={self.user_id} message={self.message}>"
