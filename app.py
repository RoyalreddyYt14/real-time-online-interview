import os
import re
import subprocess
import sys
import threading
import time
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    flash,
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PyPDF2 import PdfReader

from flask_socketio import SocketIO, join_room

from database.db import db
from models.user_model import User
from models.warning_event_model import WarningEvent
from models.interview_attempt_model import InterviewAttempt

# Technical question generator (skill-based)
from utils.question_generator import (
    generate_technical_questions,
    generate_aptitude_questions,
    generate_coding_questions,
    generate_hr_questions,
    load_question_bank,
    add_question,
)

# Admin utilities
from modules.admin_utils import calculate_admin_stats

# OAuth
from modules.oauth import oauth, init_oauth, get_oauth_user_info

# General utilities
from modules.utils import (
    admin_required,
    get_user_role,
    login_required,
    is_admin,
    allowed_file,
    extract_text,
    extract_skills,
    format_mmss,
    get_proctor_stop_file,
    generate_interview_suggestions,
)

app = Flask(__name__)

# =========================
# Logging
# =========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("interview_app")

# =========================
# SOCKET.IO (Real-time UI)
# =========================
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Interview settings
# INTERVIEW_DURATION_SECONDS = 2 * 60 * 60  # 2 hours
# MAX_ATTEMPTS = 3

from modules.config import (
    get_config_dict,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    ADMIN_PASSWORD_HASH,
    MAIL_SERVER,
    MAIL_PORT,
    MAIL_USE_TLS,
    MAIL_USERNAME,
    MAIL_PASSWORD,
    GMAIL_OAUTH2_ENABLED,
    GMAIL_OAUTH2_CLIENT_ID,
    GMAIL_OAUTH2_CLIENT_SECRET,
    GMAIL_OAUTH2_TOKEN_FILE,
    ALLOWED_EXTENSIONS,
    INTERVIEW_DURATION_SECONDS,
    MAX_ATTEMPTS,
    UPLOAD_FOLDER,
    INSTANCE_DIR,
    BASE_DIR,
)

app.config.update(get_config_dict())

# ===========================
# INITIALIZE OAUTH
# ===========================
init_oauth(app)

# Per-user in-memory session state (timer + status).
_session_states = {}  # user_id -> {time_left, started, ended}
_connected_user_ids = set()
_session_lock = threading.Lock()
_background_task_started = False


# Use centralized email helpers
from modules.email_utils import (
    send_login_notification,
    send_result_email,
    is_email_configured,
    log_email_config_status,
)

log_email_config_status()

# =========================
# DATABASE CONFIG
# =========================
# Keep SQLAlchemy aligned with the SQLite writes in:
# - face_detection.py
# - face_verification.py
# - voice_interview.py
db_path = os.path.join(INSTANCE_DIR, "interview.db")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path.replace("\\", "/")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# COUNT FUNCTION
def get_attempt_count(user_id):
    return InterviewAttempt.query.filter_by(user_id=user_id).count()


# 🔥 RESUME UPLOAD FOLDER
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)

db.init_app(app)

# Interview pass thresholds
MIN_APTITUDE_PASS_SCORE = 10
# Technical pass should allow reasonable, correct free-text answers rather than requiring near-perfect length.
MIN_TECHNICAL_PASS_SCORE = 20
MIN_CODING_PASS_SCORE = 20


def has_passed_aptitude(user: User) -> bool:
    return bool(
        user.aptitude_done and (user.aptitude_score or 0) >= MIN_APTITUDE_PASS_SCORE
    )


def has_passed_technical(user: User) -> bool:
    return bool(
        user.technical_done and (user.technical_score or 0) >= MIN_TECHNICAL_PASS_SCORE
    )


def has_passed_coding(user: User) -> bool:
    return bool(user.coding_done and (user.coding_score or 0) >= MIN_CODING_PASS_SCORE)


def has_failed_aptitude(user: User) -> bool:
    return bool(user.aptitude_done and not has_passed_aptitude(user))


def has_failed_technical(user: User) -> bool:
    return bool(user.technical_done and not has_passed_technical(user))


def has_failed_coding(user: User) -> bool:
    return bool(user.coding_done and not has_passed_coding(user))


def _ensure_profile_and_face_verified(user: User):
    """Require resume/profile completion and face verification before interview rounds."""
    if not user.profile_completed:
        flash(
            "Please complete your profile and upload your resume before starting the interview.",
            "warning",
        )
        return redirect(url_for("profile"))
    if not user.face_image:
        flash(
            "Please complete face verification before starting the interview.",
            "warning",
        )
        return redirect(url_for("face_verification"))
    return None


# =========================
# GLOBAL PROCESS HANDLING
# =========================
# Per-user processes so we can start/stop monitoring cleanly.
voice_processes = {}  # user_id -> Popen
proctor_processes = {}  # user_id -> Popen


# =========================
# LOGIN CHECK
# =========================
def sync_interview_status_from_db(user: User) -> str:
    """
    Convert DB progress flags into a stable interview_status for session gating.
    """
    if user.hr_done:
        return "completed"
    if user.aptitude_done or user.technical_done or user.coding_done:
        return "in_progress"
    return "not_started"


def check_warnings(user):
    # Be defensive: even though the model sets a default, existing DB rows
    # or partial records may still have NULL.
    return (user.warning_count or 0) >= 5


# =========================
# REAL-TIME SESSION STATE
# =========================
def _ensure_session_state(user: User) -> None:
    """
    Initialize per-user Socket.IO session state.
    """
    user_id = user.id
    with _session_lock:
        if user_id not in _session_states:
            _session_states[user_id] = {
                "time_left": INTERVIEW_DURATION_SECONDS,
                "started": False,
                "ended": False,
            }

        # If the candidate already progressed, consider the session started.
        st = _session_states[user_id]
        if (
            user.aptitude_done
            or user.technical_done
            or user.coding_done
            or user.hr_done
        ):
            st["started"] = True


def mark_interview_started(user_id: int) -> None:
    """
    Start (or resume) the countdown when proctoring begins.
    """
    with _session_lock:
        if user_id not in _session_states:
            _session_states[user_id] = {
                "time_left": INTERVIEW_DURATION_SECONDS,
                "started": True,
                "ended": False,
            }
        else:
            _session_states[user_id]["started"] = True


def _compute_interview_status(user: User, st: dict) -> str:
    if user.hr_done or st.get("ended"):
        return "Completed"
    if st.get("started"):
        return "Active"
    return "Waiting"


def _build_session_payload(user: User) -> dict:
    st = _session_states.get(user.id) or {
        "time_left": INTERVIEW_DURATION_SECONDS,
        "started": False,
        "ended": False,
    }

    recent_events = []
    try:
        # Latest warnings for non-intrusive UI messaging.
        recent_events = (
            WarningEvent.query.filter_by(user_id=user.id)
            .order_by(WarningEvent.created_at.desc())
            .limit(3)
            .all()
        )
    except Exception:
        recent_events = []

    interview_status = sync_interview_status_from_db(user)
    attempts_completed = get_attempt_count(user.id)

    payload = {
        # Used by the frontend badges.
        "status": _compute_interview_status(user, st),
        "time_left": format_mmss(st.get("time_left", INTERVIEW_DURATION_SECONDS)),
        "warnings": (
            [e.message for e in recent_events if e and e.message]
            if (user.warning_count or 0) > 0
            else []
        ),
        # Extra field used by the frontend to reliably detect new alerts.
        "warning_count": user.warning_count or 0,
        # Used by frontend redirects (guarded so it can't bounce on dashboard).
        "interview_status": interview_status,
        "can_retake": attempts_completed < MAX_ATTEMPTS,
        "connection": "Stable" if user.id in _connected_user_ids else "Offline",
        # Latest HR transcription: updated by server-side voice process.
        "hr_transcription": (
            (user.hr_answer or "") if hasattr(user, "hr_answer") else ""
        ),
    }
    return payload


# =========================
# PROCESS CONTROL
# =========================
def start_proctoring(user_id):
    existing = proctor_processes.get(user_id)
    if existing and existing.poll() is None:
        return

    try:
        script_path = os.path.join(BASE_DIR, "face_detection.py")
        stop_file = get_proctor_stop_file(user_id)
        # Clear any stop signal from a previous run.
        try:
            if os.path.exists(stop_file):
                os.remove(stop_file)
        except Exception:
            pass
        creationflags = 0
        startupinfo = None
        kwargs = {}

        # Windows: hide console window for silent monitoring.
        if os.name == "nt":
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        # Redirect stdout/stderr to keep logs silent.
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL

        proctor_processes[user_id] = subprocess.Popen(
            [sys.executable, script_path, str(user_id), stop_file],
            cwd=BASE_DIR,
            creationflags=creationflags,
            startupinfo=startupinfo,
            **kwargs,
        )
    except Exception:
        # Silent failure: UI still renders; monitoring may be missing.
        proctor_processes.pop(user_id, None)


def start_voice_interview(user_id):
    existing = voice_processes.get(user_id)
    if existing and existing.poll() is None:
        return

    try:
        script_path = os.path.join(BASE_DIR, "voice_interview.py")
        voice_processes[user_id] = subprocess.Popen(
            [sys.executable, script_path, str(user_id)],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            cwd=BASE_DIR,
        )
    except Exception:
        voice_processes.pop(user_id, None)


def stop_all_processes():
    # Stop every per-user process.
    for _uid, p in list(voice_processes.items()):
        try:
            if p and p.poll() is None:
                p.terminate()
        except Exception:
            pass
    for uid in list(proctor_processes.keys()):
        try:
            stop_proctoring(uid)
        except Exception:
            pass


def stop_proctoring(user_id: int) -> None:
    p = proctor_processes.get(user_id)
    stop_file = get_proctor_stop_file(user_id)

    # Signal the monitoring script to stop cleanly (releases webcam).
    try:
        with open(stop_file, "w", encoding="utf-8") as f:
            f.write(str(datetime.now(timezone.utc)))
    except Exception:
        pass

    if not p:
        return
    try:
        if p.poll() is None:
            # Give it a moment to observe the stop file and release resources.
            try:
                p.wait(timeout=3)
            except Exception:
                pass
        if p.poll() is None:
            # Last resort.
            p.terminate()
            try:
                p.wait(timeout=2)
            except Exception:
                pass
    except Exception:
        pass
    finally:
        proctor_processes.pop(user_id, None)


# =========================
# ATTEMPT HELPERS + RESET
# =========================
def _get_completed_attempt_count(user_id: int) -> int:
    try:
        return (
            InterviewAttempt.query.filter_by(user_id=user_id)
            .filter(InterviewAttempt.completed_at.isnot(None))
            .count()
        )
    except Exception:
        return 0


def _get_latest_attempt(user_id: int):
    try:
        return (
            InterviewAttempt.query.filter_by(user_id=user_id)
            .order_by(InterviewAttempt.attempt_number.desc())
            .first()
        )
    except Exception:
        return None


def _can_retake(user: User) -> bool:
    """
    Return True when the user may start a new attempt.

    Candidates may retry as long as they have not reached the maximum
    configured attempt count. Incomplete or interrupted attempts should
    not block a fresh restart.
    """
    total_attempts = get_attempt_count(user.id)
    return total_attempts < MAX_ATTEMPTS


def _mark_latest_attempt_completed(user: User) -> None:
    latest = _get_latest_attempt(user.id)
    if latest and latest.completed_at is None:
        latest.completed_at = datetime.now(timezone.utc)
        db.session.commit()


def _compute_technical_answer_score(answer: str) -> int:
    """Compute a fallback technical score from free-text answers."""
    if not answer:
        return 0

    text = answer.lower().strip()
    keyword_score = 0
    keywords = [
        "class",
        "object",
        "inheritance",
        "polymorphism",
        "encapsulation",
        "abstraction",
        "exception",
        "error",
        "function",
        "variable",
        "loop",
        "array",
        "pointer",
        "reference",
        "sql",
        "select",
        "where",
        "join",
        "query",
        "database",
        "html",
        "css",
        "javascript",
        "react",
        "django",
        "flask",
        "api",
        "rest",
        "server",
        "client",
        "async",
        "thread",
        "data",
        "model",
        "browser",
        "deployment",
        "testing",
        "bug",
        "debug",
        "version",
        "control",
        "git",
        "memory",
        "performance",
        "optimization",
        "backend",
        "frontend",
    ]

    for keyword in keywords:
        if keyword in text:
            keyword_score += 3

    length_score = (
        8
        if len(text) >= 100
        else (
            5
            if len(text) >= 75
            else 3 if len(text) >= 50 else 1 if len(text) >= 30 else 0
        )
    )
    completeness_score = (
        6
        if len(text.split()) >= 15
        else 4 if len(text.split()) >= 10 else 2 if len(text.split()) >= 6 else 0
    )

    score = min(20, keyword_score + length_score + completeness_score)
    return score


def _normalize_technical_score(raw_score: int, max_raw_score: int = 40) -> int:
    raw_score = max(0, int(raw_score or 0))
    if max_raw_score <= 40:
        return min(raw_score, 40)
    normalized = round((min(raw_score, max_raw_score) / max_raw_score) * 40)
    return max(0, min(normalized, 40))


def _compute_technical_score_from_answers(form_data) -> int:
    answers = [value for key, value in form_data.items() if key.startswith("answer_")]
    return sum(_compute_technical_answer_score(answer) for answer in answers)


def _compute_coding_score_from_answers(form_data) -> int:
    answers = [value for key, value in form_data.items() if key.startswith("answer_")]
    keyword_score = 0
    for answer in answers:
        text = (answer or "").lower()
        word_count = len(text.split())
        keyword_score += sum(
            3
            for keyword in [
                "def ",
                "return",
                "split(",
                "lower()",
                "for ",
                "if ",
                "in ",
                "function ",
                "filter(",
                "map(",
                "=>",
                "select",
                "from",
                "where",
                "join",
                "group by",
                "public",
                "static",
                "boolean",
                "std::",
                "string",
                "vector",
                "<form",
                "<input",
                "<img",
                "<table",
                "<a",
                "useState",
                "render(request",
                "models.Model",
            ]
            if keyword in text
        )
        length_score = min(20, len(text) // 30)
        completeness_score = 5 if word_count >= 10 else 0
        keyword_score += length_score + completeness_score

    return min(100, keyword_score)


def _is_blank_answer(answer: str) -> bool:
    if answer is None:
        return True
    normalized = str(answer).strip()
    return not normalized or normalized == "(no transcript captured)"


def _compute_hr_answer_score(answer: str) -> int:
    """Score a single HR answer on a 0-20 scale."""
    if _is_blank_answer(answer):
        return 0

    text = str(answer).strip()
    word_count = len(re.findall(r"\b\w+\b", text))
    sentences = re.findall(r"[^\r\n.!?]+[.!?]+", text)
    sentence_count = len(sentences) if sentences else 1

    keywords = [
        "project",
        "experience",
        "team",
        "challenge",
        "learn",
        "skill",
        "role",
        "problem",
        "feedback",
        "deadline",
        "communication",
        "collaborate",
        "improve",
        "result",
        "success",
        "goal",
        "motivation",
        "customer",
        "impact",
        "leadership",
        "responsibility",
        "adapt",
        "culture",
        "company",
    ]
    relevance_hits = sum(1 for keyword in keywords if keyword in text.lower())
    relevance_score = min(5, relevance_hits * 2)

    if word_count <= 3:
        base_score = min(5, 2 + word_count)
    elif sentence_count == 1:
        base_score = 6 + min(4, max(0, (word_count - 6) // 5))
    elif sentence_count <= 3:
        base_score = 11 + min(4, max(0, (word_count - 12) // 8))
    else:
        base_score = 16 + min(4, max(0, (word_count - 25) // 10))

    completeness_bonus = 0
    if word_count >= 25 and sentence_count >= 2:
        completeness_bonus += 1
    if word_count >= 35 and sentence_count >= 3:
        completeness_bonus += 1
    if word_count >= 50 and sentence_count >= 4:
        completeness_bonus += 1

    score = base_score + relevance_score + completeness_bonus
    if sentence_count >= 3 and relevance_hits >= 3 and word_count >= 35:
        score = max(score, 18)
    if sentence_count >= 4 and relevance_hits >= 4 and word_count >= 45:
        score = max(score, 19)
        if word_count >= 55:
            score = max(score, 20)

    return max(0, min(20, score))


def _compute_hr_score_from_answers(raw_answers) -> int:
    if not raw_answers:
        return 0
    scores = [_compute_hr_answer_score(answer) for answer in raw_answers]
    if not scores:
        return 0
    return max(0, min(20, round(sum(scores) / len(scores))))


def _get_current_attempt_number(user: User) -> int:
    latest = _get_latest_attempt(user.id)
    return latest.attempt_number if latest else 1


def reset_interview_state_for_new_attempt(user: User) -> None:
    """
    Reset per-round flags/scores + warnings + timer for a new attempt.
    """
    # Keep camera monitoring running across rounds so proctoring feels continuous.
    # Previously we stopped proctoring here which caused gaps between rounds.
    # Do not stop the proctor process when resetting internal state.

    # Reset DB progress flags/scores for a fresh attempt.
    user.aptitude_score = 0
    user.technical_score = 0
    user.coding_score = 0
    user.hr_score = 0

    user.aptitude_done = False
    user.technical_done = False
    user.coding_done = False
    user.hr_done = False
    user.hr_answer = None

    # Reset warnings.
    user.warning_count = 0
    user.last_warning = None

    try:
        WarningEvent.query.filter_by(user_id=user.id).delete()
    except Exception:
        pass

    # Reset socket timer for UI.
    with _session_lock:
        _session_states[user.id] = {
            "time_left": INTERVIEW_DURATION_SECONDS,
            "started": False,
            "ended": False,
        }

    db.session.commit()


def start_new_attempt(user: User) -> InterviewAttempt:
    """
    Create attempt row and reset interview state.
    """
    total_attempts = get_attempt_count(user.id)
    if total_attempts >= MAX_ATTEMPTS:
        raise ValueError("Max attempts reached")

    latest = _get_latest_attempt(user.id)
    next_attempt_number = 1 if latest is None else latest.attempt_number + 1

    reset_interview_state_for_new_attempt(user)

    attempt = InterviewAttempt(user_id=user.id, attempt_number=next_attempt_number)
    db.session.add(attempt)
    db.session.commit()

    session["attempt_id"] = attempt.id
    session["attempt_number"] = attempt.attempt_number

    # Ensure background proctoring is running for this user.
    try:
        start_proctoring(user.id)
    except Exception:
        pass

    return attempt


def ensure_first_attempt_exists(user: User) -> None:
    """
    If user has no attempts created yet, create attempt #1 (without rolling back if already in progress).
    """
    latest = _get_latest_attempt(user.id)
    if latest is not None:
        session["attempt_id"] = latest.id
        session["attempt_number"] = latest.attempt_number
        return

    # First attempt: create row. If the user is already mid-interview,
    # do not destroy their current progress.
    has_progress = bool(
        user.aptitude_done or user.technical_done or user.coding_done or user.hr_done
    )
    if not has_progress:
        reset_interview_state_for_new_attempt(user)

    attempt = InterviewAttempt(user_id=user.id, attempt_number=1)
    db.session.add(attempt)
    db.session.commit()
    session["attempt_id"] = attempt.id
    session["attempt_number"] = attempt.attempt_number


# =========================
# SOCKET.IO BACKGROUND LOOP
# =========================
def _background_emit_loop():
    # Keep DB ops inside app context for Flask-SQLAlchemy.
    with app.app_context():
        while True:
            socketio.sleep(1)

            with _session_lock:
                user_ids = list(_session_states.keys())

            for user_id in user_ids:
                user = db.session.get(User, user_id)
                if not user:
                    continue

                _ensure_session_state(user)

                with _session_lock:
                    st = _session_states.get(user_id, {})
                    status = _compute_interview_status(user, st)

                    # Decrement timer only while the session is active.
                    if (
                        status == "Active"
                        and not st.get("ended")
                        and int(st.get("time_left", 0)) > 0
                    ):
                        st["time_left"] = int(st["time_left"]) - 1
                        if st["time_left"] <= 0:
                            st["time_left"] = 0
                            st["ended"] = True
                            # Best-effort cleanup (project currently uses global processes).
                            stop_proctoring(user_id)
                            # Auto-end interview: mark completion so results can render.
                            try:
                                user.aptitude_done = True
                                user.technical_done = True
                                user.coding_done = True
                                user.hr_done = True
                                # Mark latest attempt completed.
                                try:
                                    latest = _get_latest_attempt(user.id)
                                    if latest and latest.completed_at is None:
                                        latest.completed_at = datetime.now(timezone.utc)
                                except Exception:
                                    pass
                                db.session.commit()
                            except Exception:
                                pass

                    # If the session is completed, lock timer at 0.
                    if _compute_interview_status(user, st) == "Completed":
                        st["time_left"] = 0

                    payload = _build_session_payload(user)

                # Emit only to connected clients.
                if user_id in _connected_user_ids:
                    socketio.emit("session_update", payload, room=f"user_{user_id}")


# =========================
# SESSION AUDIT + SYNC
# =========================
@app.before_request
def session_audit_and_sync():
    """
    Keep session-based gating stable and log role/interview status.
    (No redirect logic here to avoid routing loops.)
    """
    role = get_user_role()

    if role == "candidate" and "user_id" in session:
        try:
            user = db.session.get(User, session["user_id"])
            if user:
                # ✅ DO NOT override when starting new attempt
                if session.get("interview_status") != "not_started":
                    session["interview_status"] = sync_interview_status_from_db(user)

                # Keep background camera monitoring alive while the interview is active.
                if session.get("interview_status") == "in_progress":
                    start_proctoring(user.id)
            else:
                session.pop("user_id", None)
                session.pop("user_role", None)
                session.pop("role", None)
                session.pop("interview_status", None)
        except Exception:
            # Don't block page render if sync fails.
            pass

    if role in ("candidate", "admin"):
        logger.info(
            "Request path=%s role=%s interview_status=%s user_id=%s",
            request.path,
            role,
            session.get("interview_status"),
            session.get("user_id"),
        )


# =========================
# HOME
# =========================
@app.route("/")
def home():
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    if login_required():
        return redirect(url_for("dashboard"))
    return render_template("welcome.html")


# =========================
# REGISTER
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirmPassword", "")
        agreed = request.form.get("terms")

        if not name or not email or not password:
            flash("Name, email, and password are required.", "warning")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "warning")
            return render_template("register.html")

        if not agreed:
            flash("You must agree to the Terms & Conditions.", "warning")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash(
                "Email already exists. Please login or use a different email.",
                "warning",
            )
            return render_template("register.html")

        # Store a hashed password instead of plaintext
        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
        )

        db.session.add(user)
        db.session.commit()

        session["user_id"] = user.id
        session["user_role"] = "candidate"
        session["role"] = "candidate"
        session["interview_status"] = "not_started"
        return redirect(url_for("dashboard"))

    return render_template("register.html")


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        # Lookup by email, then verify hashed password
        user = User.query.filter_by(
            email=(request.form.get("email") or "").strip().lower()
        ).first()
        if user and check_password_hash(
            user.password or "", request.form.get("password", "")
        ):
            session["user_id"] = user.id
            session["user_role"] = "candidate"
            session["role"] = "candidate"
            session["interview_status"] = sync_interview_status_from_db(user)
            # Send login notification to admin
            threading.Thread(
                target=send_login_notification, args=(user.name, user.email)
            ).start()
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
        return render_template("login.html")

    return render_template("login.html")


# ===========================
# OAUTH LOGIN ROUTES
# ===========================
@app.route("/auth/<provider>")
def oauth_authorize(provider):
    """Redirect to OAuth provider for authorization."""
    if provider not in ["google", "github", "microsoft"]:
        return "Invalid provider", 400

    redirect_uri = url_for("oauth_callback", provider=provider, _external=True)
    client = oauth.create_client(provider)
    return client.authorize_redirect(redirect_uri)


@app.route("/auth/callback/<provider>")
def oauth_callback(provider):
    """Handle OAuth callback from provider."""
    if provider not in ["google", "github", "microsoft"]:
        return "Invalid provider", 400

    try:
        client = oauth.create_client(provider)
        token = client.authorize_access_token()

        # Get user info from provider
        user_info = get_oauth_user_info(provider, token)

        if not user_info.get("email"):
            return "Unable to get email from provider", 400

        email = user_info["email"]
        name = user_info.get("name", email.split("@")[0])

        # Check if user already exists
        user = User.query.filter_by(email=email).first()

        if not user:
            # Create new user from OAuth info. Use a hashed placeholder password.
            user = User(
                name=name,
                email=email,
                password=generate_password_hash(f"oauth_{provider}_{int(time.time())}"),
            )
            db.session.add(user)
            db.session.commit()

        # Set session
        session["user_id"] = user.id
        session["user_role"] = "candidate"
        session["role"] = "candidate"
        session["interview_status"] = sync_interview_status_from_db(user)
        session["oauth_provider"] = provider

        # Send login notification
        threading.Thread(
            target=send_login_notification, args=(user.name, user.email)
        ).start()

        return redirect(url_for("dashboard"))

    except Exception as e:
        logger.error(f"OAuth callback error for {provider}: {str(e)}")
        return f"Authentication failed: {str(e)}", 500


# =========================
@app.route("/dashboard")
def dashboard():
    if is_admin():
        return redirect(url_for("admin_dashboard"))

    user = None
    attempt_number = 1
    can_retake = False

    # ✅ Proper login check
    step = 0

    if "user_id" in session:
        user = db.session.get(User, session.get("user_id"))

        if not user:
            session.clear()
            user = None
        else:
            can_retake = _can_retake(user)
            attempt_number = _get_current_attempt_number(user)
            session["attempt_number"] = attempt_number

            aptitude_passed = has_passed_aptitude(user)
            technical_passed = has_passed_technical(user)
            coding_passed = has_passed_coding(user)

            aptitude_failed = has_failed_aptitude(user)
            technical_failed = has_failed_technical(user)
            coding_failed = has_failed_coding(user)

            if aptitude_failed:
                step = 1
            elif not user.aptitude_done or not aptitude_passed:
                step = 1
            elif technical_failed:
                step = 2
            elif not user.technical_done or not technical_passed:
                step = 2
            elif coding_failed:
                step = 3
            elif not user.coding_done or not coding_passed:
                step = 3
            elif not user.hr_done:
                step = 4

    return render_template(
        "dashboard.html",
        user=user,
        attempt_number=attempt_number,
        next_attempt_number=(attempt_number + 1 if can_retake else attempt_number),
        max_attempts=MAX_ATTEMPTS,
        can_retake=can_retake,
        step=step,
        aptitude_passed=aptitude_passed if user else False,
        technical_passed=technical_passed if user else False,
        coding_passed=coding_passed if user else False,
        aptitude_failed=aptitude_failed if user else False,
        technical_failed=technical_failed if user else False,
        coding_failed=coding_failed if user else False,
    )


@app.route("/retake")
def retake_interview():
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    if not login_required():
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])
    if user:
        logger.info("Retake button clicked for user_id=%s", user.id)

    return redirect(url_for("restart_interview"))


# =========================
# PROFILE (🔥 RESUME LOGIC HERE)
# =========================
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    if not login_required():
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])

    if request.method == "POST":
        user.phone = (request.form.get("phone") or "").strip()
        user.education = (request.form.get("education") or "").strip()
        user.experience = (request.form.get("experience") or "").strip()

        # 🔥 RESUME UPLOAD
        file = request.files.get("resume")

        if file and file.filename != "":
            if not allowed_file(file.filename, ALLOWED_EXTENSIONS):
                flash("Resume must be a PDF, DOC, or DOCX file.", "warning")
                return render_template("profile.html", user=user)

            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            user.resume = "resumes/" + filename
            text = extract_text(filepath)
            skills = extract_skills(text)
            user.skills = ",".join(skills)

        user.profile_completed = True
        db.session.commit()

        flash("Profile updated successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("profile.html", user=user)


# =========================
# FACE VERIFICATION
# =========================
@app.route("/face_verification")
def face_verification():
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    if not login_required():
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])

    if not user.profile_completed:
        return redirect(url_for("profile"))

    try:
        script_path = os.path.join(BASE_DIR, "face_verification.py")
        log_path = os.path.join(BASE_DIR, "instance", "face_verification.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as log_file:
            subprocess.Popen(
                [sys.executable, script_path, str(user.id)],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=BASE_DIR,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
    except Exception as e:
        print("Face verification error:", e)

    return render_template("face_verification.html", user=user)


@app.route("/face_verification/status")
def face_verification_status():
    if is_admin():
        return jsonify(
            {"completed": False, "message": "Admin users do not use face verification."}
        )
    if not login_required():
        return jsonify({"completed": False, "message": "Not logged in."}), 401

    user = db.session.get(User, session["user_id"])
    if not user:
        return jsonify({"completed": False, "message": "User not found."}), 404

    return jsonify(
        {
            "completed": bool(user.face_image),
            "face_image": user.face_image,
            "message": (
                "Face verification completed."
                if user.face_image
                else "Waiting for face verification..."
            ),
        }
    )


# =========================
# APTITUDE
# =========================
@app.route("/aptitude", methods=["GET", "POST"])
def aptitude():
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    if not login_required():
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])

    profile_redirect = _ensure_profile_and_face_verified(user)
    if profile_redirect:
        return profile_redirect

    if user.aptitude_done:
        if has_passed_aptitude(user):
            return redirect(url_for("technical"))
        if _can_retake(user):
            flash(
                f"You did not pass the aptitude round. Start a new attempt to retry the interview.",
                "warning",
            )
            return redirect(url_for("restart_interview"))
        flash(
            f"You did not pass the aptitude round. Minimum {MIN_APTITUDE_PASS_SCORE}/20 is required to continue.",
            "danger",
        )
        return redirect(url_for("dashboard"))

    # ✅ RESET FIX
    if session.get("interview_status") == "completed":
        user.hr_done = False
        user.aptitude_done = False
        user.technical_done = False
        user.coding_done = False
        db.session.commit()
        session["interview_status"] = "not_started"

    # ✅ Ensure attempt
    if not session.get("attempt_id"):
        ensure_first_attempt_exists(user)

    session["interview_status"] = "in_progress"

    # ✅ WARNING CHECK (FIXED INDENT)
    # if check_warnings(user):
    # stop_proctoring(user.id)
    # return "❌ Disqualified"

    mark_interview_started(user.id)
    start_proctoring(user.id)

    skills = user.skills.split(",") if user.skills else []
    aptitude_data = generate_aptitude_questions(skills)

    if request.method == "POST":
        questions = session.get("aptitude_questions", aptitude_data["questions"])
        score = 0
        for index, question in enumerate(questions):
            answer = request.form.get(f"q{index}")
            if answer and answer == question.get("answer"):
                score += 1

        user.aptitude_score = score
        user.aptitude_done = True
        db.session.commit()
        session.pop("aptitude_questions", None)

        if not has_passed_aptitude(user):
            _mark_latest_attempt_completed(user)
            flash(
                f"You scored {score}/20 on the aptitude round. You must score at least {MIN_APTITUDE_PASS_SCORE} to continue to Technical.",
                "danger",
            )
            return redirect(url_for("dashboard"))

        return redirect(url_for("technical"))

    session["aptitude_questions"] = aptitude_data["questions"]
    return render_template("aptitude.html", user=user, aptitude=aptitude_data)


# =========================
# TECHNICAL (🔥 SKILL BASED WITH DYNAMIC QUESTION GENERATOR)
# =========================
@app.route("/technical", methods=["GET", "POST"])
def technical():
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    if not login_required():
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])

    profile_redirect = _ensure_profile_and_face_verified(user)
    if profile_redirect:
        return profile_redirect

    if not session.get("attempt_id"):
        ensure_first_attempt_exists(user)

    session["interview_status"] = sync_interview_status_from_db(user)
    if session.get("interview_status") == "completed":
        attempts_completed = get_attempt_count(user.id)
        can_retake = attempts_completed < MAX_ATTEMPTS
        return redirect(url_for("dashboard") if can_retake else url_for("results"))

    if not user.aptitude_done or not has_passed_aptitude(user):
        flash(
            f"Please complete and pass the aptitude round before accessing the technical round. Minimum {MIN_APTITUDE_PASS_SCORE}/20 is required.",
            "warning",
        )
        return redirect(url_for("dashboard"))

    if user.technical_done:
        if has_passed_technical(user):
            return redirect(url_for("coding"))
        if _can_retake(user):
            flash(
                "You did not pass the technical round. Start a new attempt to retry the interview.",
                "warning",
            )
            return redirect(url_for("restart_interview"))
        flash(
            "You did not pass the technical round and cannot continue to coding.",
            "danger",
        )
        return redirect(url_for("dashboard"))

    # if check_warnings(user):
    # stop_proctoring(user.id)
    # return "❌ Disqualified"

    session["interview_status"] = "in_progress"
    mark_interview_started(user.id)
    start_proctoring(user.id)

    # Generate questions dynamically based on user.skills
    skills = user.skills.split(",") if user.skills else []
    questions = generate_technical_questions(skills)
    if not questions:
        questions = ["Explain any programming concept"]

    if request.method == "POST":
        score_value = request.form.get("score")
        try:
            raw_score = int(score_value or 0)
        except (ValueError, TypeError):
            raw_score = 0

        questions = generate_technical_questions(skills)
        max_raw_score = len(questions) * 20 if questions else 40

        normalized_score = _normalize_technical_score(raw_score, max_raw_score)
        app.logger.debug("Technical raw score: %s", raw_score)
        app.logger.debug(
            "Technical calculated score: %s from raw %s and max_raw_score %s",
            normalized_score,
            raw_score,
            max_raw_score,
        )

        # Fallback: compute a heuristic score from submitted answers when JavaScript scoring fails or is low.
        if normalized_score < MIN_TECHNICAL_PASS_SCORE:
            fallback_raw = _compute_technical_score_from_answers(request.form)
            fallback_score = _normalize_technical_score(fallback_raw, max_raw_score)
            app.logger.debug("Technical fallback raw score: %s", fallback_raw)
            app.logger.debug(
                "Technical fallback calculated score: %s from raw %s",
                fallback_score,
                fallback_raw,
            )
            if fallback_score > normalized_score:
                normalized_score = fallback_score

        normalized_score = max(0, min(normalized_score, 40))
        app.logger.debug("Technical final score before save: %s", normalized_score)
        user.technical_score = normalized_score
        user.technical_done = True
        db.session.commit()
        app.logger.debug("Technical final score saved: %s", user.technical_score)

        if not has_passed_technical(user):
            _mark_latest_attempt_completed(user)
            flash(
                f"You scored {user.technical_score}. Minimum {MIN_TECHNICAL_PASS_SCORE} is required to continue to coding.",
                "danger",
            )
            return redirect(url_for("dashboard"))

        return redirect(url_for("coding"))

    return render_template("technical.html", user=user, questions=questions)


# =========================
# CODING
# =========================
@app.route("/coding", methods=["GET", "POST"])
def coding():
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    if not login_required():
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])

    profile_redirect = _ensure_profile_and_face_verified(user)
    if profile_redirect:
        return profile_redirect

    if not session.get("attempt_id"):
        ensure_first_attempt_exists(user)

    session["interview_status"] = sync_interview_status_from_db(user)
    if session.get("interview_status") == "completed":
        attempts_completed = get_attempt_count(user.id)
        can_retake = attempts_completed < MAX_ATTEMPTS
        return redirect(url_for("dashboard") if can_retake else url_for("results"))

    if not user.technical_done or not has_passed_technical(user):
        flash(
            f"Please complete and pass the technical round before accessing the coding round. Minimum {MIN_TECHNICAL_PASS_SCORE} is required.",
            "warning",
        )
        return redirect(url_for("dashboard"))

    if user.coding_done:
        if has_passed_coding(user):
            return redirect(url_for("hr"))
        if _can_retake(user):
            flash(
                "You did not pass the coding round. Start a new attempt to retry the interview.",
                "warning",
            )
            return redirect(url_for("restart_interview"))
        flash(
            "You did not pass the coding round and cannot continue to HR.",
            "danger",
        )
        return redirect(url_for("dashboard"))

    session["interview_status"] = "in_progress"
    # if check_warnings(user):
    # stop_proctoring(user.id)
    # return "❌ Disqualified"

    mark_interview_started(user.id)
    start_proctoring(user.id)

    skills = user.skills.split(",") if user.skills else []
    coding_data = generate_coding_questions(skills)

    if request.method == "POST":
        try:
            user.coding_score = int(request.form.get("score") or 0)
        except (ValueError, TypeError):
            user.coding_score = 0

        if user.coding_score < MIN_CODING_PASS_SCORE:
            fallback_score = _compute_coding_score_from_answers(request.form)
            if fallback_score > user.coding_score:
                user.coding_score = fallback_score

        # Enforce backend score caps.
        user.coding_score = max(0, min(user.coding_score, 40))
        user.coding_done = True
        db.session.commit()

        if not has_passed_coding(user):
            _mark_latest_attempt_completed(user)
            flash(
                f"You scored {user.coding_score}. Minimum {MIN_CODING_PASS_SCORE} is required to continue to HR.",
                "danger",
            )
            return redirect(url_for("dashboard"))

        return redirect(url_for("hr"))

    return render_template(
        "coding.html",
        user=user,
        coding_questions=coding_data["questions"],
        coding_keywords=coding_data["keywords"],
    )


# =========================
# =========================
# HR
# =========================
@app.route("/hr", methods=["GET", "POST"])
def hr():
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    if not login_required():
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])

    profile_redirect = _ensure_profile_and_face_verified(user)
    if profile_redirect:
        return profile_redirect

    # Development-only one-time HR test mode.
    if request.args.get("hr_test") == "1":
        session["hr_test_mode"] = True
        flash(
            "HR test mode enabled for this session. Coding gate is bypassed once.",
            "info",
        )

    hr_test_mode = session.get("hr_test_mode", False)

    # ✅ Allow HR only after coding round unless test mode is enabled.
    if not user.coding_done and not hr_test_mode:
        flash("Please complete the coding round before accessing HR.", "warning")
        return redirect(url_for("dashboard"))

    if not has_passed_coding(user) and not hr_test_mode:
        flash(
            f"You did not pass the coding round. Minimum {MIN_CODING_PASS_SCORE} is required to reach HR.",
            "danger",
        )
        return redirect(url_for("dashboard"))

    # Prevent re-entering the HR flow once the round is completed.
    if user.hr_done:
        session["interview_status"] = "completed"
        session.pop("hr_test_mode", None)
        return redirect(url_for("results"))

    attempts_completed = get_attempt_count(user.id)

    if not session.get("attempt_id"):
        ensure_first_attempt_exists(user)

    session["interview_status"] = sync_interview_status_from_db(user)

    # //

    # if check_warnings(user):
    # stop_proctoring(user.id)
    # try:
    # user.hr_done = True
    # user.hr_answer = user.hr_answer or None

    # latest = _get_latest_attempt(user.id)
    # if latest and latest.completed_at is None:
    #  latest.completed_at = datetime.utcnow()

    # db.session.commit()
    # except Exception:
    # pass
    # return redirect(url_for("dashboard"))

    session["interview_status"] = "in_progress"
    mark_interview_started(user.id)
    start_proctoring(user.id)

    # =========================
    # POST (FINAL SUBMISSION)
    # =========================
    if request.method == "POST":
        stop_proctoring(user.id)

        answers = request.form.getlist("answers[]")
        raw_answers = [a for a in answers if a is not None]
        cleaned_answers = [
            a.strip()
            for a in answers
            if a and a.strip() and a.strip() != "(no transcript captured)"
        ]
        user.hr_answer = " | ".join(cleaned_answers) if cleaned_answers else None

        # Calculate HR score dynamically from each spoken answer.
        user.hr_score = _compute_hr_score_from_answers(raw_answers)
        user.hr_score = max(0, min(user.hr_score, 20))

        user.hr_done = True

        # ✅ Mark interview completed
        session["interview_status"] = "completed"

        # ✅ Mark the attempt as completed
        try:
            attempt_id = session.get("attempt_id")
            if attempt_id:
                attempt = db.session.get(InterviewAttempt, attempt_id)
                if attempt and attempt.completed_at is None:
                    attempt.completed_at = datetime.now(timezone.utc)
        except Exception:
            pass

        db.session.commit()

        return redirect(url_for("results"))

    # =========================
    # GET
    # =========================
    skills = user.skills.split(",") if user.skills else []
    hr_questions = generate_hr_questions(skills)
    if len(hr_questions) < 6:
        hr_questions = (
            hr_questions
            + [
                "Tell me about yourself and your most recent project.",
                "Why are you interested in this role and our company?",
                "What are your strengths and how do they relate to this job?",
                "Describe a situation when you solved a difficult problem.",
                "How do you handle feedback and tough deadlines?",
                "How do you stay motivated during challenging projects?",
            ]
        )[:6]

    session.pop("answers", None)
    session.pop("warnings", None)
    session.pop("timer", None)
    # ✅ FIX: Keep interview_status as "in_progress" during HR interview
    # Do NOT set it to "not_started" as it breaks redirect logic
    session["interview_status"] = "in_progress"

    attempt_number = session.get("attempt_number") or 1
    # Render HR page for GET
    return render_template(
        "hr.html",
        user=user,
        questions=hr_questions,
        attempt_number=attempt_number,
        max_attempts=MAX_ATTEMPTS,
    )


# =========================
# RESULTS
# =========================
@app.route("/results")
def results():
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    if not login_required():
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])

    # Ensure monitoring is stopped after completion.
    try:
        stop_proctoring(user.id)
    except Exception:
        pass

    attempt_number = None
    try:
        attempt_id = session.get("attempt_id")
        if attempt_id:
            attempt = db.session.get(InterviewAttempt, attempt_id)
            if attempt and attempt.user_id == user.id:
                attempt_number = attempt.attempt_number
        if attempt_number is None:
            latest = _get_latest_attempt(user.id)
            attempt_number = latest.attempt_number if latest else 1
    except Exception:
        attempt_number = 1

    # Only allow retake while the current attempt number is below the maximum.
    # This keeps the results button in sync with the "Attempt X of Y" display.
    can_retake = _can_retake(user)
    session["interview_status"] = sync_interview_status_from_db(user)

    # Allow results page access if: session says completed OR database shows user.hr_done
    interview_status = session.get("interview_status")
    if interview_status != "completed" and not user.hr_done:
        return redirect(url_for("dashboard"))

    aptitude = max(0, min(user.aptitude_score or 0, 20))
    technical = max(0, min(user.technical_score or 0, 40))
    coding = max(0, min(user.coding_score or 0, 40))
    hr = max(0, min(user.hr_score or 0, 20))

    app.logger.debug("Technical final score for results page: %s", technical)
    total = aptitude + technical + coding + hr
    status = "SELECTED" if total >= 70 else "REJECTED"

    # Interview integrity score (based on silent monitoring warnings).
    try:
        warning_events = (
            WarningEvent.query.filter_by(user_id=user.id)
            .order_by(WarningEvent.created_at.desc())
            .all()
        )
    except Exception:
        warning_events = []

    total_warnings = len(warning_events)

    multiple_count = sum(
        1
        for ev in warning_events
        if ev and ev.message and ("Multiple" in ev.message or "multiple" in ev.message)
    )
    no_face_count = sum(
        1
        for ev in warning_events
        if ev and ev.message and "not visible" in ev.message.lower()
    )
    looking_away_count = sum(
        1
        for ev in warning_events
        if ev and ev.message and "looking away" in ev.message.lower()
    )

    # Developer-level scoring: heavy penalty for integrity-breaking behaviors.
    integrity_score = max(
        0,
        100 - (multiple_count * 14) - (no_face_count * 18) - (looking_away_count * 10),
    )

    recent_warnings = [ev.message for ev in warning_events[:6] if ev and ev.message]

    # Generate dynamic suggestions based on performance
    suggestions = generate_interview_suggestions(user, warning_events, total_warnings)

    attempt = None
    if session.get("attempt_id"):
        attempt = db.session.get(InterviewAttempt, session.get("attempt_id"))
    if not attempt or attempt.user_id != user.id:
        attempt = _get_latest_attempt(user.id)

    if attempt and attempt.completed_at:
        timestamp = attempt.completed_at
    elif attempt and attempt.created_at:
        timestamp = attempt.created_at
    else:
        timestamp = datetime.now(timezone.utc)

    # Convert UTC to local timezone
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    local_timestamp = timestamp.astimezone()

    interview_date = local_timestamp.strftime("%d %B %Y")
    interview_time = local_timestamp.strftime("%H:%M")
    interview_id = (
        f"INT-{timestamp.year}-{attempt.id:04d}" if attempt and attempt.id else None
    )

    return render_template(
        "results.html",
        user=user,
        attempt_number=attempt_number,
        max_attempts=MAX_ATTEMPTS,
        aptitude=aptitude,
        technical=technical,
        coding=coding,
        hr=hr,
        total=total,
        status=status,
        integrity_score=integrity_score,
        total_warnings=total_warnings,
        multiple_count=multiple_count,
        no_face_count=no_face_count,
        looking_away_count=looking_away_count,
        recent_warnings=recent_warnings,
        hr_answers_summary=user.hr_answer,
        can_retake=can_retake,
        suggestions=suggestions,
        interview_date=interview_date,
        interview_time=interview_time,
        interview_id=interview_id,
    )


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    stop_all_processes()
    role = get_user_role()
    session.clear()
    # Always send users back to dashboard; it will render in guest mode.
    return redirect(url_for("dashboard"))


@app.route("/interview/heartbeat", methods=["POST"])
def interview_heartbeat():
    """
    Keep camera monitoring alive during active interviews.
    Called periodically from frontend to ensure proctor process doesn't get terminated.
    """
    if not login_required():
        return jsonify({"status": "error", "message": "not_logged_in"}), 401

    user = db.session.get(User, session.get("user_id"))
    if not user:
        return jsonify({"status": "error", "message": "user_not_found"}), 404

    # Only restart proctoring if interview is actively in progress.
    interview_status = sync_interview_status_from_db(user)
    if interview_status == "in_progress":
        try:
            start_proctoring(user.id)
        except Exception:
            pass

    return jsonify({"status": "ok", "interview_status": interview_status}), 200


@app.route("/interview/exit", methods=["POST"])
def interview_exit():
    """
    Stop camera monitoring when user leaves the interview pages.
    """
    if not login_required():
        return ("", 403)

    user = db.session.get(User, session.get("user_id"))
    if not user:
        return ("", 204)

    try:
        stop_proctoring(user.id)
    except Exception:
        pass

    return ("", 204)


# =========================
# ADMIN AUTH + DASHBOARD
# =========================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if is_admin():
        return redirect(url_for("admin_dashboard"))

    # If a candidate is logged in and tries admin login, block for safety.
    if get_user_role() == "candidate":
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()

        if email == ADMIN_EMAIL.lower() and check_password_hash(
            ADMIN_PASSWORD_HASH, password
        ):
            session["user_role"] = "admin"
            session["role"] = "admin"  # backwards compatible
            session["interview_status"] = "not_started"
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin credentials.", "danger")
        return render_template("admin_login.html")

    return render_template("admin_login.html")


@app.route("/admin/test-email")
def test_email():
    """Test email notification - for admin testing only"""
    if not is_admin():
        return "Unauthorized", 403

    if not is_email_configured():
        return (
            "Email sending is not configured. Set MAIL_USERNAME or SMTP_USERNAME and MAIL_PASSWORD or SMTP_PASSWORD, or enable Gmail OAuth2 with the correct environment variables.",
            400,
        )

    sent = send_login_notification("Test Candidate", "test@example.com")
    if sent:
        return "Test email sent successfully! Check your mailbox."
    return "Error sending test email. Check server logs for details.", 500


@app.route("/admin")
def admin_dashboard():
    if get_user_role() != "admin":
        if get_user_role() == "candidate":
            return redirect(url_for("dashboard"))
        return redirect(url_for("admin_login"))

    users = User.query.all()
    stats = calculate_admin_stats(users)

    return render_template(
        "admin.html",
        user={"name": "Admin"},
        users=users,
        active_page="dashboard",
        **stats,
    )


@app.route("/admin/user/<int:user_id>")
def admin_user_detail(user_id):
    if get_user_role() != "admin":
        return redirect(url_for("admin_login"))

    user = db.session.get(User, user_id)
    if not user:
        return redirect(url_for("admin_dashboard"))

    return render_template(
        "admin_user_detail.html", user=user, email_configured=is_email_configured()
    )


@app.route("/admin/user/<int:user_id>/toggle_complete", methods=["POST"])
def admin_toggle_complete(user_id):
    if get_user_role() != "admin":
        return ("", 403)

    user = db.session.get(User, user_id)
    if user:
        user.aptitude_done = not user.aptitude_done
        user.technical_done = user.aptitude_done
        user.coding_done = user.aptitude_done
        user.hr_done = user.aptitude_done
        db.session.commit()

    return redirect(url_for("admin_user_detail", user_id=user_id))


@app.route("/admin/user/<int:user_id>/send_result_email", methods=["POST"])
def admin_send_result_email(user_id):
    if get_user_role() != "admin":
        return redirect(url_for("admin_login"))

    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    recipient = (request.form.get("email") or "").strip()
    selection = (request.form.get("result") or "rejected").strip().lower()
    message = (request.form.get("message") or "").strip()

    if not recipient:
        flash("Please provide a recipient email.", "warning")
        return redirect(url_for("admin_user_detail", user_id=user_id))

    if not is_email_configured():
        flash(
            "Result email is not configured. Set MAIL_USERNAME and either MAIL_PASSWORD or Gmail OAuth2 env vars.",
            "danger",
        )
        return redirect(url_for("admin_user_detail", user_id=user_id))

    sent = send_result_email(user, recipient, selection, message)
    if sent:
        flash("Result email sent successfully.", "success")
    else:
        flash(
            "Failed to send result email. Check server logs and mail configuration.",
            "danger",
        )

    return redirect(url_for("admin_user_detail", user_id=user_id))


@app.route("/admin/questions", methods=["GET", "POST"])
@admin_required
def admin_questions():
    question_bank = load_question_bank()

    if request.method == "POST":
        skill = (request.form.get("skill") or "").strip()
        question = (request.form.get("question") or "").strip()
        if skill and question:
            add_question(skill, question)
            return redirect(url_for("admin_questions"))

    return render_template(
        "admin_questions.html",
        user={"name": "Admin"},
        question_bank=question_bank,
        active_page="questions",
    )


@app.route("/admin/interviews")
@admin_required
def admin_interviews():
    attempts = InterviewAttempt.query.order_by(InterviewAttempt.created_at.desc()).all()
    attempts_data = []
    for attempt in attempts:
        user = db.session.get(User, attempt.user_id)
        attempts_data.append(
            {
                "id": attempt.id,
                "candidate_name": user.name if user else "Unknown",
                "email": user.email if user else "Unknown",
                "attempt_number": attempt.attempt_number,
                "created_at": attempt.created_at,
                "completed_at": attempt.completed_at,
                "status": "Completed" if attempt.is_completed() else "In Progress",
                "progress": "Completed" if user and user.hr_done else "In Progress",
            }
        )

    completed_attempts = sum(1 for a in attempts_data if a["status"] == "Completed")
    return render_template(
        "admin_interviews.html",
        user={"name": "Admin"},
        attempts=attempts_data,
        total_attempts=len(attempts_data),
        completed_attempts=completed_attempts,
        active_page="interviews",
    )


@app.route("/admin/reports")
@admin_required
def admin_reports():
    users = User.query.all()
    stats = calculate_admin_stats(users)
    top_candidates = sorted(users, key=lambda u: u.total_score(), reverse=True)[:10]
    total_warnings = sum(u.warning_count or 0 for u in users)

    return render_template(
        "admin_reports.html",
        user={"name": "Admin"},
        stats=stats,
        top_candidates=top_candidates,
        total_warnings=total_warnings,
        active_page="reports",
    )


# =========================
# RESUME / PERFORMANCE / SETTINGS (Dropdown links)
# =========================
@app.route("/resume")
def resume_view():
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    if not login_required():
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])
    resume_url = (
        url_for("static", filename=user.resume) if user and user.resume else None
    )
    return render_template("resume.html", user=user, resume_url=resume_url)


@app.route("/performance")
def performance_view():
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    if not login_required():
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])
    aptitude = max(0, min(user.aptitude_score or 0, 20))
    technical = max(0, min(user.technical_score or 0, 40))
    coding = max(0, min(user.coding_score or 0, 40))
    hr_score = max(0, min(user.hr_score or 0, 20))

    app.logger.debug("Technical final score for performance page: %s", technical)
    total = aptitude + technical + coding + hr_score
    status = "SELECTED" if total >= 70 else "REJECTED"

    return render_template(
        "performance.html",
        user=user,
        aptitude=aptitude,
        technical=technical,
        coding=coding,
        hr=hr_score,
        total=total,
        status=status,
    )


@app.route("/settings")
def settings_view():
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    if not login_required():
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])
    return render_template("settings.html", user=user)


# RESTART
@app.route("/restart_interview")
def restart_interview():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])
    if not user or not _can_retake(user):
        return redirect(url_for("dashboard"))

    session["interview_status"] = "not_started"
    session.pop("answers", None)
    session.pop("warnings", None)
    session.pop("attempt_id", None)
    session.pop("attempt_number", None)
    session.pop("hr_test_mode", None)
    session["timer"] = INTERVIEW_DURATION_SECONDS

    try:
        start_new_attempt(user)
    except ValueError:
        return redirect(url_for("results"))

    return redirect(url_for("aptitude"))


# =========================
# SOCKET.IO EVENTS
# =========================
@socketio.on("connect")
def on_socket_connect():
    user_id = session.get("user_id")
    if not user_id:
        return

    join_room(f"user_{user_id}")
    with _session_lock:
        _connected_user_ids.add(user_id)

    user = db.session.get(User, user_id)
    if user:
        _ensure_session_state(user)
        payload = _build_session_payload(user)
        socketio.emit("session_update", payload, room=f"user_{user_id}")

    global _background_task_started
    with _session_lock:
        if not _background_task_started:
            _background_task_started = True
            socketio.start_background_task(_background_emit_loop)


@socketio.on("disconnect")
def on_socket_disconnect():
    user_id = session.get("user_id")
    if not user_id:
        return
    with _session_lock:
        _connected_user_ids.discard(user_id)


# =========================
# RUN
# =========================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    # -------------------------
    # Share / Public access
    # -------------------------
    # Run on all network interfaces so devices on your LAN (and tools like ngrok)
    # can reach the server.
    #
    # Example:
    #   export HOST=0.0.0.0
    #   export PORT=5000
    #
    # ngrok (temporary public URL):
    #   1) Start the app: python app.py
    #   2) Run: ngrok http 5000
    #   3) Use the https://xxxx.ngrok-free.app URL in your mobile browser
    #
    # Deployment-ready:
    # Many platforms (Render/Railway/Fly.io) provide PORT via environment variable.
    # Keep host 0.0.0.0 and read PORT from the environment.
    # ngrok requirement: bind to 0.0.0.0 so the public tunnel can reach us.
    # Deployment compatibility: keep reading PORT from the environment.
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("DEBUG", "true").lower() in ("1", "true", "yes", "on")
    socketio.run(app, host=host, port=port, debug=debug)
