"""
Audio diagnostic tool

Usage:
  python audio_diagnostic.py --list
  python audio_diagnostic.py --test --device 1 --duration 4

Options:
  --list            List available microphone devices with their index
  --test            Run a short recording and attempt recognition
  --device INDEX    Microphone device index to use for test
  --duration N      Recording duration in seconds (default 4)
  --offline         Force offline recognition (PocketSphinx)
"""

import argparse
import sys
import time

try:
    import speech_recognition as sr
except Exception as e:
    print("Missing dependency: SpeechRecognition. Install with: pip install SpeechRecognition")
    sys.exit(1)


def list_mics():
    names = sr.Microphone.list_microphone_names()
    if not names:
        print("No microphones found.")
        return
    print("Available microphones:")
    for i, name in enumerate(names):
        print(f"  {i}: {name}")


def test_record(device_index=None, duration=4, offline=False):
    r = sr.Recognizer()
    r.adjust_for_ambient_noise = getattr(r, 'adjust_for_ambient_noise')

    mic_args = {}
    if device_index is not None:
        mic_args['device_index'] = device_index

    try:
        with sr.Microphone(**mic_args) as source:
            print(f"Using microphone: {device_index if device_index is not None else 'default'}")
            print(f"Calibrating for ambient noise (1s)...")
            r.adjust_for_ambient_noise(source, duration=1)
            print(f"Recording for {duration} seconds. Speak now...")
            audio = r.record(source, duration=duration)
    except Exception as e:
        print(f"Microphone error: {e}")
        return

    # Try recognition
    if offline:
        try:
            print("Attempting offline PocketSphinx recognition...")
            text = r.recognize_sphinx(audio)
            print("Decoded (sphinx):", text)
            return
        except Exception as e:
            print("PocketSphinx recognition failed:", e)
            return

    # Try online (Google) first
    try:
        print("Attempting Google recognition (requires network)...")
        text = r.recognize_google(audio)
        print("Decoded (google):", text)
        return
    except sr.RequestError as e:
        print("Google STT request error (network or quota):", e)
    except sr.UnknownValueError:
        print("Google STT could not understand audio.")

    # Fallback to PocketSphinx if available
    try:
        print("Falling back to PocketSphinx (offline)...")
        text = r.recognize_sphinx(audio)
        print("Decoded (sphinx):", text)
    except Exception as e:
        print("PocketSphinx fallback failed:", e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--device', type=int)
    parser.add_argument('--duration', type=int, default=4)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()

    if args.list:
        list_mics()
        sys.exit(0)

    if args.test:
        test_record(device_index=args.device, duration=args.duration, offline=args.offline)
        sys.exit(0)

    parser.print_help()
