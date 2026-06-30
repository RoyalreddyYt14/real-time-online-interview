"""
voice_interview.py
-------------------
Robust server-side voice capture for the HR interview using
SpeechRecognition + PyAudio. This script:

- Verifies dependencies (SpeechRecognition, PyAudio)
- Verifies microphone availability before recording
- Uses ambient noise adjustment before listening
- Uses `recognizer.listen(source, timeout=10, phrase_time_limit=15)`
- Handles common exceptions and prints debug output
- Saves incremental recognized text to the same SQLite DB used by Flask

Notes:
- This script is intended to run as a per-user subprocess (the Flask app
  currently launches it). It writes recognized text to the `users.hr_answer`
  column so the Flask app can read and emit updates to connected clients.

Compatible with Python 3.12.
"""

from __future__ import annotations

import os
import sys
import time
import sqlite3
import logging
from typing import Optional

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("voice_interview")


def dependency_check() -> None:
    """Ensure required packages are installed or print install hints and exit."""
    missing = []
    try:
        import speech_recognition as sr  # noqa: F401
    except Exception:  # pragma: no cover - runtime check
        missing.append("SpeechRecognition")
    try:
        import pyaudio  # noqa: F401
    except Exception:  # pragma: no cover
        missing.append("PyAudio")

    if missing:
        logger.error("Missing dependencies: %s", ", ".join(missing))
        logger.info("Install via pip: pip install SpeechRecognition pyaudio")
        logger.info(
            "On Windows if PyAudio fails: pip install pipwin; pipwin install pyaudio"
        )
        logger.info(
            "Alternative: use 'sounddevice' + 'soundfile' and adapt the recorder."
        )
        sys.exit(1)


def get_db_path() -> str:
    """Return the SQLite DB path used by the Flask app (instance/interview.db)."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "instance", "interview.db")


def save_transcription(user_id: str, text: str) -> None:
    """Append or set the HR answer for `user_id` in the users table.

    We append each recognized piece separated by ' | ' so the Flask app
    can display incremental progress. This function is defensive: it
    logs database errors but continues where appropriate.
    """
    db_path = get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # Read existing
        cur.execute("SELECT hr_answer FROM users WHERE id=?", (user_id,))
        row = cur.fetchone()
        existing = (row[0] or "") if row else ""
        if existing:
            new_val = existing + " | " + (text or "")
        else:
            new_val = text or ""
        cur.execute("UPDATE users SET hr_answer=? WHERE id=?", (new_val, user_id))
        conn.commit()
        conn.close()
        logger.info(
            "Saved transcription to DB for user %s (len=%d)", user_id, len(new_val)
        )
    except Exception as e:
        logger.exception("DB write failed: %s", e)


def verify_microphone() -> bool:
    """Return True when at least one microphone is detected and usable.

    This uses SpeechRecognition's list_microphone_names and a minimal
    PyAudio open/close smoke test to verify audio input can be opened.
    """
    try:
        import speech_recognition as sr
        import pyaudio
    except Exception as e:
        logger.warning("verify_microphone: dependency import failed: %s", e)
        return False

    try:
        names = sr.Microphone.list_microphone_names()
        if not names:
            logger.warning("No microphone names reported by SpeechRecognition")
            return False
        # Try to open the default input device briefly
        pa = pyaudio.PyAudio()
        try:
            default_index = None
            try:
                default_index = pa.get_default_input_device_info().get("index")
            except Exception:
                default_index = None
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=default_index,
            )
            stream.stop_stream()
            stream.close()
            pa.terminate()
            logger.info("Microphone smoke-test OK (device index=%s)", default_index)
            return True
        except Exception as e:
            logger.warning("Microphone open failed: %s", e)
            try:
                pa.terminate()
            except Exception:
                pass
            return False
    except Exception as e:
        logger.warning("Microphone detection failed: %s", e)
        return False


def recognize_loop(user_id: str) -> None:
    """Main recognition loop: speaks questions, listens, recognizes, saves.

    Implementation notes:
    - Uses ambient noise adjustment (duration=1)
    - Uses timeout=10 and phrase_time_limit=15 when listening
    - Handles WaitTimeoutError, UnknownValueError, RequestError
    - Adds detailed debug logs for troubleshooting
    """
    import speech_recognition as sr

    questions = [
        "Tell me about yourself",
        "Why should we hire you",
        "What are your strengths",
    ]

    r = sr.Recognizer()
    # Tune recognizer parameters for reliability with quieter voices
    r.energy_threshold = 300
    r.dynamic_energy_threshold = True
    r.pause_threshold = 0.5

    # Verify microphone availability
    if not verify_microphone():
        logger.error("No working microphone detected. Aborting voice interview.")
        # As a fallback, write a marker so Flask can see no mic
        save_transcription(user_id, "(no microphone detected)")
        return

    for idx, q in enumerate(questions, start=1):
        logger.info("Question %d/%d: %s", idx, len(questions), q)
        # Informational pause to let candidate prepare
        time.sleep(0.5)

        recognized_text: Optional[str] = None

        try:
            with sr.Microphone() as source:
                logger.info("Adjusting for ambient noise (1s)...")
                try:
                    r.adjust_for_ambient_noise(source, duration=1)
                except Exception as e:
                    logger.warning("adjust_for_ambient_noise failed: %s", e)

                logger.info("Listening (timeout=10, phrase_time_limit=15)...")
                try:
                    audio = r.listen(source, timeout=10, phrase_time_limit=15)
                except sr.WaitTimeoutError:
                    logger.warning(
                        "Listen timeout: no speech detected for question %d", idx
                    )
                    recognized_text = None
                else:
                    # Try recognition
                    try:
                        logger.info("Sending audio to Google Speech Recognition...")
                        recognized_text = r.recognize_google(audio, language="en-US")
                        logger.info("Recognized (raw): %s", recognized_text)
                    except sr.UnknownValueError:
                        logger.warning("UnknownValueError: Speech not understood")
                        recognized_text = None
                    except sr.RequestError as e:
                        logger.error(
                            "RequestError: Problem contacting Google API: %s", e
                        )
                        recognized_text = None
                    except Exception as e:
                        logger.exception("Unexpected recognition error: %s", e)
                        recognized_text = None

        except Exception as e:
            logger.exception("Microphone capture error: %s", e)
            recognized_text = None

        if recognized_text:
            # Save and also print for debugging/Flask tailing
            cleaned = str(recognized_text).strip()
            logger.info("Final recognized for question %d: %s", idx, cleaned)
            save_transcription(user_id, cleaned)
        else:
            logger.info(
                "No valid recognition for question %d; saving empty marker", idx
            )
            save_transcription(user_id, "")


def main() -> None:
    if len(sys.argv) < 2:
        logger.error("Usage: python voice_interview.py <user_id>")
        sys.exit(1)

    user_id = sys.argv[1]
    logger.info("Starting server-side voice interview for user %s", user_id)

    dependency_check()

    try:
        recognize_loop(user_id)
    except Exception as e:
        logger.exception("Unhandled error in recognize_loop: %s", e)


if __name__ == "__main__":
    main()
