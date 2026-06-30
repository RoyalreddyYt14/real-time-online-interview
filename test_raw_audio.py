"""
Direct audio recording test using PyAudio (bypasses SpeechRecognition).
This tests if audio is actually flowing from your microphone.
"""
import sys

try:
    import pyaudio
    import wave
except ImportError:
    print("ERROR: Missing PyAudio. Install: pip install PyAudio")
    sys.exit(1)

import struct
import math


def list_devices():
    p = pyaudio.PyAudio()
    print("\nAvailable audio devices:")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        print(f"{i}: {info['name']} (channels: {info['maxInputChannels']}, {info['maxOutputChannels']})")
    p.terminate()


def record_raw(device_index=None, duration=3, out_file="test_audio_raw.wav"):
    """Record raw audio directly using PyAudio."""
    p = pyaudio.PyAudio()
    
    if device_index is not None:
        device_info = p.get_device_info_by_index(device_index)
        print(f"\nRecording from device {device_index}: {device_info['name']}")
        channels = int(device_info['maxInputChannels'])
        sample_rate = int(device_info['defaultSampleRate'])
    else:
        print(f"\nRecording from default device")
        channels = 1
        sample_rate = 44100

    print(f"  Channels: {channels}, Sample Rate: {sample_rate}, Duration: {duration}s")
    print("  Speak now...\n")

    # Open stream
    chunk_size = 1024
    stream = p.open(format=pyaudio.paInt16,
                    channels=channels,
                    rate=sample_rate,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=chunk_size)

    # Record
    frames = []
    for i in range(0, int(sample_rate / chunk_size * duration)):
        try:
            data = stream.read(chunk_size, exception_on_overflow=False)
            frames.append(data)
            print(".", end="", flush=True)
        except Exception as e:
            print(f"  Error reading chunk {i}: {e}")

    print("\n  Recording complete.")

    # Stop and close stream
    stream.stop_stream()
    stream.close()
    p.terminate()

    # Save WAV
    try:
        with wave.open(out_file, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(sample_rate)
            wf.writeframes(b''.join(frames))
        print(f"  Saved to: {out_file}")
    except Exception as e:
        print(f"  Failed to save WAV: {e}")
        return None

    # Analyze audio levels
    try:
        audio_data = b''.join(frames)
        audio_int16 = struct.unpack('<' + 'h' * (len(audio_data) // 2), audio_data)
        
        # Compute RMS
        rms = math.sqrt(sum(x ** 2 for x in audio_int16) / len(audio_int16))
        peak = max(abs(x) for x in audio_int16)
        dbfs = 20 * math.log10(rms / 32768.0) if rms > 0 else float('-inf')
        
        print(f"  RMS: {rms:.0f}, Peak: {peak}, dBFS: {dbfs:.1f}")
        
        if rms < 50:
            print(f"  ⚠️  WARNING: Very low audio level (RMS={rms:.0f})")
            print(f"     Microphone may be muted or not working!")
        elif rms < 500:
            print(f"  ⚠️  Low audio level (RMS={rms:.0f}) - speaker should be louder")
        else:
            print(f"  ✅ Good audio level detected!")
            
    except Exception as e:
        print(f"  Could not analyze: {e}")

    return out_file


if __name__ == "__main__":
    import sys
    
    if "--list" in sys.argv:
        list_devices()
    else:
        device = None
        if "--device" in sys.argv:
            idx = sys.argv.index("--device")
            if idx + 1 < len(sys.argv):
                device = int(sys.argv[idx + 1])
        
        print("="*60)
        print("RAW AUDIO RECORDING TEST")
        print("="*60)
        
        list_devices()
        
        print("\n" + "="*60)
        print(f"Testing device {device if device is not None else 'default'}...")
        print("="*60)
        
        record_raw(device, duration=4)
        
        print("\n✅ If RMS > 50, your microphone is working!")
        print("   If RMS < 50, your microphone may be muted/not working.")
