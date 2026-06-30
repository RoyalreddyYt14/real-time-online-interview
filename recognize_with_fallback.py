"""
Fallback speech recognition with automatic device detection and extreme sensitivity.
"""
import logging
import time
import sys
import os

try:
    import speech_recognition as sr
except ImportError:
    print("Missing: pip install SpeechRecognition")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("recognize_with_fallback")

# Try to import voice config
try:
    from voice_config import VoiceConfig
except ImportError:
    class VoiceConfig:
        INITIAL_ENERGY_THRESHOLD = 10
        MIN_ENERGY_THRESHOLD = 5
        MAX_ENERGY_THRESHOLD = 80
        LISTEN_TIMEOUT = 30
        PHRASE_TIME_LIMIT = 40


def list_all_devices():
    """List all available audio devices."""
    try:
        names = sr.Microphone.list_microphone_names()
        for i, n in enumerate(names):
            print(f"{i}: {n}")
        return names
    except Exception as e:
        logger.error(f"Failed to list devices: {e}")
        return []


def try_device(device_index, timeout=5, phrase_limit=10):
    """Try to record from a specific device and return recognized text."""
    r = sr.Recognizer()
    r.energy_threshold = VoiceConfig.MIN_ENERGY_THRESHOLD  # ULTRA SENSITIVE
    r.dynamic_energy_threshold = True
    r.pause_threshold = 0.3
    r.phrase_threshold = 0.002
    r.non_speaking_duration = 0.1

    try:
        logger.info(f"Trying device {device_index}...")
        with sr.Microphone(device_index=device_index) as source:
            logger.info(f"  Adjusting for noise...")
            r.adjust_for_ambient_noise(source, duration=0.3)
            logger.info(f"  Threshold: {r.energy_threshold}. Listening for {timeout}s...")
            audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)

        logger.info(f"  Audio captured. Recognizing...")
        text = r.recognize_google(audio, language="en-US").lower().strip()
        logger.info(f"  ✅ Device {device_index} SUCCESS: '{text}'")
        return text

    except sr.WaitTimeoutError:
        logger.warning(f"  Device {device_index}: TIMEOUT (no speech)")
        return None
    except sr.UnknownValueError:
        logger.warning(f"  Device {device_index}: could not understand audio")
        return None
    except sr.RequestError as e:
        logger.error(f"  Device {device_index}: Google error - {e}")
        return None
    except Exception as e:
        logger.error(f"  Device {device_index}: {type(e).__name__}: {e}")
        return None


def recognize_with_auto_device(timeout=None, phrase_limit=None, max_retries=8):
    """
    Try all available devices until one works.
    """
    if timeout is None:
        timeout = VoiceConfig.LISTEN_TIMEOUT
    if phrase_limit is None:
        phrase_limit = VoiceConfig.PHRASE_TIME_LIMIT

    try:
        names = sr.Microphone.list_microphone_names()
    except Exception as e:
        logger.error(f"Failed to list devices: {e}")
        return None

    if not names:
        logger.error("No audio devices found!")
        return None

    logger.info(f"Found {len(names)} device(s). Will try each until one works...")

    # Filter to likely input devices
    input_devices = []
    for i, name in enumerate(names):
        lower = name.lower()
        if any(k in lower for k in ("output", "speaker", "playback", "stereo mix", "virtual", "loopback")):
            logger.debug(f"  Skipping {i}: {name} (likely output)")
        else:
            input_devices.append(i)

    logger.info(f"Candidate input devices: {input_devices}")

    attempt = 0
    device_pos = 0

    while attempt < max_retries:
        if not input_devices:
            logger.warning("No input devices left to try.")
            break

        device_idx = input_devices[device_pos % len(input_devices)]
        device_pos += 1
        attempt += 1

        logger.info(f"\nAttempt {attempt}/{max_retries}")
        result = try_device(device_idx, timeout=timeout, phrase_limit=phrase_limit)
        if result:
            return result

        time.sleep(0.5)

    logger.error(f"Failed after {max_retries} attempts on all devices.")
    return None


if __name__ == "__main__":
    # Test mode
    import sys
    if "--list" in sys.argv:
        print("Available devices:")
        list_all_devices()
    else:
        print("Testing speech recognition with auto-device fallback...")
        print("Speak into your microphone...\n")
        text = recognize_with_auto_device(timeout=10, phrase_limit=15)
        if text:
            print(f"\n✅ Recognized: {text}")
        else:
            print("\n❌ Failed to recognize speech")
