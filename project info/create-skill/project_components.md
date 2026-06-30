# Project Components and Dependencies

This file documents all the languages, frameworks, libraries, packages, and modules used in the Real-Time Online Interview project.

## Languages

- **Python**: Version 3.12.18 (as specified in runtime.txt)

## Frameworks

- **Flask**: Web framework for building the application (version 2.3.3)
- **Flask-SocketIO**: For real-time communication (version 5.3.6)
- **Flask-SQLAlchemy**: ORM for database interactions (version 3.0.5)

## Libraries

- **OpenCV**: Computer vision library for image processing (opencv-python==4.8.1.78)
- **NumPy**: Numerical computing library (version 1.26.4)
- **Ultralytics**: YOLO model library for object detection (version 8.4.37)
- **PyPDF2**: PDF processing library (version 3.0.1)
- **Eventlet**: Asynchronous networking library (version 0.33.3)
- **Gunicorn**: WSGI HTTP Server (version 21.2.0)

## Python Packages (from requirements.txt)

- bidict==0.23.1
- blinker==1.9.0
- click==8.3.3
- colorama==0.4.6
- Flask==2.3.3
- Flask-SocketIO==5.3.6
- Flask-SQLAlchemy==3.0.5
- greenlet==3.5.0
- h11==0.16.0
- itsdangerous==2.2.0
- Jinja2==3.1.6
- MarkupSafe==3.0.3
- pip==25.3
- PyPDF2==3.0.1
- python-engineio==4.13.1
- python-socketio==5.16.1
- simple-websocket==1.1.0
- SQLAlchemy==2.0.49
- typing_extensions==4.15.0
- Werkzeug==3.1.8
- wsproto==1.3.2
- numpy==1.26.4
- opencv-python==4.8.1.78
- ultralytics==8.4.37
- python-socketio==5.8.0
- python-engineio==4.7.1
- eventlet==0.33.3
- gunicorn==21.2.0

## Custom Modules

- **app.py**: Main Flask application file
- **face_detection.py**: Face detection functionality
- **face_verification.py**: Face verification using YOLO
- **voice_interview.py**: Voice interview handling
- **database/db.py**: Database configuration and models
- **models/user_model.py**: User data model
- **models/interview_attempt_model.py**: Interview attempt tracking
- **models/warning_event_model.py**: Warning event logging
- **modules/admin_utils.py**: Admin utility functions
- **modules/config.py**: Configuration settings
- **modules/utils.py**: General utility functions
- **utils/question_generator.py**: Dynamic question generation
- **utils/**init**.py**: Utils package initialization

## Database

- **SQLite**: Database engine (via SQLAlchemy)

## Other Technologies

- **HTML/CSS/JavaScript**: For frontend templates
- **Jinja2**: Templating engine
- **Socket.IO**: Real-time communication protocol
- **YOLOv8**: Object detection model (via ultralytics)
- **SMTP**: For email notifications (optional, requires MAIL_USERNAME/MAIL_PASSWORD)

## Environment

- **Virtual Environment**: .venv-1 (Python 3.12)
- **Operating System**: Windows (based on setup scripts)

## Main Application Logic

The Real-Time Online Interview application is a Flask-based web platform that conducts automated interviews with proctoring features. Here's the core working logic:

### User Workflow

1. **Registration/Login**: Users register with name, email, and password. Login authenticates and sets session roles (candidate or admin).
2. **Dashboard**: Post-login, candidates see their interview status and can start or resume interviews. Admins access monitoring dashboards.

### Interview Process

- **Stages**: Interviews progress through Aptitude, Technical, Coding, and HR rounds. Each stage loads dynamic questions from `question_bank.json` or generated via `question_generator.py`.
- **Question Handling**: Questions are served via SocketIO for real-time interaction. Answers are submitted and scored automatically.
- **Progress Tracking**: Interview attempts are logged in the database with timestamps and scores.

### Proctoring and Monitoring

- **Face Verification**: Uses YOLOv8 (via ultralytics) and OpenCV to detect and verify faces in real-time. Captures images and updates user profiles.
- **Voice Interview**: Handles audio-based questions, likely with speech recognition (though not fully implemented in code).
- **Real-Time Proctoring**: SocketIO enables live monitoring. Warnings are logged for suspicious activities (e.g., multiple faces, no face detected).
- **Admin Oversight**: Admins can view live interviews, user details, reports, and manage questions.

### Key Features

- **Dynamic Questions**: Generated based on user skills and interview stage using AI-like logic in `question_generator.py`.
- **Email Notifications**: Sends login alerts to admins (requires SMTP config).
- **Database**: SQLite stores users, interview attempts, and warning events.
- **Security**: Role-based access (candidate/admin), session management, and proctoring flags.
- **Results Page Fix**: Interview date, time, and ID are now generated dynamically from `InterviewAttempt` timestamps instead of hardcoded values.
- **Local Time Display**: Stored UTC timestamps are converted to local timezone for the displayed interview time.
- **Admin Login Fix**: Fixed missing `ADMIN_PASSWORD_HASH` import in `app.py` so admin authentication works correctly.
- **End-to-End Flow Verified**: New candidate flow was tested through registration, aptitude, technical, coding, HR, and results.

### Application Flow

- Flask routes handle GET/POST requests for pages like `/login`, `/dashboard`, `/aptitude`, etc.
- SocketIO events manage real-time data (e.g., question submissions, proctoring updates).
- Background tasks (e.g., face detection) run asynchronously.
- Templates render HTML with Jinja2, styled with CSS/JS.

This logic ensures a secure, automated interview experience with real-time proctoring.

## Key Code Snippets

Here are some representative code snippets illustrating the main logic:

### Flask App Initialization (from app.py)

```python
from flask import Flask
from flask_socketio import SocketIO
from database.db import db

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///interview.db'
db.init_app(app)
```

### User Login Route (from app.py)

```python
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email").strip().lower()
        password = request.form.get("password").strip()
        user = User.query.filter_by(email=email).first()
        if user and user.password == password:
            session["user_id"] = user.id
            session["user_role"] = "candidate"
            return redirect(url_for("dashboard"))
        return "Invalid credentials"
    return render_template("login.html")
```

### Face Verification Logic (from face_verification.py)

```python
import cv2
from ultralytics import YOLO

model = YOLO('yolov8n.pt')

def verify_face(image_path, user_id):
    results = model(image_path)
    faces = [r for r in results if r.names[r.cls] == 'person']
    if len(faces) == 1:
        # Update user face data
        return True
    return False
```

### SocketIO Event for Question Submission (from app.py)

```python
@socketio.on('submit_answer')
def handle_submit_answer(data):
    user_id = session.get('user_id')
    answer = data.get('answer')
    # Process answer, update score
    emit('next_question', {'question': next_q})
```

### Database Model Example (from models/user_model.py)

```python
from database.db import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    face_data = db.Column(db.Text)  # JSON string for face embeddings
```

These snippets show the core structure: Flask routing, real-time events, AI-based verification, and data persistence.

This list covers all components installed and used in the project.
