import os
import subprocess
import sys
import threading
import time
import logging
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader

from flask_socketio import SocketIO, join_room

from database.db import db
from models.user_model import User
from models.warning_event_model import WarningEvent
from models.interview_attempt_model import InterviewAttempt

# Technical question generator (skill-based)
from utils.question_generator import generate_technical_questions

# Admin utilities
from modules.admin_utils import calculate_admin_stats

# General utilities
from modules.utils import (
    admin_required,
    get_user_role,
    login_required,
    is_admin,
    extract_text,
    extract_skills,
    format_mmss,
    get_proctor_stop_file,
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
# INTERVIEW_DURATION_SECONDS = 15 * 60  # 15 minutes
# MAX_ATTEMPTS = 3

from modules.config import (
    get_config_dict,
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    INTERVIEW_DURATION_SECONDS,
    MAX_ATTEMPTS,
    UPLOAD_FOLDER,
    INSTANCE_DIR,
    BASE_DIR,
)

app.config.update(get_config_dict())

# Per-user in-memory session state (timer + status).
_session_states = {}  # user_id -> {time_left, started, ended}
_connected_user_ids = set()
_session_lock = threading.Lock()
_background_task_started = False

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

# =========================
# GLOBAL PROCESS HANDLING
# =========================
# Per-user processes so we can start/stop monitoring cleanly.
voice_processes = {}  # user_id -> Popen
proctor_processes = {}  # user_id -> Popen


# =========================
# LOGIN CHECK
# =========================
def get_user_role() -> str | None:
    # Prefer the new session key but keep backward compatibility.
    return session.get("user_role") or session.get("role")


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
    attempts_completed = _get_completed_attempt_count(user.id)

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


def reset_interview_state_for_new_attempt(user: User) -> None:
    """
    Reset per-round flags/scores + warnings + timer for a new attempt.
    """
    # Stop camera monitoring to ensure webcam resources are released.
    stop_proctoring(user.id)

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
    completed = _get_completed_attempt_count(user.id)
    if completed >= MAX_ATTEMPTS:
        raise ValueError("Max attempts reached")

    latest = _get_latest_attempt(user.id)
    next_attempt_number = 1 if latest is None else latest.attempt_number + 1

    reset_interview_state_for_new_attempt(user)

    attempt = InterviewAttempt(user_id=user.id, attempt_number=next_attempt_number)
    db.session.add(attempt)
    db.session.commit()

    session["attempt_id"] = attempt.id
    session["attempt_number"] = attempt.attempt_number

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
    return redirect(url_for("dashboard"))


# =========================
# REGISTER
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        if User.query.filter_by(email=request.form["email"]).first():
            return "Email already exists"

        user = User(
            name=request.form["name"],
            email=request.form["email"],
            password=request.form["password"],
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

        user = User.query.filter_by(
            email=request.form["email"], password=request.form["password"]
        ).first()

        if user:
            session["user_id"] = user.id
            session["user_role"] = "candidate"
            session["role"] = "candidate"
            session["interview_status"] = "not_started"
            return redirect(url_for("dashboard"))

        return "Invalid credentials"

    return render_template("login.html")


# =========================
@app.route("/dashboard")
def dashboard():
    if is_admin():
        return redirect(url_for("admin_dashboard"))

    user = None
    attempt_number = 1
    can_retake = False

    # ✅ Proper login check
    if "user_id" in session:
        user = db.session.get(User, session.get("user_id"))

        if not user:
            session.clear()
            user = None
        else:
            # ✅ Get attempts count
            attempts_completed = _get_completed_attempt_count(user.id)
            can_retake = attempts_completed < MAX_ATTEMPTS

            # ✅ Simple attempt number logic
            attempt_number = attempts_completed + 1

            # Save in session (optional)
            session["attempt_number"] = attempt_number

    return render_template(
        "dashboard.html",
        user=user,
        attempt_number=attempt_number,
        max_attempts=MAX_ATTEMPTS,
        can_retake=can_retake,
    )


@app.route("/retake")
def retake_interview():
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    if not login_required():
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])
    if not user:
        return redirect(url_for("login"))

    # Only allow retake after completion.
    if not user.hr_done:
        return redirect(url_for("dashboard"))

    # Reset per-round session gating/state for the next attempt.
    session["interview_status"] = "not_started"
    session["answers"] = []
    session["warnings"] = []
    session["timer"] = INTERVIEW_DURATION_SECONDS

    try:
        start_new_attempt(user)
    except ValueError:
        return redirect(url_for("results"))

    return redirect(url_for("dashboard"))


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
        user.phone = request.form["phone"]
        user.education = request.form["education"]
        user.experience = request.form["experience"]

        # 🔥 RESUME UPLOAD
        file = request.files.get("resume")

        if file and file.filename != "":
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            user.resume = "resumes/" + filename

            text = extract_text(filepath)
            skills = extract_skills(text)

            user.skills = ",".join(skills)

            print("Extracted Skills:", skills)

        user.profile_completed = True
        db.session.commit()

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
        subprocess.Popen(
            [sys.executable, script_path, str(user.id)],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            cwd=BASE_DIR,
        )
    except Exception as e:
        print("Face verification error:", e)

    return render_template("face_verification.html")


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

    # ✅ POST
    if request.method == "POST":
        user.aptitude_score = int(request.form.get("score", 0))
        user.aptitude_done = True
        db.session.commit()
        return redirect(url_for("technical"))

    return render_template("aptitude.html")


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

    if not session.get("attempt_id"):
        ensure_first_attempt_exists(user)

    session["interview_status"] = sync_interview_status_from_db(user)
    if session.get("interview_status") == "completed":
        attempts_completed = _get_completed_attempt_count(user.id)
        can_retake = attempts_completed < MAX_ATTEMPTS
        return redirect(url_for("dashboard") if can_retake else url_for("results"))

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
        user.technical_score = int(request.form.get("score", 0))
        user.technical_done = True
        db.session.commit()
        return redirect(url_for("coding"))

    return render_template("technical.html", questions=questions)


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

    if not session.get("attempt_id"):
        ensure_first_attempt_exists(user)

    session["interview_status"] = sync_interview_status_from_db(user)
    if session.get("interview_status") == "completed":
        attempts_completed = _get_completed_attempt_count(user.id)
        can_retake = attempts_completed < MAX_ATTEMPTS
        return redirect(url_for("dashboard") if can_retake else url_for("results"))

    session["interview_status"] = "in_progress"
    # if check_warnings(user):
    # stop_proctoring(user.id)
    # return "❌ Disqualified"

    mark_interview_started(user.id)
    start_proctoring(user.id)

    if request.method == "POST":
        user.coding_score = int(request.form.get("score", 0))
        user.coding_done = True
        db.session.commit()
        return redirect(url_for("hr"))

    return render_template("coding.html")


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
    # ✅ Allow HR only after coding round
    if not user.coding_done:
        return redirect(url_for("dashboard"))
    # ✅ ADD THIS LINE
    attempts_completed = _get_completed_attempt_count(user.id)

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
        cleaned_answers = [a.strip() for a in answers if a and a.strip()]
        user.hr_answer = " | ".join(cleaned_answers)

        user.hr_score = 15
        user.hr_done = True

        # ✅ Mark interview completed
        session["interview_status"] = "completed"

        db.session.commit()

        return redirect(url_for("results"))

    # =========================
    # GET
    # =========================
    hr_questions = [
        "Tell me about yourself",
        "Why should we hire you",
        "What are your strengths",
    ]

    attempt_number = session.get("attempt_number") or 1

    return render_template(
        "hr.html",
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
    can_retake = int(attempt_number) < MAX_ATTEMPTS
    session["interview_status"] = sync_interview_status_from_db(user)
    if session.get("interview_status") != "completed":
        return redirect(url_for("dashboard"))

    aptitude = user.aptitude_score or 0
    technical = user.technical_score or 0
    coding = user.coding_score or 0
    hr = user.hr_score or 0

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

        if email == ADMIN_EMAIL.lower() and password == ADMIN_PASSWORD:
            session["user_role"] = "admin"
            session["role"] = "admin"  # backwards compatible
            session["interview_status"] = "not_started"
            return redirect(url_for("admin_dashboard"))

        return "Invalid admin credentials"

    return render_template("admin_login.html")


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
        **stats,
    )


@app.route("/admin/user/<int:user_id>")
def admin_user_detail(user_id):
    if get_user_role() != "admin":
        return redirect(url_for("admin_login"))

    user = db.session.get(User, user_id)
    if not user:
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_user_detail.html", user=user)


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
    aptitude = user.aptitude_score or 0
    technical = user.technical_score or 0
    coding = user.coding_score or 0
    hr_score = user.hr_score or 0

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

    # ✅ RESET USER STATE (VERY IMPORTANT)
    user.hr_done = False
    user.aptitude_done = False
    user.technical_done = False
    user.coding_done = False

    db.session.commit()

    # ✅ START NEW ATTEMPT
    try:
        start_new_attempt(user)
    except ValueError:
        return redirect(url_for("results"))

    session["interview_status"] = "not_started"

    return redirect(url_for("aptitude"))
    # 🔥 DIRECT START

    # ✅ RESET SESSION (VERY IMPORTANT)
    session["interview_status"] = "not_started"
    session.pop("answers", None)
    session.pop("warnings", None)
    session.pop("attempt_id", None)

    return redirect(url_for("dashboard"))


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
