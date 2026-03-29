import cv2
import os
import time
import sys
import sqlite3
from ultralytics import YOLO

user_id = sys.argv[1]

os.makedirs("static/faces", exist_ok=True)

cap = cv2.VideoCapture(0)

# =========================
# MODELS
# =========================
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

eye_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_eye.xml"
)

model = YOLO("yolov8n.pt")

# =========================
# VARIABLES
# =========================
stable_frames = 0
required_frames = 15
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
                cv2.rectangle(frame, (x1,y1), (x2,y2), (255,255,0), 2)
                cv2.putText(frame, "Person", (x1,y1-5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 2)

            # PHONE
            if label in ["cell phone", "remote"]:
                phone_detected = True
                cv2.rectangle(frame, (x1,y1), (x2,y2), (0,0,255), 2)
                cv2.putText(frame, "Phone Detected", (x1,y1-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)

    # =========================
    # 🔴 BLOCK CONDITIONS
    # =========================

    # MULTIPLE PERSON
    if person_count > 1:
        stable_frames = 0
        cv2.putText(frame,
                    "Multiple Persons - Blocked",
                    (20,40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0,0,255),
                    2)

        cv2.imshow("Face Verification System", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
        continue

    # PHONE DETECTED
    if phone_detected:
        stable_frames = 0
        cv2.putText(frame,
                    "Phone Detected - Blocked",
                    (20,40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0,0,255),
                    2)

        cv2.imshow("Face Verification System", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
        continue

    # =========================
    # FACE DETECTION 🔥
    # =========================
    faces = face_cascade.detectMultiScale(
        gray, 1.3, 6, minSize=(120,120)
    )

    if len(faces) == 1:

        (x, y, w, h) = faces[0]

        cv2.rectangle(frame, (x,y), (x+w,y+h), (0,255,0), 3)

        face_roi_gray = gray[y:y+h, x:x+w]
        face_roi_color = frame[y:y+h, x:x+w]

        eyes = eye_cascade.detectMultiScale(face_roi_gray)

        if len(eyes) >= 2:

            for (ex, ey, ew, eh) in eyes:
                cv2.rectangle(face_roi_color,
                              (ex,ey),
                              (ex+ew,ey+eh),
                              (255,0,0), 2)

            # CENTER CHECK
            frame_center = frame.shape[1] // 2
            face_center = x + w // 2

            if abs(face_center - frame_center) > 100:

                stable_frames = 0
                cv2.putText(frame, "Center Your Face", (20,40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)

            else:

                stable_frames += 1

                cv2.putText(frame, "Verifying Face...",
                            (x, y-10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.8,
                            (0,255,0),
                            2)

                # SAVE IMAGE
                if stable_frames >= required_frames:

                    filename = f"user_{user_id}_{int(time.time())}.jpg"
                    path = os.path.join("static/faces", filename)

                    cv2.imwrite(path, original_frame)

                    conn = sqlite3.connect("instance/interview.db")
                    cursor = conn.cursor()

                    cursor.execute(
                        "UPDATE users SET face_image=? WHERE id=?",
                        (f"faces/{filename}", user_id)
                    )

                    conn.commit()
                    conn.close()

                    verified = True
                    break

        else:
            stable_frames = 0
            cv2.putText(frame, "Look At Camera", (20,40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)

    else:
        stable_frames = 0
        cv2.putText(frame, "No Face Detected", (20,40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)

    # =========================
    # DISPLAY
    # =========================
    cv2.imshow("Face Verification System", frame)

    if verified:
        cv2.waitKey(2000)
        break

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()

#
# No forced client-side redirects from this script.
# The Flask route that launched face verification will render the template.