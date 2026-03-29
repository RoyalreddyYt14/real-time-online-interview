import cv2
import os
import time
import sys
import sqlite3
from ultralytics import YOLO

# ===============================
# GET USER ID
# ===============================
user_id = None

if len(sys.argv) > 1:
    user_id = sys.argv[1]

# Optional graceful stop flag (passed by app.py).
stop_file = None
if len(sys.argv) > 2:
    stop_file = sys.argv[2]

if not user_id:
    print("User ID missing")
    exit()

# ===============================
# CREATE IMAGE FOLDER
# ===============================
os.makedirs("static/faces", exist_ok=True)

# ===============================
# DATABASE FUNCTION (WARNING)
# ===============================
def add_warning(user_id, message):
    try:
        conn = sqlite3.connect("instance/interview.db")
        cursor = conn.cursor()

        # Store warning event for backend evaluation.
        # (If the table doesn't exist yet, we still update the summary fields.)
        try:
            cursor.execute(
                """
                INSERT INTO warning_events (user_id, message, created_at)
                VALUES (?, ?, datetime('now'))
                """,
                (user_id, message),
            )
        except Exception:
            pass

        cursor.execute("""
            UPDATE users 
            SET warning_count = COALESCE(warning_count,0) + 1,
                last_warning = ?
            WHERE id=?
        """, (message, user_id))

        conn.commit()
        conn.close()

    except Exception as e:
        # Silent failure; monitoring continues.
        pass

# ===============================
# CAMERA
# ===============================
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Camera error")
    exit()

# ===============================
# MODELS
# ===============================
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

eye_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_eye.xml"
)

model = YOLO("yolov8n.pt")

# ===============================
# VARIABLES
# ===============================
verified = False
stable_frames = 0
required_frames = 15

# ⚠️ ANTI-SPAM WARNING CONTROL
last_warning_time = 0
warning_cooldown = 5  # seconds

# Silent monitoring: keep camera processing running without showing UI windows
DISPLAY_ENABLED = False

# ===============================
# MAIN LOOP
# ===============================
while True:
    # Graceful stop: app.py writes this file before attempting termination.
    if stop_file and os.path.exists(stop_file):
        break

    ret, frame = cap.read()
    if not ret:
        break

    original_frame = frame.copy()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    current_time = time.time()

    # ===============================
    # YOLO DETECTION
    # ===============================
    results = model(frame, verbose=False)

    person_count = 0
    phone_detected = False

    for r in results:
        for box in r.boxes:

            cls = int(box.cls[0])
            label = model.names[cls]

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # PERSON
            if label == "person":
                person_count += 1
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 0), 2)
                cv2.putText(frame, "Person", (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

            # PHONE
            if label in ["cell phone", "remote"]:
                phone_detected = True
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, "Phone Detected", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # ===============================
    # CHEATING DETECTION (COOLDOWN)
    # ===============================
    if current_time - last_warning_time > warning_cooldown:

        if person_count > 1:
            add_warning(user_id, "Multiple persons detected")
            last_warning_time = current_time

        elif phone_detected:
            add_warning(user_id, "Mobile phone detected")
            last_warning_time = current_time

    # ===============================
    # FACE DETECTION
    # ===============================
    faces = face_cascade.detectMultiScale(gray, 1.2, 5, minSize=(80, 80))
    looking_away = False

    if len(faces) == 1:

        (x, y, w, h) = faces[0]

        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        face_roi_gray = gray[y:y + h, x:x + w]
        face_roi_color = frame[y:y + h, x:x + w]

        eyes = eye_cascade.detectMultiScale(face_roi_gray)

        if len(eyes) < 2:
            looking_away = True
            stable_frames = 0
            cv2.putText(frame, "Look At Camera", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        else:

            for (ex, ey, ew, eh) in eyes:
                cv2.rectangle(face_roi_color,
                              (ex, ey),
                              (ex + ew, ey + eh),
                              (255, 0, 0), 2)

            frame_center = frame.shape[1] // 2
            face_center = x + w // 2

            if abs(face_center - frame_center) > 120:
                looking_away = True
                stable_frames = 0
                cv2.putText(frame, "Look Straight", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            else:

                looking_away = False

                # ===============================
                # FACE VERIFICATION (ONLY ONCE)
                # ===============================
                if not verified:

                    cv2.putText(frame, "Verifying Face...", (x, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

                    stable_frames += 1

                    if stable_frames >= required_frames:

                        timestamp = int(time.time())
                        filename = f"user_{user_id}_{timestamp}.jpg"

                        save_path = os.path.join("static", "faces", filename)

                        cv2.imwrite(save_path, original_frame)

                        try:
                            conn = sqlite3.connect("instance/interview.db")
                            cursor = conn.cursor()

                            db_path = f"faces/{filename}"

                            cursor.execute(
                                "UPDATE users SET face_image=? WHERE id=?",
                                (db_path, user_id)
                            )

                            conn.commit()
                            conn.close()

                        except Exception:
                            # Silent failure; face verification is best-effort.
                            pass

                        verified = True

                else:
                    # AFTER VERIFIED → ONLY MONITOR
                    cv2.putText(frame, "Monitoring...", (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    else:
        stable_frames = 0
        cv2.putText(frame, "No Face Detected", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    # ===============================
    # SILENT WARNING DETECTION (COOLDOWN)
    # ===============================
    if current_time - last_warning_time > warning_cooldown:
        if len(faces) == 0:
            add_warning(user_id, "Face not visible")
            last_warning_time = current_time
        elif len(faces) > 1:
            add_warning(user_id, "Multiple faces detected")
            last_warning_time = current_time
        elif looking_away:
            add_warning(user_id, "Looking away")
            last_warning_time = current_time

    # ===============================
    # DISPLAY WINDOW (disabled in silent mode)
    # ===============================
    if DISPLAY_ENABLED:
        cv2.imshow("AI Proctoring System", frame)

        if cv2.waitKey(1) & 0xFF == 27:
            break

# ===============================
# ===============================
# CLEANUP
# ===============================
cap.release()
if DISPLAY_ENABLED:
    cv2.destroyAllWindows()