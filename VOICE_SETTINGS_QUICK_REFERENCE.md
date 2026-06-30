# Quick Reference: Voice Detection Settings

## Critical Settings Explained

### Energy Threshold (Most Important)

```
Lower Value = More Sensitive (detects quiet voices)
Higher Value = Less Sensitive (only loud voices)

Range: 100-400
Recommended: 150 (optimized for low voices)

Adjust if:
- Missing soft speech → Decrease (100-120)
- Too many false positives → Increase (180-200)
```

### Pause Threshold

```
Time (seconds) of silence to detect end of phrase
Too Short = Cuts off sentences
Too Long = Waits too long

Default: 0.8 seconds
Adjust if:
- Natural pauses are cut off → Increase (0.9-1.0)
- Too slow to detect end → Decrease (0.6-0.7)
```

### Phrase Threshold

```
Minimum audio duration (seconds) to consider as speech
Too High = Misses single words
Too Low = Captures noise as words

Default: 0.1 seconds
Adjust if:
- Missing short words (yes/no) → Decrease (0.05-0.08)
- Too much noise detected → Increase (0.15-0.2)
```

### Calibration Duration

```
Time (seconds) to adjust for ambient noise
Too Short = Poor noise detection
Too Long = Takes too much time

Default: 3 seconds
Adjust if:
- Poor in noisy environments → Increase (4-5)
- Good baseline, just calibrate faster → Decrease (2)
```

---

## Quick Adjustment Guide

### Problem: Missing Low Volume Words

```python
# In voice_config.py:
INITIAL_ENERGY_THRESHOLD = 100  # Decrease from 150
CALIBRATION_DURATION = 4         # Increase from 3
PHRASE_THRESHOLD = 0.05          # Decrease from 0.1
```

### Problem: Missing Words in Noisy Environment

```python
# In voice_config.py:
INITIAL_ENERGY_THRESHOLD = 180   # Increase from 150
CALIBRATION_DURATION = 5         # Increase from 3
PAUSE_THRESHOLD = 1.0            # Increase from 0.8
```

### Problem: Captures Too Much Noise/Background

```python
# In voice_config.py:
INITIAL_ENERGY_THRESHOLD = 200   # Increase from 150
PHRASE_THRESHOLD = 0.15          # Increase from 0.1
NON_SPEAKING_DURATION = 0.4      # Increase from 0.3
```

### Problem: Too Many Recognition Retries

```python
# In voice_config.py:
MAX_RETRIES = 1  # Reduce from 2
# Or improve microphone calibration:
CALIBRATION_DURATION = 4  # Increase from 3
```

---

## Environment-Specific Presets

### Use Quiet Setting

```python
# In voice_config.py or select from VOICE_PROFILES:
INITIAL_ENERGY_THRESHOLD = 100
CALIBRATION_DURATION = 4
PAUSE_THRESHOLD = 1.0
```

✓ Office, library, quiet room

### Use Standard Setting (Recommended)

```python
INITIAL_ENERGY_THRESHOLD = 150  # DEFAULT
CALIBRATION_DURATION = 3         # DEFAULT
PAUSE_THRESHOLD = 0.8           # DEFAULT
```

✓ Normal office with some background noise

### Use Noisy Setting

```python
INITIAL_ENERGY_THRESHOLD = 200
CALIBRATION_DURATION = 5
PAUSE_THRESHOLD = 0.7
```

✓ Open office, hallway, or noisy environment

### Use Aggressive Setting (Whispers)

```python
INITIAL_ENERGY_THRESHOLD = 80
CALIBRATION_DURATION = 2
PAUSE_THRESHOLD = 0.6
```

⚠️ Very sensitive - may capture more noise

---

## Testing Your Changes

### After Modifying voice_config.py:

```bash
# Test recognizer configuration
python -c "from audio_processor import AudioProcessor; p = AudioProcessor(); print(f'Energy: {p.recognizer.energy_threshold}')"

# Quick microphone test
python -c "
from audio_processor import create_processor
p = create_processor()
p.calibrate_microphone()
result = p.recognize_speech()
print(f'Test result: {result}')
"

# Full interview test
python voice_interview.py <test_user_id>
```

---

## Default Values Comparison

| Setting              | Old  | New  | Change                     |
| -------------------- | ---- | ---- | -------------------------- |
| energy_threshold     | 300  | 150  | -50% (2x more sensitive)   |
| calibration_duration | 1s   | 3s   | +200% (better accuracy)    |
| pause_threshold      | 0.5s | 0.8s | +60% (natural pauses)      |
| phrase_threshold     | 0.3s | 0.1s | -67% (catches short words) |
| listen_timeout       | 6s   | 8s   | +33% (more time)           |
| phrase_time_limit    | 12s  | 15s  | +25% (longer answers)      |
| max_retries          | 0    | 2    | +200% (better reliability) |

---

## Advanced: Microphone Gain

Currently using system microphone settings. To boost input:

### Windows

Settings → Sound → Advanced → Microphone → Input level slider → Turn up

### Linux

```bash
alsamixer
# Find Mic Boost, increase to +20dB
```

### macOS

System Preferences → Sound → Input → Use system-wide settings

---

## Debug: Check Current Settings

```bash
python -c "
from voice_config import VoiceConfig, get_config
print('Current Voice Settings:')
for key, value in get_config().items():
    print(f'  {key}: {value}')
"
```

---

## Common Misconfigurations

❌ **DON'T DO THIS:**

```python
# Energy threshold way too high - misses all quiet speech
INITIAL_ENERGY_THRESHOLD = 500

# Pause threshold too short - cuts sentences
PAUSE_THRESHOLD = 0.1

# Phrase threshold too high - misses small words
PHRASE_THRESHOLD = 0.5
```

✅ **DO THIS INSTEAD:**

```python
# Start with recommended defaults
INITIAL_ENERGY_THRESHOLD = 150
PAUSE_THRESHOLD = 0.8
PHRASE_THRESHOLD = 0.1

# Adjust gradually based on testing
# If missing words → lower energy threshold by 10-20
# If too much noise → raise energy threshold by 10-20
```

---

## Important Notes

1. **Internet Required**: Google Speech-to-Text requires internet connection
2. **Microphone Quality**: Better microphone = better results
3. **Test Different Values**: Settings depend on microphone, environment, and user
4. **Gradual Adjustment**: Change one setting at a time and test
5. **Logging**: Check logs for detailed info about what's happening

---

## Files to Modify

- `voice_config.py` - Main configuration
- `audio_processor.py` - Advanced audio settings (rarely needed)
- `voice_interview.py` - Interview flow (only if changing logic)

---

For detailed documentation, see: `VOICE_DETECTION_FIX.md`
