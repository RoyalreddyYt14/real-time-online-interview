"""
Small diagnostic script to list microphones, record a short sample, save to `test_record.wav`,
and print RMS/peak/dBFS and other useful info.

Usage:
  # record with default device for 5 seconds
  python test_record.py

  # record with specific device index
  set AUDIO_DEVICE_INDEX=2
  python test_record.py

Or pass args:
  python test_record.py --device 2 --duration 4
"""
import argparse
import json
import wave
import math
import os
import sys

try:
    import speech_recognition as sr
except Exception as e:
    print("Missing dependency: pip install SpeechRecognition")
    raise

import audioop


def list_mics():
    try:
        names = sr.Microphone.list_microphone_names()
        for i, n in enumerate(names):
            print(f"{i}: {n}")
    except Exception as e:
        print("Failed to list microphones:", e)


def record_and_save(device_index, duration, out_path):
    r = sr.Recognizer()
    mic_args = {}
    if device_index is not None:
        mic_args['device_index'] = device_index

    print(f"Recording {duration}s using device_index={device_index}...")
    try:
        with sr.Microphone(**mic_args) as source:
            print("Adjusting for ambient noise (0.5s)... be quiet")
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.record(source, duration=duration)
    except Exception as e:
        print("Recording failed:", e)
        return None

    wav_bytes = audio.get_wav_data()

    # Save raw wav bytes
    try:
        with open(out_path, 'wb') as f:
            f.write(wav_bytes)
        print(f"Saved recording to: {out_path}")
    except Exception as e:
        print("Failed to save WAV:", e)

    # Analyze using wave + audioop
    try:
        with wave.open(out_path, 'rb') as w:
            nchannels = w.getnchannels()
            sampwidth = w.getsampwidth()
            framerate = w.getframerate()
            nframes = w.getnframes()
            frames = w.readframes(nframes)

        # If stereo, convert to mono for RMS
        if nchannels > 1:
            mono = audioop.tomono(frames, sampwidth, 1, 1)
        else:
            mono = frames

        rms = audioop.rms(mono, sampwidth)
        peak = audioop.max(mono, sampwidth)
        # max possible for signed samples
        max_possible = float((2 ** (8 * sampwidth - 1)) - 1)
        dbfs = 20 * math.log10(rms / max_possible) if rms > 0 else float('-inf')

        info = {
            'device_index': device_index,
            'duration': duration,
            'nchannels': nchannels,
            'sampwidth': sampwidth,
            'framerate': framerate,
            'nframes': nframes,
            'rms': rms,
            'peak': peak,
            'dBFS': dbfs,
            'wav_path': out_path,
        }
        print(json.dumps(info, indent=2))
        return info
    except Exception as e:
        print('Analysis failed:', e)
        return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', type=int, help='Microphone device index')
    parser.add_argument('--duration', type=int, default=5)
    parser.add_argument('--out', type=str, default='test_record.wav')
    args = parser.parse_args()

    env_idx = os.environ.get('AUDIO_DEVICE_INDEX')
    device = args.device if args.device is not None else (int(env_idx) if env_idx is not None else None)

    print('=== Microphone List ===')
    list_mics()
    print('=== Start Recording ===')
    info = record_and_save(device, args.duration, args.out)
    if info is None:
        sys.exit(2)
    print('=== Done ===')
