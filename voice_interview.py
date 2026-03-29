import os
import sqlite3
import sys
import time

try:
    import speech_recognition as sr  # type: ignore
except ImportError:
    print(
        "Missing dependency: speech_recognition. "
        "Install with: pip install SpeechRecognition"
    )
    sys.exit(1)

try:
    import pyttsx3  # type: ignore
except ImportError:
    print(
        "Missing dependency: pyttsx3. "
        "Install with: pip install pyttsx3"
    )
    sys.exit(1)

# =========================
# SAFE SPEAK FUNCTION 🔥 (FIX AUDIO BUG)
# =========================
def speak(text):
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 170)

        engine.say(text)
        engine.runAndWait()

        engine.stop()
        del engine   # 🔥 IMPORTANT (kill engine)

    except Exception as e:
        print("TTS Error:", e)


# =========================
# USER ID
# =========================
if len(sys.argv) < 2:
    print("Usage: python voice_interview.py <user_id>")
    sys.exit(1)

user_id = sys.argv[1]

# =========================
# QUESTIONS
# =========================
questions = [
    "Tell me about yourself",
    "Why should we hire you",
    "What are your strengths"
]

# =========================
# INIT
# =========================
recognizer = sr.Recognizer()
answers = []

# =========================
# LOOP QUESTIONS 🔥
# =========================
for q in questions:

    print("\n==============================")
    print("HR Question:", q)

    # 🔊 SPEAK (FIXED)
    speak(q)
    time.sleep(0.7)

    print("🎤 Speak your answer. Say 'done' when finished.")

    final_answer = ""
    silence_count = 0

    while True:
        try:
            with sr.Microphone() as source:
                print("Listening...")
                recognizer.adjust_for_ambient_noise(source, duration=0.5)

                audio = recognizer.listen(
                    source,
                    timeout=5,
                    phrase_time_limit=10
                )

            text = recognizer.recognize_google(audio).lower()
            print("You said:", text)

            # 🔥 STOP CONDITION
            if any(word in text for word in ["done", "finish", "stop"]):
                print("🛑 Answer finished")
                break

            final_answer += " " + text
            silence_count = 0

        except sr.WaitTimeoutError:
            silence_count += 1
            print("⌛ No speech detected...")

            if silence_count >= 2:
                print("➡ Moving to next question...")
                break

        except sr.UnknownValueError:
            print("❌ Could not understand, try again...")

        except sr.RequestError as e:
            # Usually happens when Google STT is unreachable / quota exceeded.
            print("❌ Speech recognition request error:", e)
            # Break to avoid an infinite loop of repeated failures.
            break

        except Exception as e:
            print("❌ Unexpected recognition error:", e)
            break

    answers.append(final_answer.strip())
    print("✅ Answer Saved")

# =========================
# SAVE TO DATABASE
# =========================
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "instance", "interview.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    all_answers = " | ".join(answers)

    cursor.execute(
        "UPDATE users SET hr_answer=? WHERE id=?",
        (all_answers, user_id)
    )

    conn.commit()
    conn.close()

except Exception as e:
    print("Database error:", e)

# =========================
# FINISH
# =========================
print("\n🎉 HR Interview Completed Successfully")

# 🔊 FINAL MESSAGE
speak("Your interview is completed. Thank you.")

time.sleep(1)
exit()