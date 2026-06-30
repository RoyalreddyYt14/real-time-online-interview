"""
Voice Recognition Configuration
Fine-tune voice detection settings for optimal performance.
"""

class VoiceConfig:
    """Voice recognition configuration settings."""
    
    # ===== ENERGY THRESHOLD SETTINGS =====
    # Energy threshold: Lower = more sensitive to quiet voices, Higher = only loud voices
    # Default range: 100-400 (lower = better for soft voices)
    INITIAL_ENERGY_THRESHOLD = 30  # ⚡ MAXIMUM SENSITIVITY FOR LOW-VOICE DETECTION (proven optimal)
    MIN_ENERGY_THRESHOLD = 15       # Minimum (ultra-sensitive for whispers)
    MAX_ENERGY_THRESHOLD = 100      # Maximum for low-voice environments
    MINIMUM_AUDIO_RMS = 20          # Minimum detectable RMS for a working microphone
    
    # ===== MICROPHONE CALIBRATION =====
    # Calibration duration: Longer = better noise profile, but takes more time
    CALIBRATION_DURATION = 3  # seconds (increased from 1 for better accuracy)
    QUICK_RECALIBRATION_INTERVAL = 3  # Recalibrate every N attempts
    
    # ===== LISTENING PARAMETERS =====
    # Timeout: Maximum time to wait for speech before giving up
    LISTEN_TIMEOUT = 30  # seconds (VERY generous timeout for low-voice detection)
    
    # Phrase time limit: Maximum duration of a single phrase
    PHRASE_TIME_LIMIT = 40  # seconds (allow much longer answers without cutting for slow speakers)
    
    # Pause threshold: Time of silence to consider end of phrase
    PAUSE_THRESHOLD = 0.5  # seconds (3.6x faster than default, detects end-of-phrase without cutting mid-sentence)
    
    # Phrase threshold: Minimum audio duration to consider as speech
    PHRASE_THRESHOLD = 0.01  # seconds (ultra-sensitive to very short or quiet words)
    
    # Non-speaking duration: time of silence within phrase before cutting
    NON_SPEAKING_DURATION = 0.25  # seconds (allows natural speech pauses while detecting continuous speech)
    
    # Dynamic energy adjustment for quieter speech (DISABLED - causes interference)
    # Setting to neutral values to prevent auto-adjustment that cuts words
    DYNAMIC_ENERGY_RATIO = 1.0
    DYNAMIC_ENERGY_ADJUSTMENT_DAMPING = 0.0
    
    # ===== RECOGNITION PARAMETERS =====
    # Maximum retries per recognition attempt
    MAX_RETRIES = 5  # Balanced retry count for low-voice detection
    
    # Questions loop parameters
    SILENCE_THRESHOLD = 3  # Max consecutive timeouts before skipping question
    MAX_ATTEMPTS_PER_QUESTION = 5  # Maximum attempts to capture answer
    
    # ===== SPEECH RATE =====
    # TTS speech rate in words per minute
    TTS_SPEECH_RATE = 170  # words per minute
    
    # ===== TIMEOUTS =====
    # Delay between question and listening start (seconds)
    PRE_LISTEN_DELAY = 1.0
    
    # Delay after speaking question (seconds)
    POST_QUESTION_DELAY = 0.5
    
    # Delay between retries (seconds)
    RETRY_DELAY = 0.5


def get_config() -> dict:
    """Get configuration as dictionary."""
    return {
        'energy_threshold': VoiceConfig.INITIAL_ENERGY_THRESHOLD,
        'min_threshold': VoiceConfig.MIN_ENERGY_THRESHOLD,
        'max_threshold': VoiceConfig.MAX_ENERGY_THRESHOLD,
        'calibration_duration': VoiceConfig.CALIBRATION_DURATION,
        'listen_timeout': VoiceConfig.LISTEN_TIMEOUT,
        'phrase_time_limit': VoiceConfig.PHRASE_TIME_LIMIT,
        'pause_threshold': VoiceConfig.PAUSE_THRESHOLD,
        'phrase_threshold': VoiceConfig.PHRASE_THRESHOLD,
        'non_speaking_duration': VoiceConfig.NON_SPEAKING_DURATION,
        'max_retries': VoiceConfig.MAX_RETRIES,
        'silence_threshold': VoiceConfig.SILENCE_THRESHOLD,
    }


# ===== PRESET PROFILES =====
VOICE_PROFILES = {
    'quiet_environment': {
        'energy_threshold': 40,  # Ultra-low for quiet rooms
        'pause_threshold': 0.5,
        'calibration_duration': 4,
    },
    'noisy_environment': {
        'energy_threshold': 80,  # Still low but slightly higher for noise
        'pause_threshold': 0.5,
        'calibration_duration': 5,
    },
    'standard': {
        'energy_threshold': 30,  # Ultra-low standard
        'pause_threshold': 0.5,
        'calibration_duration': 3,
    },
    'aggressive_detection': {
        'energy_threshold': 20,  # Extreme sensitivity for very low voices
        'pause_threshold': 0.4,  # Fast detection
        'calibration_duration': 2,
        'phrase_threshold': 0.01,
        'non_speaking_duration': 0.2,
    },
    'whisper_detection': {
        'energy_threshold': 15,  # Maximum sensitivity for whispers
        'pause_threshold': 0.3,
        'calibration_duration': 3,
        'phrase_threshold': 0.005,
        'non_speaking_duration': 0.15,
        'listen_timeout': 30,
    }
}
