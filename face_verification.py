import os
import time
import sys
import sqlite3
import traceback

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(ROOT_DIR, "instance", "face_verification.log")
FACES_DIR = os.path.join(ROOT_DIR, "static", "faces")
DB_PATH = os.path.join(ROOT_DIR, "instance", "interview.db")
MODEL_PATH = os.path.join(ROOT_DIR, "yolov8n.pt")


def write_log(message, exc=False):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(message + "\n")
            if exc:
                traceback.print_exc(file=f)
    except Exception:
        pass
    print(message)
    if exc:
        traceback.print_exc()


# Headless test mode: exit before importing heavy libs
if "--headless-test" in sys.argv:
    write_log("Headless test mode active: exiting before importing heavy dependencies")
    sys.exit(0)

try:
    import cv2
    from ultralytics import YOLO
except Exception as e:
    write_log(f"Face verification startup error: {e}", exc=True)
    sys.exit(1)

user_id = sys.argv[1] if len(sys.argv) > 1 else None

# Headless test mode: exit quickly for CI / headless runs
if "--headless-test" in sys.argv:
    write_log("Headless test mode active: exiting without camera access")
    sys.exit(0)

os.makedirs(FACES_DIR, exist_ok=True)


def open_camera():
    backends = []
    if hasattr(cv2, "CAP_DSHOW"):
        backends.append(cv2.CAP_DSHOW)
    if hasattr(cv2, "CAP_MSMF"):
        backends.append(cv2.CAP_MSMF)
    backends.append(None)

    for backend in backends:
        for device in range(0, 4):
            try:
                cap = (
                    cv2.VideoCapture(device)
                    if backend is None
                    else cv2.VideoCapture(device, backend)
                )
                if cap.isOpened():
                    write_log(f"Opened camera device {device} using backend {backend}")
                    return cap
                cap.release()
            except Exception as inner_e:
                write_log(
                    f"Camera probe failed for device {device} backend {backend}: {inner_e}",
                    exc=True,
                )
    return None


cap = open_camera()
if not cap or not cap.isOpened():
    write_log("Face verification error: unable to open camera")
    sys.exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

# =========================
# MODELS
# =========================
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

model = YOLO(MODEL_PATH)

# =========================
# VARIABLES
# =========================
stable_frames = 0
required_frames = 8
verified = False

# =========================
# LOOP
# =========================
while True:

    ret, frame = cap.read()
    if not ret:
        break

    original_frame = frame.copy()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # =========================
    # YOLO DETECTION 🔥
    # =========================
    results = model(frame, verbose=False, imgsz=320)

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
                cv2.putText(
                    frame,
                    "Person",
                    (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 0),
                    2,
                )

            # PHONE
            if label in ["cell phone", "remote"]:
                phone_detected = True
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(
                    frame,
                    "Phone Detected",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2,
                )

    # =========================
    # 🔴 BLOCK CONDITIONS
    # =========================

    # MULTIPLE PERSON
    if person_count > 1:
        stable_frames = 0
        cv2.putText(
            frame,
            "Multiple Persons - Blocked",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
        )

        try:
            cv2.imshow("Face Verification System", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break
        except Exception:
            pass  # Headless environment
        continue

    # PHONE DETECTED
    if phone_detected:
        stable_frames = 0
        cv2.putText(
            frame,
            "Phone Detected - Blocked",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
        )

        try:
            cv2.imshow("Face Verification System", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break
        except Exception:
            pass  # Headless environment
        continue

    # =========================
    # FACE DETECTION 🔥
    # =========================
    faces = face_cascade.detectMultiScale(gray, 1.3, 6, minSize=(120, 120))

    if len(faces) == 1:

        x, y, w, h = faces[0]

        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)

        face_roi_gray = gray[y : y + h, x : x + w]
        face_roi_color = frame[y : y + h, x : x + w]

        eyes = eye_cascade.detectMultiScale(face_roi_gray)

        if len(eyes) >= 2:

            for ex, ey, ew, eh in eyes:
                cv2.rectangle(
                    face_roi_color, (ex, ey), (ex + ew, ey + eh), (255, 0, 0), 2
                )

            # CENTER CHECK
            frame_center = frame.shape[1] // 2
            face_center = x + w // 2

            if abs(face_center - frame_center) > 100:

                stable_frames = 0
                cv2.putText(
                    frame,
                    "Center Your Face",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                )

            else:

                stable_frames += 1

                cv2.putText(
                    frame,
                    "Verifying Face...",
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2,
                )

                # SAVE IMAGE
                if stable_frames >= required_frames:

                    filename = f"user_{user_id}_{int(time.time())}.jpg"
                    path = os.path.join(FACES_DIR, filename)

                    cv2.imwrite(path, original_frame)

                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()

                    cursor.execute(
                        "UPDATE users SET face_image=? WHERE id=?",
                        (f"faces/{filename}", user_id),
                    )

                    conn.commit()
                    conn.close()

                    verified = True
                    break

        else:
            stable_frames = 0
            cv2.putText(
                frame,
                "Look At Camera",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )

    else:
        stable_frames = 0
        cv2.putText(
            frame,
            "No Face Detected",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
        )

    # =========================
    # DISPLAY (SAFE)
    # =========================
    try:
        cv2.imshow("Face Verification System", frame)
    except Exception:
        pass  # Headless environment; no display available

    if verified:
        try:
            cv2.waitKey(2000)
        except Exception:
            pass
        break

    try:
        if cv2.waitKey(1) & 0xFF == 27:
            break
    except Exception:
        pass

cap.release()
cv2.destroyAllWindows()

#
# No forced client-side redirects from this script.
# The Flask route that launched face verification will render the template.
